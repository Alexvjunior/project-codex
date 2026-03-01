import json
import os
import time
import uuid
from base64 import b64decode

import boto3
from botocore.exceptions import ClientError

from shared.events import build_event
from shared.config import validate_runtime_env
from shared.logging_utils import http_response, log_json, resolve_correlation_id
from shared.secrets import load_service_secrets
from shared.whatsapp import (
    build_session_id,
    header_get,
    normalize_messages,
    verify_meta_signature,
    verify_webhook_challenge,
)


sqs = boto3.client("sqs")
dynamodb = boto3.client("dynamodb")

INBOUND_QUEUE_URL = os.getenv("INBOUND_QUEUE_URL", "")
IDEMPOTENCY_TABLE = os.getenv("IDEMPOTENCY_TABLE", "")


def _plain_response(status_code: int, body: str, correlation_id: str):
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "text/plain",
            "x-correlation-id": correlation_id,
        },
        "body": body,
    }


def _extract_secret(secret_block, keys):
    for key in keys:
        value = secret_block.get(key)
        if value:
            return str(value)
    return ""


def _decode_raw_body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        try:
            return b64decode(raw).decode("utf-8")
        except Exception:
            return ""
    return raw


def _handle_healthcheck(correlation_id: str):
    return http_response(
        200,
        {
            "ok": True,
            "component": "ingest-whatsapp",
            "queue_configured": bool(INBOUND_QUEUE_URL),
            "idempotency_table_configured": bool(IDEMPOTENCY_TABLE),
        },
        correlation_id,
    )


def _handle_webhook_challenge(event, whatsapp_secret, correlation_id: str):
    verify_token = _extract_secret(
        whatsapp_secret,
        ["WHATSAPP_VERIFY_TOKEN", "verify_token", "VERIFY_TOKEN"],
    )
    params = event.get("queryStringParameters") or {}
    result = verify_webhook_challenge(params, verify_token)
    if result["ok"]:
        log_json("INFO", "ingest_whatsapp.challenge_verified", correlation_id)
        return _plain_response(200, result["challenge"], correlation_id)
    log_json("WARN", "ingest_whatsapp.challenge_failed", correlation_id)
    return http_response(403, {"ok": False, "error": "Invalid verify token"}, correlation_id)


def lambda_handler(event, context):
    correlation_id = resolve_correlation_id(event, context)
    log_json("INFO", "ingest_whatsapp.started", correlation_id)
    validate_runtime_env()
    secrets = load_service_secrets()
    whatsapp_secret = secrets.get("whatsapp", {})

    method = (
        ((event.get("requestContext") or {}).get("http") or {}).get("method")
        or event.get("httpMethod")
        or "POST"
    ).upper()
    raw_path = event.get("rawPath", "")

    if method == "GET" and raw_path.endswith("/health/ingest"):
        log_json("INFO", "ingest_whatsapp.healthcheck", correlation_id)
        return _handle_healthcheck(correlation_id)

    if method == "GET":
        return _handle_webhook_challenge(event, whatsapp_secret, correlation_id)

    raw_body = _decode_raw_body(event)
    app_secret = _extract_secret(
        whatsapp_secret,
        ["WHATSAPP_APP_SECRET", "META_APP_SECRET", "APP_SECRET", "app_secret"],
    )
    signature = header_get(event.get("headers") or {}, "x-hub-signature-256")
    if not verify_meta_signature(app_secret, raw_body, signature):
        log_json("WARN", "ingest_whatsapp.invalid_signature", correlation_id)
        return http_response(401, {"ok": False, "error": "Invalid signature"}, correlation_id)

    try:
        body = json.loads(raw_body or "{}")
    except json.JSONDecodeError:
        log_json("WARN", "ingest_whatsapp.invalid_json", correlation_id)
        return http_response(400, {"ok": False, "error": "Invalid JSON body"}, correlation_id)

    normalized_messages = normalize_messages(body)
    if not normalized_messages:
        log_json("INFO", "ingest_whatsapp.no_messages", correlation_id)
        return http_response(200, {"ok": True, "queued": 0}, correlation_id)

    queued = 0
    duplicates = 0
    for message in normalized_messages:
        channel_message_id = message.get("channel_message_id") or str(uuid.uuid4())
        session_id = build_session_id(message.get("from", "unknown"))
        idempotency_key = f"whatsapp:{channel_message_id}"
        event_payload = {
            "channel_message_id": channel_message_id,
            "from": message.get("from", ""),
            "to": message.get("to", ""),
            "is_echo": message.get("is_echo", False),
            "text": message.get("text", ""),
            "received_at": message.get("received_at", ""),
            "raw_type": message.get("raw_type", ""),
        }
        outbound_event = build_event(
            "whatsapp.message.received.v1",
            session_id,
            correlation_id,
            idempotency_key,
            event_payload,
        )
        try:
            dynamodb.put_item(
                TableName=IDEMPOTENCY_TABLE,
                Item={
                    "idempotency_key": {"S": idempotency_key},
                    "expires_at": {"N": str(int(time.time()) + 7 * 24 * 3600)},
                },
                ConditionExpression="attribute_not_exists(idempotency_key)",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                duplicates += 1
                continue
            raise

        sqs.send_message(
            QueueUrl=INBOUND_QUEUE_URL,
            MessageBody=json.dumps(outbound_event, ensure_ascii=True),
            MessageGroupId=session_id,
            MessageDeduplicationId=idempotency_key,
        )
        queued += 1

    log_json(
        "INFO",
        "ingest_whatsapp.completed",
        correlation_id,
        normalized=len(normalized_messages),
        queued=queued,
        duplicates=duplicates,
    )
    return http_response(200, {"ok": True, "queued": queued, "duplicates": duplicates}, correlation_id)

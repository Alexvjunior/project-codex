import json
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError

from shared.config import OUTBOX_TABLE, OUTBOUND_QUEUE_URL, validate_runtime_env
from shared.logging_utils import http_response, log_json, resolve_correlation_id
from shared.outbox import create_outbox_item, enqueue_outbox_event, session_phone
from shared.secrets import load_service_secrets


dynamodb = boto3.client("dynamodb")

PAYMENTS_TABLE = os.getenv("PAYMENTS_TABLE", "")
APPOINTMENTS_TABLE = os.getenv("APPOINTMENTS_TABLE", "")
IDEMPOTENCY_TABLE = os.getenv("IDEMPOTENCY_TABLE", "")


def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "payment_webhook.started", correlation_id)
    validate_runtime_env()
    load_service_secrets()

    method = (
        ((event.get("requestContext") or {}).get("http") or {}).get("method")
        or event.get("httpMethod")
        or "POST"
    ).upper()
    raw_path = event.get("rawPath", "")
    if method == "GET" and raw_path.endswith("/health/payment"):
        log_json("INFO", "payment_webhook.healthcheck", correlation_id)
        return http_response(
            200,
            {
                "ok": True,
                "component": "payment-webhook",
                "payments_table_configured": bool(PAYMENTS_TABLE),
                "appointments_table_configured": bool(APPOINTMENTS_TABLE),
            },
            correlation_id,
        )

    body_raw = event.get("body") or "{}"
    body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw

    gateway_event_id = body.get("gateway_event_id", str(uuid.uuid4()))
    appointment_id = body.get("appointment_id", "unknown_appointment")
    payment_id = body.get("payment_id", f"pay_{uuid.uuid4()}")

    try:
        dynamodb.put_item(
            TableName=IDEMPOTENCY_TABLE,
            Item={
                "idempotency_key": {"S": f"payment:{gateway_event_id}"},
                "expires_at": {"N": str(int(time.time()) + 30 * 24 * 3600)},
            },
            ConditionExpression="attribute_not_exists(idempotency_key)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            log_json("INFO", "payment_webhook.duplicate", correlation_id, gateway_event_id=gateway_event_id)
            return http_response(200, {"ok": True, "duplicate": True}, correlation_id)
        raise

    dynamodb.put_item(
        TableName=PAYMENTS_TABLE,
        Item={
            "payment_id": {"S": payment_id},
            "appointment_id": {"S": appointment_id},
            "status": {"S": "approved"},
            "created_at": {"S": str(int(time.time()))},
        },
    )

    dynamodb.update_item(
        TableName=APPOINTMENTS_TABLE,
        Key={"appointment_id": {"S": appointment_id}},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": {"S": "CONFIRMED"}},
    )

    session_id = body.get("session_id", "unknown_session")
    destination = body.get("patient_whatsapp") or session_phone(session_id)
    messages = [{"type": "text", "text": "Pagamento aprovado! Sua consulta foi confirmada."}]
    context_payload = {"appointment_id": appointment_id, "payment_id": payment_id}
    outbox_id = create_outbox_item(
        table_name=OUTBOX_TABLE,
        session_id=session_id,
        correlation_id=correlation_id,
        destination=destination,
        messages=messages,
        context=context_payload,
    )
    enqueue_outbox_event(
        queue_url=OUTBOUND_QUEUE_URL,
        session_id=session_id,
        correlation_id=correlation_id,
        outbox_id=outbox_id,
        destination=destination,
        messages=messages,
        context=context_payload,
    )

    log_json("INFO", "payment_webhook.completed", correlation_id, appointment_id=appointment_id, payment_id=payment_id)
    return http_response(200, {"ok": True}, correlation_id)

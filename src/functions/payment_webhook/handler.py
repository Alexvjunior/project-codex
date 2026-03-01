import json
import os
import time
import uuid
from base64 import b64decode
import hashlib
import hmac

import boto3
from botocore.exceptions import ClientError

from shared.config import OUTBOX_TABLE, OUTBOUND_QUEUE_URL, validate_runtime_env
from shared.events import build_event
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
    secrets = load_service_secrets(whatsapp=False, payment=True, llm=False)

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

    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = b64decode(raw_body).decode("utf-8")
    body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body

    gateway_event_id = body.get("gateway_event_id", str(uuid.uuid4()))
    appointment_id = body.get("appointment_id", "unknown_appointment")
    payment_id = body.get("payment_id", f"pay_{uuid.uuid4()}")
    payment_signature = ""
    for k, v in (event.get("headers") or {}).items():
        if str(k).lower() == "x-payment-signature":
            payment_signature = str(v)
            break

    payment_secret = (secrets.get("payment") or {}).get("PAYMENT_WEBHOOK_SECRET", "")
    expected = hmac.new(str(payment_secret).encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256).hexdigest()
    if payment_secret and (not payment_signature or not hmac.compare_digest(expected, payment_signature)):
        log_json("WARN", "payment_webhook.invalid_signature", correlation_id)
        return http_response(401, {"ok": False, "error": "Invalid payment signature"}, correlation_id)

    try:
        paid_at = body.get("paid_at")
        paid_at_value = str(paid_at) if paid_at else str(int(time.time()))
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": IDEMPOTENCY_TABLE,
                        "Item": {
                            "idempotency_key": {"S": f"payment:{gateway_event_id}"},
                            "expires_at": {"N": str(int(time.time()) + 30 * 24 * 3600)},
                        },
                        "ConditionExpression": "attribute_not_exists(idempotency_key)",
                    }
                },
                {
                    "Put": {
                        "TableName": PAYMENTS_TABLE,
                        "Item": {
                            "payment_id": {"S": payment_id},
                            "appointment_id": {"S": appointment_id},
                            "status": {"S": "paid"},
                            "gateway_payment_id": {"S": str(body.get("gateway_payment_id", ""))},
                            "amount": {"N": str(body.get("amount", 250.0))},
                            "currency": {"S": str(body.get("currency", "BRL"))},
                            "paid_at": {"S": paid_at_value},
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": APPOINTMENTS_TABLE,
                        "Key": {"appointment_id": {"S": appointment_id}},
                        "UpdateExpression": "SET #s = :s, payment_status = :ps",
                        "ExpressionAttributeNames": {"#s": "status"},
                        "ExpressionAttributeValues": {
                            ":s": {"S": "CONFIRMED"},
                            ":ps": {"S": "paid"},
                        },
                    }
                },
            ]
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("ConditionalCheckFailedException", "TransactionCanceledException"):
            log_json("INFO", "payment_webhook.duplicate", correlation_id, gateway_event_id=gateway_event_id)
            return http_response(200, {"ok": True, "duplicate": True}, correlation_id)
        raise

    session_id = body.get("session_id", "unknown_session")
    payment_confirmed_event = build_event(
        event_type="payment.confirmed.v1",
        session_id=session_id,
        correlation_id=correlation_id,
        idempotency_key=f"payment_confirmed:{gateway_event_id}",
        payload={
            "gateway_event_id": gateway_event_id,
            "appointment_id": appointment_id,
            "payment_id": payment_id,
            "amount": body.get("amount", 250.0),
            "currency": body.get("currency", "BRL"),
        },
    )
    log_json(
        "INFO",
        "payment_webhook.payment_confirmed_event",
        correlation_id,
        event_id=payment_confirmed_event["event_id"],
        appointment_id=appointment_id,
    )

    destination = body.get("patient_whatsapp") or session_phone(session_id)
    messages = [{"type": "text", "text": "Pagamento aprovado! Sua consulta foi confirmada."}]
    context_payload = {
        "appointment_id": appointment_id,
        "payment_id": payment_id,
        "trigger_event": payment_confirmed_event,
    }
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

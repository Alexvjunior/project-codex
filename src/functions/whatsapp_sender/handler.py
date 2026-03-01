import json
import urllib.error
import urllib.request

from shared.config import OUTBOX_TABLE, OUTBOUND_QUEUE_URL, validate_runtime_env
from shared.logging_utils import log_json, resolve_correlation_id
from shared.outbox import (
    get_outbox_item,
    get_retry_limit,
    mark_outbox_failed,
    mark_outbox_retry,
    mark_outbox_sent,
    parse_outbox_messages,
    requeue_outbox_event,
)
from shared.secrets import load_service_secrets


def _send_to_whatsapp(destination: str, messages, whatsapp_secret):
    access_token = str(whatsapp_secret.get("WHATSAPP_ACCESS_TOKEN", ""))
    phone_number_id = str(whatsapp_secret.get("WHATSAPP_PHONE_NUMBER_ID", ""))
    api_version = str(whatsapp_secret.get("WHATSAPP_API_VERSION", "v21.0"))

    # Fallback for local environments without external credentials.
    if not access_token or not phone_number_id:
        return {"mode": "simulated", "sent": len(messages)}

    endpoint = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    sent = 0
    for message in messages:
        msg_type = message.get("type", "text")
        payload = {
            "messaging_product": "whatsapp",
            "to": destination,
            "type": msg_type,
        }
        if msg_type == "text":
            payload["text"] = {"preview_url": False, "body": str(message.get("text", ""))}
        else:
            payload[msg_type] = message.get(msg_type, {})

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Unexpected WhatsApp API status: {response.status}")
        sent += 1
    return {"mode": "api", "sent": sent}


def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "whatsapp_sender.started", correlation_id)
    validate_runtime_env()
    secrets = load_service_secrets()
    whatsapp_secret = secrets.get("whatsapp", {})

    sent = 0
    retried = 0
    failed = 0
    skipped = 0
    records = event.get("Records", [])
    for record in records:
        envelope = json.loads(record["body"])
        payload = envelope.get("payload") or {}
        outbox_id = str(payload.get("outbox_id", ""))
        attempt = int(payload.get("attempt", 0))

        if not outbox_id:
            log_json("WARN", "whatsapp_sender.missing_outbox_id", correlation_id)
            skipped += 1
            continue

        item = get_outbox_item(OUTBOX_TABLE, outbox_id)
        if not item:
            log_json("WARN", "whatsapp_sender.outbox_not_found", correlation_id, outbox_id=outbox_id)
            skipped += 1
            continue
        if str(item.get("status", "")) == "SENT":
            skipped += 1
            continue

        destination = str(payload.get("to") or item.get("destination") or "")
        messages = payload.get("messages") or parse_outbox_messages(item)
        if not destination or not messages:
            mark_outbox_failed(OUTBOX_TABLE, outbox_id, attempt, "Missing destination or messages")
            failed += 1
            continue

        try:
            _send_to_whatsapp(destination, messages, whatsapp_secret)
            mark_outbox_sent(OUTBOX_TABLE, outbox_id)
            sent += 1
        except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            retry_limit = get_retry_limit()
            next_attempt = attempt + 1
            error_message = str(exc)
            if next_attempt <= retry_limit:
                mark_outbox_retry(OUTBOX_TABLE, outbox_id, next_attempt, error_message)
                requeue_outbox_event(OUTBOUND_QUEUE_URL, envelope, next_attempt)
                retried += 1
            else:
                mark_outbox_failed(OUTBOX_TABLE, outbox_id, next_attempt, error_message)
                failed += 1

    log_json(
        "INFO",
        "whatsapp_sender.completed",
        correlation_id,
        processed=len(records),
        sent=sent,
        retried=retried,
        failed=failed,
        skipped=skipped,
    )
    return {"processed": len(records), "sent": sent, "retried": retried, "failed": failed, "skipped": skipped}

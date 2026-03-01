import json

from shared.config import validate_runtime_env
from shared.logging_utils import log_json, resolve_correlation_id
from shared.secrets import load_service_secrets


def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "whatsapp_sender.started", correlation_id)
    validate_runtime_env()
    load_service_secrets()

    sent = 0
    records = event.get("Records", [])
    for record in records:
        _payload = json.loads(record["body"])
        # Placeholder for WhatsApp Cloud API call.
        sent += 1
    log_json("INFO", "whatsapp_sender.completed", correlation_id, processed=len(records), sent=sent)
    return {"processed": len(records), "sent": sent}

import json

from shared.config import validate_runtime_env
from shared.secrets import load_service_secrets


def lambda_handler(event, _context):
    validate_runtime_env()
    load_service_secrets()

    sent = 0
    records = event.get("Records", [])
    for record in records:
        _payload = json.loads(record["body"])
        # Placeholder for WhatsApp Cloud API call.
        sent += 1
    return {"processed": len(records), "sent": sent}

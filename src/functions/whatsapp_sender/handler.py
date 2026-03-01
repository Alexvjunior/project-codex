import json

from shared.config import validate_runtime_env


def lambda_handler(event, _context):
    validate_runtime_env()

    sent = 0
    records = event.get("Records", [])
    for record in records:
        _payload = json.loads(record["body"])
        # Placeholder for WhatsApp Cloud API call.
        sent += 1
    return {"processed": len(records), "sent": sent}

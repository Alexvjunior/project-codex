import json


def lambda_handler(event, _context):
    sent = 0
    records = event.get("Records", [])
    for record in records:
        _payload = json.loads(record["body"])
        # Placeholder for WhatsApp Cloud API call.
        sent += 1
    return {"processed": len(records), "sent": sent}

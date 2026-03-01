import json
import os
import uuid

import boto3

from shared.config import validate_runtime_env
from shared.secrets import load_service_secrets


sqs = boto3.client("sqs")

TURN_QUEUE_URL = os.getenv("TURN_QUEUE_URL", "")


def lambda_handler(event, _context):
    validate_runtime_env()
    load_service_secrets()

    records = event.get("Records", [])
    if not records:
        return {"processed": 0}

    grouped = {}
    for record in records:
        payload = json.loads(record["body"])
        session_id = payload.get("session_id", "unknown_session")
        grouped.setdefault(session_id, []).append(payload)

    for session_id, items in grouped.items():
        turn = {
            "event_type": "conversation.turn.ready.v1",
            "session_id": session_id,
            "turn_id": str(uuid.uuid4()),
            "messages": items,
        }
        sqs.send_message(
            QueueUrl=TURN_QUEUE_URL,
            MessageBody=json.dumps(turn, ensure_ascii=True),
            MessageGroupId=session_id,
            MessageDeduplicationId=f"{session_id}:{turn['turn_id']}",
        )

    return {"processed": len(records), "sessions": len(grouped)}

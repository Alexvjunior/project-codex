import json
import os
import uuid

import boto3

from shared.config import validate_runtime_env


sqs = boto3.client("sqs")
OUTBOUND_QUEUE_URL = os.getenv("OUTBOUND_QUEUE_URL", "")


def lambda_handler(event, _context):
    validate_runtime_env()

    records = event.get("Records", [])
    emitted = 0

    for record in records:
        turn = json.loads(record["body"])
        session_id = turn.get("session_id", "unknown_session")

        # Placeholder deterministic response until LangGraph is integrated.
        outbound = {
            "event_type": "whatsapp.message.send.requested.v1",
            "session_id": session_id,
            "message_id": str(uuid.uuid4()),
            "payload": {
                "type": "text",
                "text": "Recebi sua mensagem e vou te ajudar com o agendamento.",
            },
        }
        sqs.send_message(
            QueueUrl=OUTBOUND_QUEUE_URL,
            MessageBody=json.dumps(outbound, ensure_ascii=True),
            MessageGroupId=session_id,
            MessageDeduplicationId=f"{session_id}:{outbound['message_id']}",
        )
        emitted += 1

    return {"processed": len(records), "emitted": emitted}

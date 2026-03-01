import json
import os
import uuid

import boto3

from shared.config import validate_runtime_env
from shared.logging_utils import log_json, resolve_correlation_id
from shared.secrets import load_service_secrets


sqs = boto3.client("sqs")
OUTBOUND_QUEUE_URL = os.getenv("OUTBOUND_QUEUE_URL", "")


def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "conversation_orchestrator.started", correlation_id)
    validate_runtime_env()
    load_service_secrets()

    records = event.get("Records", [])
    emitted = 0

    for record in records:
        turn = json.loads(record["body"])
        session_id = turn.get("session_id", "unknown_session")
        turn_correlation = turn.get("correlation_id", correlation_id)

        # Placeholder deterministic response until LangGraph is integrated.
        outbound = {
            "event_id": str(uuid.uuid4()),
            "event_type": "whatsapp.message.send.requested.v1",
            "event_version": 1,
            "correlation_id": turn_correlation,
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

    log_json(
        "INFO",
        "conversation_orchestrator.completed",
        correlation_id,
        processed=len(records),
        emitted=emitted,
    )
    return {"processed": len(records), "emitted": emitted}

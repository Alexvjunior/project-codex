import json
import os
import uuid

import boto3

from shared.config import validate_runtime_env
from shared.logging_utils import log_json, resolve_correlation_id
from shared.secrets import load_service_secrets


sqs = boto3.client("sqs")

TURN_QUEUE_URL = os.getenv("TURN_QUEUE_URL", "")


def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "message_aggregator.started", correlation_id)
    validate_runtime_env()
    load_service_secrets()

    records = event.get("Records", [])
    if not records:
        log_json("INFO", "message_aggregator.no_records", correlation_id)
        return {"processed": 0}

    grouped = {}
    for record in records:
        payload = json.loads(record["body"])
        if "correlation_id" not in payload:
            payload["correlation_id"] = correlation_id
        session_id = payload.get("session_id", "unknown_session")
        grouped.setdefault(session_id, []).append(payload)

    for session_id, items in grouped.items():
        turn = {
            "event_id": str(uuid.uuid4()),
            "event_type": "conversation.turn.ready.v1",
            "event_version": 1,
            "correlation_id": correlation_id,
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

    log_json(
        "INFO",
        "message_aggregator.completed",
        correlation_id,
        processed=len(records),
        sessions=len(grouped),
    )
    return {"processed": len(records), "sessions": len(grouped)}

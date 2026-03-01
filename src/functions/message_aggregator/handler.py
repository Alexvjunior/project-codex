import hashlib
import json
import uuid

import boto3

from shared import config
from shared.events import build_event
from shared.config import validate_runtime_env
from shared.logging_utils import log_json, resolve_correlation_id


sqs = boto3.client("sqs")

def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "message_aggregator.started", correlation_id)
    validate_runtime_env()

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
        sorted_items = sorted(
            items,
            key=lambda i: ((i.get("payload") or {}).get("received_at", ""), i.get("event_id", "")),
        )
        dedupe_base = "|".join(str(i.get("event_id", "")) for i in sorted_items)
        turn_hash = hashlib.sha256(f"{session_id}|{dedupe_base}".encode("utf-8")).hexdigest()
        turn_id = str(uuid.UUID(turn_hash[:32]))
        turn_payload = {
            "turn_id": turn_id,
            "messages": [i.get("payload", {}) for i in sorted_items],
            "window_seconds": config.AGGREGATION_WINDOW_SECONDS,
        }
        turn_event = build_event(
            event_type="conversation.turn.ready.v1",
            session_id=session_id,
            correlation_id=correlation_id,
            idempotency_key=f"turn:{session_id}:{turn_id}",
            payload=turn_payload,
        )
        sqs.send_message(
            QueueUrl=config.TURN_QUEUE_URL,
            MessageBody=json.dumps(turn_event, ensure_ascii=True),
            MessageGroupId=session_id,
            MessageDeduplicationId=turn_event["idempotency_key"],
        )

    log_json(
        "INFO",
        "message_aggregator.completed",
        correlation_id,
        processed=len(records),
        sessions=len(grouped),
    )
    return {"processed": len(records), "sessions": len(grouped)}

import json
import os
import uuid
from typing import Any, Dict, List, Optional

import boto3

from shared.events import build_event
from shared.utils import utc_now_iso


_dynamodb = boto3.resource("dynamodb")
_sqs = boto3.client("sqs")


def _outbox_table(table_name: str):
    return _dynamodb.Table(table_name)


def create_outbox_item(
    table_name: str,
    session_id: str,
    correlation_id: str,
    destination: str,
    messages: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> str:
    outbox_id = str(uuid.uuid4())
    now = utc_now_iso()
    _outbox_table(table_name).put_item(
        Item={
            "outbox_id": outbox_id,
            "session_id": session_id,
            "status": "PENDING",
            "attempt_count": 0,
            "destination": destination,
            "messages_json": json.dumps(messages, ensure_ascii=True),
            "context_json": json.dumps(context or {}, ensure_ascii=True),
            "correlation_id": correlation_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    return outbox_id


def enqueue_outbox_event(
    queue_url: str,
    session_id: str,
    correlation_id: str,
    outbox_id: str,
    destination: str,
    messages: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    attempt: int = 0,
) -> Dict[str, Any]:
    idempotency_key = f"outbox:{outbox_id}:{attempt}"
    envelope = build_event(
        event_type="whatsapp.message.send.requested.v1",
        session_id=session_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload={
            "outbox_id": outbox_id,
            "to": destination,
            "messages": messages,
            "context": context or {},
            "attempt": attempt,
        },
    )
    _sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(envelope, ensure_ascii=True),
        MessageGroupId=session_id,
        MessageDeduplicationId=idempotency_key,
    )
    return envelope


def get_outbox_item(table_name: str, outbox_id: str) -> Optional[Dict[str, Any]]:
    response = _outbox_table(table_name).get_item(Key={"outbox_id": outbox_id})
    return response.get("Item")


def mark_outbox_sent(table_name: str, outbox_id: str) -> None:
    _outbox_table(table_name).update_item(
        Key={"outbox_id": outbox_id},
        UpdateExpression="SET #s = :s, sent_at = :t, updated_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "SENT", ":t": utc_now_iso()},
    )


def mark_outbox_retry(table_name: str, outbox_id: str, attempt_count: int, error: str) -> None:
    _outbox_table(table_name).update_item(
        Key={"outbox_id": outbox_id},
        UpdateExpression="SET #s = :s, attempt_count = :a, last_error = :e, updated_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "RETRY_PENDING",
            ":a": attempt_count,
            ":e": error[:1000],
            ":t": utc_now_iso(),
        },
    )


def mark_outbox_failed(table_name: str, outbox_id: str, attempt_count: int, error: str) -> None:
    _outbox_table(table_name).update_item(
        Key={"outbox_id": outbox_id},
        UpdateExpression="SET #s = :s, attempt_count = :a, last_error = :e, updated_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "FAILED",
            ":a": attempt_count,
            ":e": error[:1000],
            ":t": utc_now_iso(),
        },
    )


def requeue_outbox_event(
    queue_url: str,
    event_envelope: Dict[str, Any],
    attempt: int,
) -> None:
    payload = event_envelope.get("payload") or {}
    payload["attempt"] = attempt
    event_envelope["payload"] = payload
    event_envelope["idempotency_key"] = f"outbox:{payload.get('outbox_id', 'unknown')}:{attempt}"
    delay_seconds = min(2 ** attempt, 900)
    _sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(event_envelope, ensure_ascii=True),
        MessageGroupId=event_envelope.get("session_id", "unknown_session"),
        MessageDeduplicationId=event_envelope["idempotency_key"],
        DelaySeconds=delay_seconds,
    )


def session_phone(session_id: str) -> str:
    if ":" in session_id:
        return session_id.split(":", 1)[1]
    return session_id


def parse_outbox_messages(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    return json.loads(item.get("messages_json", "[]"))


def parse_outbox_context(item: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(item.get("context_json", "{}"))


def get_retry_limit() -> int:
    try:
        return int(os.getenv("OUTBOX_MAX_RETRIES", "3"))
    except Exception:
        return 3

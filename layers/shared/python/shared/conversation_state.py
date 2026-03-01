import json
from typing import Any, Dict

import boto3

from shared.utils import utc_now_iso


_dynamodb = boto3.resource("dynamodb")


DEFAULT_STATE = {
    "state": "ACTIVE",
    "reschedule_count": 0,
    "handoff_until": "",
    "payment_pending_since": "",
    "appointment_id": "",
    "updated_at": "",
}


def _table(table_name: str):
    return _dynamodb.Table(table_name)


def get_state(table_name: str, session_id: str) -> Dict[str, Any]:
    response = _table(table_name).get_item(Key={"session_id": session_id})
    item = response.get("Item") or {}
    raw = item.get("state_json")
    if not raw:
        return DEFAULT_STATE.copy()
    try:
        parsed = json.loads(raw)
        merged = DEFAULT_STATE.copy()
        merged.update(parsed)
        return merged
    except Exception:
        return DEFAULT_STATE.copy()


def put_state(table_name: str, session_id: str, state: Dict[str, Any], correlation_id: str) -> None:
    payload = DEFAULT_STATE.copy()
    payload.update(state)
    payload["updated_at"] = utc_now_iso()
    _table(table_name).put_item(
        Item={
            "session_id": session_id,
            "state_json": json.dumps(payload, ensure_ascii=True),
            "correlation_id": correlation_id,
            "updated_at": payload["updated_at"],
        }
    )

import uuid
from typing import Any, Dict, Optional

from shared import config
from shared.utils import utc_now_iso


def build_event(
    event_type: str,
    session_id: str,
    correlation_id: str,
    idempotency_key: str,
    payload: Dict[str, Any],
    *,
    causation_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": 1,
        "occurred_at": utc_now_iso(),
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "tenant_id": tenant_id or config.SERVICE_NAME,
        "session_id": session_id,
        "idempotency_key": idempotency_key,
        "payload": payload,
    }

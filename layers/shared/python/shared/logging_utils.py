import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _header_get(headers: Optional[Dict[str, Any]], key: str) -> str:
    if not headers:
        return ""
    key_lower = key.lower()
    for k, v in headers.items():
        if str(k).lower() == key_lower:
            return str(v)
    return ""


def resolve_correlation_id(event: Optional[Dict[str, Any]] = None, context: Any = None) -> str:
    if isinstance(event, dict):
        from_headers = _header_get(event.get("headers"), "x-correlation-id")
        if from_headers:
            return from_headers

        event_correlation = event.get("correlation_id")
        if event_correlation:
            return str(event_correlation)

        request_ctx = event.get("requestContext") or {}
        request_id = request_ctx.get("requestId")
        if request_id:
            return str(request_id)

        records = event.get("Records") or []
        if records:
            try:
                body = json.loads(records[0].get("body", "{}"))
                record_correlation = body.get("correlation_id")
                if record_correlation:
                    return str(record_correlation)
            except Exception:
                pass

    aws_request_id = getattr(context, "aws_request_id", "")
    if aws_request_id:
        return str(aws_request_id)
    return str(uuid.uuid4())


def log_json(
    level: str,
    message: str,
    correlation_id: str,
    **fields: Any,
) -> None:
    payload = {
        "timestamp": _utc_now_iso(),
        "level": level.upper(),
        "message": message,
        "correlation_id": correlation_id,
        "service": os.getenv("SERVICE_NAME", ""),
        "stage": os.getenv("STAGE", ""),
        "function_name": os.getenv("AWS_LAMBDA_FUNCTION_NAME", ""),
    }
    payload.update(fields)
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))


def http_response(status_code: int, body: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "content-type": "application/json",
            "x-correlation-id": correlation_id,
        },
        "body": json.dumps(body, ensure_ascii=True),
    }

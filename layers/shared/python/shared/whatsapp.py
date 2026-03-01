import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, List

from shared import config


def header_get(headers: Dict[str, Any], key: str) -> str:
    if not headers:
        return ""
    target = key.lower()
    for k, v in headers.items():
        if str(k).lower() == target:
            return str(v)
    return ""


def verify_meta_signature(app_secret: str, raw_body: str, signature_header: str) -> bool:
    if not app_secret or not raw_body or not signature_header:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def verify_webhook_challenge(params: Dict[str, Any], expected_verify_token: str) -> Dict[str, Any]:
    mode = str(params.get("hub.mode", ""))
    verify_token = str(params.get("hub.verify_token", ""))
    challenge = str(params.get("hub.challenge", ""))
    if mode == "subscribe" and verify_token and verify_token == expected_verify_token:
        return {"ok": True, "challenge": challenge}
    return {"ok": False, "challenge": ""}


def _to_iso_timestamp(unix_ts: str) -> str:
    try:
        return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _extract_text(message: Dict[str, Any]) -> str:
    msg_type = message.get("type", "unknown")
    if msg_type == "text":
        return str((message.get("text") or {}).get("body", ""))
    if msg_type == "button":
        return str((message.get("button") or {}).get("text", ""))
    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        interactive_type = interactive.get("type")
        if interactive_type == "button_reply":
            return str((interactive.get("button_reply") or {}).get("title", ""))
        if interactive_type == "list_reply":
            return str((interactive.get("list_reply") or {}).get("title", ""))
    return ""


def normalize_messages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    entries = payload.get("entry") or []
    for entry in entries:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            to_number = str(metadata.get("display_phone_number") or metadata.get("phone_number_id") or "")
            for message in value.get("messages") or []:
                from_number = str(message.get("from", ""))
                channel_message_id = str(message.get("id", ""))
                raw_type = str(message.get("type", "unknown"))
                normalized.append(
                    {
                        "channel_message_id": channel_message_id,
                        "from": from_number,
                        "to": to_number,
                        "is_echo": False,
                        "text": _extract_text(message),
                        "received_at": _to_iso_timestamp(str(message.get("timestamp", "0"))),
                        "raw_type": raw_type,
                        "raw_message": message,
                    }
                )
    return normalized


def build_session_id(patient_phone: str) -> str:
    return f"{config.SERVICE_NAME}:{patient_phone}"

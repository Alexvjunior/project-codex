import json
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))

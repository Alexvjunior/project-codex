import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError


_dynamodb = boto3.client("dynamodb")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _slot_to_iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _deterministic_ids(session_id: str, slot_start: str) -> Dict[str, str]:
    digest = hashlib.sha256(f"{session_id}|{slot_start}".encode("utf-8")).hexdigest()
    return {
        "appointment_id": f"apt_{digest[:16]}",
        "calendar_event_id": f"mock_evt_{digest[16:24]}",
    }


def calendar_search(days: int = 7, slots_per_day: int = 3) -> List[Dict]:
    # MVP mock strategy; can be replaced with real Google Calendar integration later.
    base_hour = 14
    slots = []
    now = _now_utc()
    for d in range(1, days + 1):
        day = now + timedelta(days=d)
        for i in range(slots_per_day):
            start = day.replace(hour=base_hour + i * 2, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=60)
            slots.append({"slot_start": _slot_to_iso(start), "slot_end": _slot_to_iso(end)})
    return slots


def calendar_book(
    appointments_table: str,
    idempotency_table: str,
    session_id: str,
    tenant_id: str,
    patient_name: str,
    patient_whatsapp: str,
    slot_start: str,
    slot_end: str,
) -> Dict:
    ids = _deterministic_ids(session_id, slot_start)
    appointment_id = ids["appointment_id"]
    calendar_event_id = ids["calendar_event_id"]
    idempotency_key = f"calendar_book:{session_id}:{slot_start}"
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        _dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": idempotency_table,
                        "Item": {
                            "idempotency_key": {"S": idempotency_key},
                            "expires_at": {"N": str(int(time.time()) + 7 * 24 * 3600)},
                        },
                        "ConditionExpression": "attribute_not_exists(idempotency_key)",
                    }
                },
                {
                    "Put": {
                        "TableName": appointments_table,
                        "Item": {
                            "appointment_id": {"S": appointment_id},
                            "tenant_id": {"S": tenant_id},
                            "slot_start": {"S": slot_start},
                            "slot_end": {"S": slot_end},
                            "status": {"S": "PAYMENT_PENDING"},
                            "payment_status": {"S": "pending"},
                            "patient_name": {"S": patient_name},
                            "patient_whatsapp": {"S": patient_whatsapp},
                            "calendar_event_id": {"S": calendar_event_id},
                            "created_at": {"S": now_iso},
                            "updated_at": {"S": now_iso},
                        },
                        "ConditionExpression": "attribute_not_exists(appointment_id)",
                    }
                },
            ]
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in (
            "ConditionalCheckFailedException",
            "TransactionCanceledException",
        ):
            return {
                "duplicate": True,
                "appointment_id": appointment_id,
                "calendar_event_id": calendar_event_id,
                "slot_start": slot_start,
                "slot_end": slot_end,
            }
        raise

    return {
        "duplicate": False,
        "appointment_id": appointment_id,
        "calendar_event_id": calendar_event_id,
        "slot_start": slot_start,
        "slot_end": slot_end,
    }


def calendar_release_slot(appointments_table: str, appointment_id: str) -> None:
    try:
        _dynamodb.update_item(
            TableName=appointments_table,
            Key={"appointment_id": {"S": appointment_id}},
            UpdateExpression="SET #s = :s, payment_status = :ps, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": {"S": "EXPIRED"},
                ":ps": {"S": "expired"},
                ":u": {"S": datetime.now(timezone.utc).isoformat()},
            },
            ConditionExpression="attribute_exists(appointment_id)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return
        raise

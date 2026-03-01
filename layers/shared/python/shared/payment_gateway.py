import uuid
from datetime import datetime, timezone
from typing import Dict

import boto3
from botocore.exceptions import ClientError


_dynamodb = boto3.client("dynamodb")


def _to_str(item: Dict, key: str, default: str = "") -> str:
    value = item.get(key) or {}
    if "S" in value:
        return str(value.get("S"))
    if "N" in value:
        return str(value.get("N"))
    return default


def _find_existing_payment(payments_table: str, appointment_id: str) -> Dict:
    try:
        response = _dynamodb.query(
            TableName=payments_table,
            IndexName="by_appointment",
            KeyConditionExpression="appointment_id = :a",
            ExpressionAttributeValues={":a": {"S": appointment_id}},
            Limit=20,
        )
    except ClientError:
        return {}

    items = response.get("Items") or []
    if not items:
        return {}

    # Prefer a paid payment first; otherwise return a pending one.
    selected = None
    for status in ("paid", "pending"):
        for item in items:
            if _to_str(item, "status") == status:
                selected = item
                break
        if selected:
            break
    if not selected:
        selected = items[0]

    gateway_payment_id = _to_str(selected, "gateway_payment_id")
    checkout_url = _to_str(selected, "checkout_url")
    if not checkout_url and gateway_payment_id:
        checkout_url = f"https://pay.mock.local/checkout/{gateway_payment_id}"
    return {
        "payment_id": _to_str(selected, "payment_id"),
        "gateway_payment_id": gateway_payment_id,
        "checkout_url": checkout_url,
        "status": _to_str(selected, "status", "pending"),
        "reused": True,
    }


def payment_generate(
    payments_table: str,
    appointment_id: str,
    amount_brl: float,
    currency: str = "BRL",
) -> Dict:
    existing = _find_existing_payment(payments_table, appointment_id)
    if existing:
        return existing

    payment_id = f"pay_{uuid.uuid4().hex[:10]}"
    gateway_payment_id = f"mock_pg_{uuid.uuid4().hex[:12]}"
    link = f"https://pay.mock.local/checkout/{gateway_payment_id}"

    _dynamodb.put_item(
        TableName=payments_table,
        Item={
            "payment_id": {"S": payment_id},
            "appointment_id": {"S": appointment_id},
            "status": {"S": "pending"},
            "gateway_payment_id": {"S": gateway_payment_id},
            "checkout_url": {"S": link},
            "amount": {"N": str(amount_brl)},
            "currency": {"S": currency},
            "created_at": {"S": datetime.now(timezone.utc).isoformat()},
        },
    )
    return {
        "payment_id": payment_id,
        "gateway_payment_id": gateway_payment_id,
        "checkout_url": link,
        "status": "pending",
        "reused": False,
    }

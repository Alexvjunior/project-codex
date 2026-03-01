import json
import time
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError


_dynamodb = boto3.client("dynamodb")


def put_inbound_message_if_new(
    table_name: str,
    session_id: str,
    channel_message_id: str,
    raw_payload: Dict[str, Any],
    normalized_payload: Dict[str, Any],
    correlation_id: str,
    ttl_days: int = 7,
) -> bool:
    expires_at = int(time.time()) + ttl_days * 24 * 3600
    try:
        _dynamodb.put_item(
            TableName=table_name,
            Item={
                "session_id": {"S": session_id},
                "message_id": {"S": channel_message_id},
                "from": {"S": "PATIENT"},
                "direction": {"S": "IN"},
                "body": {"S": str(normalized_payload.get("text", ""))},
                "raw_type": {"S": str(normalized_payload.get("raw_type", "unknown"))},
                "raw_json": {"S": json.dumps(raw_payload, ensure_ascii=True)},
                "normalized_json": {"S": json.dumps(normalized_payload, ensure_ascii=True)},
                "correlation_id": {"S": correlation_id},
                "received_at": {"S": str(normalized_payload.get("received_at", ""))},
                "expires_at": {"N": str(expires_at)},
            },
            ConditionExpression="attribute_not_exists(message_id)",
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise

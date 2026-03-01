import json
import os
import uuid

import boto3
from botocore.exceptions import ClientError

from shared.config import validate_runtime_env
from shared.secrets import load_service_secrets


sqs = boto3.client("sqs")
dynamodb = boto3.client("dynamodb")

INBOUND_QUEUE_URL = os.getenv("INBOUND_QUEUE_URL", "")
IDEMPOTENCY_TABLE = os.getenv("IDEMPOTENCY_TABLE", "")


def lambda_handler(event, _context):
    validate_runtime_env()
    load_service_secrets()

    body_raw = event.get("body") or "{}"
    body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw

    channel_message_id = body.get("message_id") or str(uuid.uuid4())
    session_id = body.get("session_id", "unknown_session")
    idempotency_key = f"whatsapp:{channel_message_id}"

    # Conditional write to avoid enqueue duplicates.
    try:
        dynamodb.put_item(
            TableName=IDEMPOTENCY_TABLE,
            Item={
                "idempotency_key": {"S": idempotency_key},
                "expires_at": {"N": str(int(__import__("time").time()) + 86400)},
            },
            ConditionExpression="attribute_not_exists(idempotency_key)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return {
                "statusCode": 200,
                "headers": {"content-type": "application/json"},
                "body": json.dumps({"ok": True, "duplicate": True}, ensure_ascii=True),
            }
        raise

    sqs.send_message(
        QueueUrl=INBOUND_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "event_type": "whatsapp.message.received.v1",
                "session_id": session_id,
                "payload": body,
            },
            ensure_ascii=True,
        ),
        MessageGroupId=session_id,
        MessageDeduplicationId=idempotency_key,
    )

    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"ok": True}, ensure_ascii=True),
    }

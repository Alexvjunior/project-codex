import json
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError


dynamodb = boto3.client("dynamodb")
sqs = boto3.client("sqs")

PAYMENTS_TABLE = os.getenv("PAYMENTS_TABLE", "")
APPOINTMENTS_TABLE = os.getenv("APPOINTMENTS_TABLE", "")
IDEMPOTENCY_TABLE = os.getenv("IDEMPOTENCY_TABLE", "")
OUTBOUND_QUEUE_URL = os.getenv("OUTBOUND_QUEUE_URL", "")


def lambda_handler(event, _context):
    body_raw = event.get("body") or "{}"
    body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw

    gateway_event_id = body.get("gateway_event_id", str(uuid.uuid4()))
    appointment_id = body.get("appointment_id", "unknown_appointment")
    payment_id = body.get("payment_id", f"pay_{uuid.uuid4()}")

    try:
        dynamodb.put_item(
            TableName=IDEMPOTENCY_TABLE,
            Item={
                "idempotency_key": {"S": f"payment:{gateway_event_id}"},
                "expires_at": {"N": str(int(time.time()) + 30 * 24 * 3600)},
            },
            ConditionExpression="attribute_not_exists(idempotency_key)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return {"statusCode": 200, "body": json.dumps({"ok": True, "duplicate": True})}
        raise

    dynamodb.put_item(
        TableName=PAYMENTS_TABLE,
        Item={
            "payment_id": {"S": payment_id},
            "appointment_id": {"S": appointment_id},
            "status": {"S": "approved"},
            "created_at": {"S": str(int(time.time()))},
        },
    )

    dynamodb.update_item(
        TableName=APPOINTMENTS_TABLE,
        Key={"appointment_id": {"S": appointment_id}},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": {"S": "CONFIRMED"}},
    )

    sqs.send_message(
        QueueUrl=OUTBOUND_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "event_type": "whatsapp.message.send.requested.v1",
                "session_id": body.get("session_id", "unknown_session"),
                "payload": {
                    "type": "text",
                    "text": "Pagamento aprovado! Sua consulta foi confirmada.",
                },
            },
            ensure_ascii=True,
        ),
        MessageGroupId=body.get("session_id", "unknown_session"),
        MessageDeduplicationId=f"payment-confirmed:{gateway_event_id}",
    )

    return {"statusCode": 200, "body": json.dumps({"ok": True})}

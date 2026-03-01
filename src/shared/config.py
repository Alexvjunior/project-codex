import os


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


STAGE = get_env("STAGE", "dev")
SERVICE_NAME = get_env("SERVICE_NAME", "secretaria-ia")

CONVERSATIONS_TABLE = get_env("CONVERSATIONS_TABLE")
MESSAGES_TABLE = get_env("MESSAGES_TABLE")
APPOINTMENTS_TABLE = get_env("APPOINTMENTS_TABLE")
PAYMENTS_TABLE = get_env("PAYMENTS_TABLE")
OUTBOX_TABLE = get_env("OUTBOX_TABLE")
IDEMPOTENCY_TABLE = get_env("IDEMPOTENCY_TABLE")

INBOUND_QUEUE_URL = get_env("INBOUND_QUEUE_URL")
TURN_QUEUE_URL = get_env("TURN_QUEUE_URL")
OUTBOUND_QUEUE_URL = get_env("OUTBOUND_QUEUE_URL")

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
WHATSAPP_SECRET_ID = get_env("WHATSAPP_SECRET_ID")
PAYMENT_SECRET_ID = get_env("PAYMENT_SECRET_ID")
LLM_SECRET_ID = get_env("LLM_SECRET_ID")

REQUIRED_ENV_VARS = [
    "STAGE",
    "SERVICE_NAME",
    "CONVERSATIONS_TABLE",
    "MESSAGES_TABLE",
    "APPOINTMENTS_TABLE",
    "PAYMENTS_TABLE",
    "OUTBOX_TABLE",
    "IDEMPOTENCY_TABLE",
]


def validate_runtime_env() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not get_env(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

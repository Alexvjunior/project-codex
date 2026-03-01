import json
from functools import lru_cache
from typing import Any, Dict

import boto3

from shared import config


_client = boto3.client("secretsmanager")


@lru_cache(maxsize=32)
def get_secret(secret_id: str) -> Dict[str, Any]:
    response = _client.get_secret_value(SecretId=secret_id)
    payload = response.get("SecretString", "{}")
    return json.loads(payload)


def load_service_secrets() -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}

    if config.WHATSAPP_SECRET_ID:
        result["whatsapp"] = get_secret(config.WHATSAPP_SECRET_ID)
    if config.PAYMENT_SECRET_ID:
        result["payment"] = get_secret(config.PAYMENT_SECRET_ID)
    if config.LLM_SECRET_ID:
        result["llm"] = get_secret(config.LLM_SECRET_ID)

    return result

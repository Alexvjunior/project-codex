import json

from shared.config import OUTBOX_TABLE, OUTBOUND_QUEUE_URL, validate_runtime_env
from shared.logging_utils import log_json, resolve_correlation_id
from shared.outbox import create_outbox_item, enqueue_outbox_event, session_phone
from shared.secrets import load_service_secrets


def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "conversation_orchestrator.started", correlation_id)
    validate_runtime_env()
    load_service_secrets()

    records = event.get("Records", [])
    emitted = 0

    for record in records:
        turn = json.loads(record["body"])
        session_id = turn.get("session_id", "unknown_session")
        turn_correlation = turn.get("correlation_id", correlation_id)
        destination = session_phone(session_id)

        messages = [
            {
                "type": "text",
                "text": "Recebi sua mensagem e vou te ajudar com o agendamento.",
            }
        ]
        context = {"source": "conversation_orchestrator"}
        outbox_id = create_outbox_item(
            table_name=OUTBOX_TABLE,
            session_id=session_id,
            correlation_id=turn_correlation,
            destination=destination,
            messages=messages,
            context=context,
        )
        enqueue_outbox_event(
            queue_url=OUTBOUND_QUEUE_URL,
            session_id=session_id,
            correlation_id=turn_correlation,
            outbox_id=outbox_id,
            destination=destination,
            messages=messages,
            context=context,
        )
        emitted += 1

    log_json(
        "INFO",
        "conversation_orchestrator.completed",
        correlation_id,
        processed=len(records),
        emitted=emitted,
    )
    return {"processed": len(records), "emitted": emitted}

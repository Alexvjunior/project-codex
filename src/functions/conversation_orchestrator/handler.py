import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from shared import config
from shared.calendar_tools import calendar_book, calendar_release_slot, calendar_search
from shared.conversation_state import get_state, put_state
from shared.config import validate_runtime_env
from shared.logging_utils import log_json, resolve_correlation_id
from shared.outbox import create_outbox_item, enqueue_outbox_event, session_phone
from shared.payment_gateway import payment_generate
from shared.rag import rag_retrieve
from shared.secrets import get_llm_api_key, load_service_secrets

from .graph import build_intent_runner


_ddb = boto3.client("dynamodb")
_RAG_BASE_DIR = os.path.join(os.path.dirname(__file__), "data")
_intent_runner = None
_intent_runner_key = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_to_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return _now()


def _latest_text(turn: Dict[str, Any]) -> str:
    payload = turn.get("payload", turn)
    messages = payload.get("messages") or []
    for item in reversed(messages):
        if isinstance(item, dict) and item.get("text"):
            return str(item.get("text"))
    return ""


def _ddb_str(item: Dict[str, Dict[str, str]], key: str, default: str = "") -> str:
    value = item.get(key) or {}
    if "S" in value:
        return str(value["S"])
    if "N" in value:
        return str(value["N"])
    return default


def _transition(correlation_id: str, session_id: str, old_state: str, new_state: str, reason: str) -> None:
    if old_state != new_state:
        log_json(
            "INFO",
            "conversation_orchestrator.transition",
            correlation_id,
            session_id=session_id,
            old_state=old_state,
            new_state=new_state,
            reason=reason,
        )


def _enqueue_response(
    session_id: str,
    correlation_id: str,
    text: str,
    context: Dict[str, Any],
) -> None:
    destination = session_phone(session_id)
    messages = [{"type": "text", "text": text}]
    outbox_id = create_outbox_item(
        table_name=config.OUTBOX_TABLE,
        session_id=session_id,
        correlation_id=correlation_id,
        destination=destination,
        messages=messages,
        context=context,
    )
    enqueue_outbox_event(
        queue_url=config.OUTBOUND_QUEUE_URL,
        session_id=session_id,
        correlation_id=correlation_id,
        outbox_id=outbox_id,
        destination=destination,
        messages=messages,
        context=context,
    )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _set_appointment_status(appointment_id: str, status: str, payment_status: str = "") -> None:
    if not appointment_id:
        return
    update_expression = "SET #s = :s, updated_at = :u"
    names = {"#s": "status"}
    values: Dict[str, Dict[str, str]] = {
        ":s": {"S": status},
        ":u": {"S": _now().isoformat()},
    }
    if payment_status:
        update_expression += ", payment_status = :ps"
        values[":ps"] = {"S": payment_status}
    try:
        _ddb.update_item(
            TableName=config.APPOINTMENTS_TABLE,
            Key={"appointment_id": {"S": appointment_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression="attribute_exists(appointment_id)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return
        raise


def _get_primary_payment(appointment_id: str) -> Dict[str, str]:
    if not appointment_id:
        return {}
    try:
        response = _ddb.query(
            TableName=config.PAYMENTS_TABLE,
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

    selected = None
    for preferred in ("paid", "pending"):
        for item in items:
            if _ddb_str(item, "status") == preferred:
                selected = item
                break
        if selected:
            break
    if not selected:
        selected = items[0]

    return {
        "payment_id": _ddb_str(selected, "payment_id"),
        "status": _ddb_str(selected, "status"),
        "checkout_url": _ddb_str(selected, "checkout_url"),
        "gateway_payment_id": _ddb_str(selected, "gateway_payment_id"),
    }


def _update_payment_status(payment_id: str, status: str) -> None:
    if not payment_id:
        return
    try:
        _ddb.update_item(
            TableName=config.PAYMENTS_TABLE,
            Key={"payment_id": {"S": payment_id}},
            UpdateExpression="SET #s = :s, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": {"S": status}, ":u": {"S": _now().isoformat()}},
            ConditionExpression="attribute_exists(payment_id)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return
        raise


def _checkout_url(payment: Dict[str, str]) -> str:
    url = str(payment.get("checkout_url", ""))
    if url:
        return url
    gateway_payment_id = str(payment.get("gateway_payment_id", ""))
    if gateway_payment_id:
        return f"https://pay.mock.local/checkout/{gateway_payment_id}"
    return ""


def _apply_cancel_policy(appointment_id: str) -> Dict[str, str]:
    if not appointment_id:
        return {
            "appointment_status": "CANCELED",
            "payment_status": "",
            "message": "Cancelamento registrado com sucesso.",
        }

    payment = _get_primary_payment(appointment_id)
    payment_id = payment.get("payment_id", "")
    payment_status = payment.get("status", "")

    if payment_status == "paid":
        _set_appointment_status(appointment_id, "CANCELED_REFUND_PENDING", "refund_pending")
        _update_payment_status(payment_id, "refund_pending")
        return {
            "appointment_status": "CANCELED_REFUND_PENDING",
            "payment_status": "refund_pending",
            "message": "Consulta cancelada. Reembolso solicitado e em processamento.",
        }

    if payment_status == "pending":
        _set_appointment_status(appointment_id, "CANCELED", "canceled")
        _update_payment_status(payment_id, "canceled")
        return {
            "appointment_status": "CANCELED",
            "payment_status": "canceled",
            "message": "Cancelamento registrado com sucesso e pagamento pendente invalido.",
        }

    _set_appointment_status(appointment_id, "CANCELED")
    return {
        "appointment_status": "CANCELED",
        "payment_status": payment_status,
        "message": "Cancelamento registrado com sucesso.",
    }


def _resolve_intent_runner(service_secrets: Dict[str, Dict[str, Any]]):
    global _intent_runner, _intent_runner_key
    api_key = get_llm_api_key(service_secrets)
    if _intent_runner is None or api_key != _intent_runner_key:
        _intent_runner = build_intent_runner(api_key)
        _intent_runner_key = api_key
    return _intent_runner


def lambda_handler(event, _context):
    correlation_id = resolve_correlation_id(event)
    log_json("INFO", "conversation_orchestrator.started", correlation_id)
    validate_runtime_env()
    secrets = load_service_secrets(whatsapp=False, payment=False, llm=bool(config.LLM_SECRET_ID))
    intent_runner = _resolve_intent_runner(secrets)

    records = event.get("Records", [])
    emitted = 0

    for record in records:
        turn_event = json.loads(record["body"])
        turn_payload = turn_event.get("payload", turn_event)
        session_id = turn_event.get("session_id") or turn_payload.get("session_id", "unknown_session")
        turn_correlation = turn_event.get("correlation_id", correlation_id)
        state = get_state(config.CONVERSATIONS_TABLE, session_id)
        old_state = str(state.get("state", "ACTIVE"))
        latest_text = _latest_text(turn_event)
        latest_text_l = latest_text.lower()

        token_estimate = _estimate_tokens(latest_text)
        if token_estimate > config.MAX_TOKENS_PER_TURN:
            log_json(
                "WARN",
                "conversation_orchestrator.token_budget_exceeded",
                turn_correlation,
                session_id=session_id,
                estimated_tokens=token_estimate,
                max_tokens=config.MAX_TOKENS_PER_TURN,
            )
            _enqueue_response(
                session_id,
                turn_correlation,
                "Sua mensagem ficou muito longa para processar de uma vez. Pode enviar em partes menores?",
                {"source": "conversation_orchestrator", "reason": "token_budget"},
            )
            emitted += 1
            continue

        # Release handoff if TTL has expired.
        if state.get("state") == "HANDOFF_HUMAN" and state.get("handoff_until"):
            handoff_until = _iso_to_dt(str(state.get("handoff_until")))
            if handoff_until <= _now():
                old = str(state.get("state", "HANDOFF_HUMAN"))
                state["state"] = "ACTIVE"
                state["handoff_until"] = ""
                _transition(turn_correlation, session_id, old, "ACTIVE", "handoff_ttl_expired")

        # Payment timeout auto-release.
        if state.get("state") == "WAIT_PAYMENT" and state.get("payment_pending_since"):
            pending_since = _iso_to_dt(str(state.get("payment_pending_since")))
            elapsed = (_now() - pending_since).total_seconds() / 60.0
            if elapsed >= config.PAYMENT_TIMEOUT_MINUTES:
                appointment_id = str(state.get("appointment_id", ""))
                if appointment_id:
                    log_json("INFO", "conversation_orchestrator.tool_call", turn_correlation, tool="calendar_release_slot")
                    calendar_release_slot(config.APPOINTMENTS_TABLE, appointment_id)
                    pending_payment = _get_primary_payment(appointment_id)
                    if pending_payment.get("status") == "pending":
                        _update_payment_status(pending_payment.get("payment_id", ""), "expired")
                state["state"] = "ACTIVE"
                state["appointment_id"] = ""
                state["payment_pending_since"] = ""
                _transition(turn_correlation, session_id, old_state, "ACTIVE", "payment_timeout")
                _enqueue_response(
                    session_id,
                    turn_correlation,
                    "Seu pagamento expirou e o horario foi liberado. Posso buscar novos horarios para voce.",
                    {"source": "conversation_orchestrator", "reason": "payment_timeout"},
                )
                put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
                emitted += 1
                continue

        # Intent via LangGraph base (fallback included).
        intent_result = intent_runner({"latest_text": latest_text, "state": state})
        intent = str(intent_result.get("intent", "general"))
        log_json("INFO", "conversation_orchestrator.intent", turn_correlation, session_id=session_id, intent=intent)

        if intent == "handoff_off":
            old = str(state.get("state", "ACTIVE"))
            state["state"] = "HANDOFF_HUMAN"
            state["handoff_until"] = (_now() + timedelta(minutes=config.HANDOFF_TTL_MINUTES)).isoformat()
            _transition(turn_correlation, session_id, old, state["state"], "command_handoff_off")
            _enqueue_response(
                session_id,
                turn_correlation,
                "Perfeito. Vou pausar o atendimento automatico por enquanto. Use /ia on para retomar.",
                {"source": "conversation_orchestrator", "flow": "handoff"},
            )
            put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
            emitted += 1
            continue

        if state.get("state") == "HANDOFF_HUMAN":
            if intent == "handoff_on" or "/ia on" in latest_text_l:
                old = state.get("state", "HANDOFF_HUMAN")
                state["state"] = "ACTIVE"
                state["handoff_until"] = ""
                _transition(turn_correlation, session_id, old, "ACTIVE", "command_handoff_on")
                _enqueue_response(
                    session_id,
                    turn_correlation,
                    "Atendimento automatico retomado. Posso continuar seu agendamento.",
                    {"source": "conversation_orchestrator", "flow": "handoff"},
                )
                put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
                emitted += 1
            else:
                log_json("INFO", "conversation_orchestrator.handoff_active", turn_correlation, session_id=session_id)
            continue

        if intent == "cancel":
            appointment_id = str(state.get("appointment_id", ""))
            policy = _apply_cancel_policy(appointment_id)
            old = str(state.get("state", "ACTIVE"))
            state["state"] = "CANCELED"
            state["appointment_id"] = ""
            state["payment_pending_since"] = ""
            _transition(turn_correlation, session_id, old, state["state"], "cancel_requested")
            _enqueue_response(
                session_id,
                turn_correlation,
                policy["message"] + " Se quiser, posso te ajudar a escolher outro horario.",
                {
                    "source": "conversation_orchestrator",
                    "flow": "cancel",
                    "appointment_status": policy["appointment_status"],
                    "payment_status": policy["payment_status"],
                },
            )
            put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
            emitted += 1
            continue

        if intent in ("schedule", "reschedule"):
            if intent == "reschedule":
                reschedules = int(state.get("reschedule_count", 0))
                if reschedules >= config.MAX_RESCHEDULES:
                    old = str(state.get("state", "ACTIVE"))
                    state["state"] = "HANDOFF_HUMAN"
                    state["handoff_until"] = (_now() + timedelta(minutes=config.HANDOFF_TTL_MINUTES)).isoformat()
                    _transition(turn_correlation, session_id, old, state["state"], "reschedule_limit")
                    _enqueue_response(
                        session_id,
                        turn_correlation,
                        "Voce atingiu o limite de remarcacoes automaticas. Vou encaminhar para atendimento humano.",
                        {"source": "conversation_orchestrator", "flow": "reschedule_limit"},
                    )
                    put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
                    emitted += 1
                    continue

                previous_appointment_id = str(state.get("appointment_id", ""))
                if previous_appointment_id:
                    _set_appointment_status(previous_appointment_id, "RESCHEDULED", "replaced")
                    previous_payment = _get_primary_payment(previous_appointment_id)
                    if previous_payment.get("status") == "pending":
                        _update_payment_status(previous_payment.get("payment_id", ""), "canceled")
                    if previous_payment.get("status") == "paid":
                        _update_payment_status(previous_payment.get("payment_id", ""), "refund_pending")

            log_json("INFO", "conversation_orchestrator.tool_call", turn_correlation, tool="calendar_search")
            slots = calendar_search(days=7, slots_per_day=3)
            selected = slots[0] if slots else {}
            if not selected:
                _enqueue_response(
                    session_id,
                    turn_correlation,
                    "Nao consegui encontrar horarios agora. Pode tentar novamente em alguns minutos?",
                    {"source": "conversation_orchestrator", "flow": intent},
                )
                emitted += 1
                continue

            log_json("INFO", "conversation_orchestrator.tool_call", turn_correlation, tool="calendar_book")
            booking = calendar_book(
                appointments_table=config.APPOINTMENTS_TABLE,
                idempotency_table=config.IDEMPOTENCY_TABLE,
                session_id=session_id,
                tenant_id=config.SERVICE_NAME,
                patient_name="Paciente",
                patient_whatsapp=session_phone(session_id),
                slot_start=str(selected["slot_start"]),
                slot_end=str(selected["slot_end"]),
            )
            appointment_id = str(booking.get("appointment_id", ""))

            log_json("INFO", "conversation_orchestrator.tool_call", turn_correlation, tool="payment_generate")
            payment = payment_generate(
                payments_table=config.PAYMENTS_TABLE,
                appointment_id=appointment_id,
                amount_brl=250.0,
            )

            payment_status = str(payment.get("status", "pending"))
            if payment_status == "paid":
                _set_appointment_status(appointment_id, "CONFIRMED", "paid")
                old = str(state.get("state", "ACTIVE"))
                state["state"] = "ACTIVE"
                state["appointment_id"] = appointment_id
                state["payment_pending_since"] = ""
                _transition(turn_correlation, session_id, old, state["state"], f"{intent}_already_paid")
                _enqueue_response(
                    session_id,
                    turn_correlation,
                    "Seu horario ja esta confirmado. Posso te ajudar com mais alguma coisa?",
                    {
                        "source": "conversation_orchestrator",
                        "flow": intent,
                        "appointment_id": appointment_id,
                        "payment_status": payment_status,
                    },
                )
                put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
                emitted += 1
                continue

            old = str(state.get("state", "ACTIVE"))
            state["state"] = "WAIT_PAYMENT"
            state["appointment_id"] = appointment_id
            state["payment_pending_since"] = _now().isoformat()
            if intent == "reschedule":
                state["reschedule_count"] = int(state.get("reschedule_count", 0)) + 1
            _transition(turn_correlation, session_id, old, state["state"], intent)
            checkout_url = _checkout_url(payment)
            _enqueue_response(
                session_id,
                turn_correlation,
                "Horario reservado! Para confirmar sua consulta, finalize o pagamento neste link: " + checkout_url,
                {
                    "source": "conversation_orchestrator",
                    "flow": intent,
                    "appointment_id": appointment_id,
                    "payment_id": payment.get("payment_id", ""),
                    "booking_duplicate": bool(booking.get("duplicate", False)),
                    "payment_reused": bool(payment.get("reused", False)),
                },
            )
            put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
            emitted += 1
            continue

        rag_docs = rag_retrieve(latest_text, _RAG_BASE_DIR, top_k=3)
        if rag_docs:
            log_json(
                "INFO",
                "conversation_orchestrator.tool_call",
                turn_correlation,
                tool="rag_retriever",
                retrieved=len(rag_docs),
            )
            response_text = (
                "Entendi. Posso te ajudar com agendamento, remarcacao ou cancelamento. "
                "Se quiser, ja posso buscar os proximos horarios."
            )
        else:
            response_text = "Posso te ajudar com seu agendamento. Quer que eu busque horarios disponiveis?"

        _enqueue_response(
            session_id,
            turn_correlation,
            response_text,
            {"source": "conversation_orchestrator", "flow": "general"},
        )
        old = str(state.get("state", "ACTIVE"))
        if old != "ACTIVE":
            state["state"] = "ACTIVE"
            _transition(turn_correlation, session_id, old, "ACTIVE", "general_reply")
        put_state(config.CONVERSATIONS_TABLE, session_id, state, turn_correlation)
        emitted += 1

    log_json(
        "INFO",
        "conversation_orchestrator.completed",
        correlation_id,
        processed=len(records),
        emitted=emitted,
    )
    return {"processed": len(records), "emitted": emitted}

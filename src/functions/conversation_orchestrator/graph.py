import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict


_GEMINI_INTENTS = {"schedule", "reschedule", "cancel", "handoff_off", "handoff_on", "general"}


def _fallback_runner(state: Dict[str, Any]) -> Dict[str, Any]:
    text = (state.get("latest_text") or "").lower()
    if "cancel" in text:
        return {"intent": "cancel"}
    if "remar" in text:
        return {"intent": "reschedule"}
    if "agendar" in text or "consulta" in text or "horario" in text:
        return {"intent": "schedule"}
    if "/ia off" in text:
        return {"intent": "handoff_off"}
    if "/ia on" in text:
        return {"intent": "handoff_on"}
    return {"intent": "general"}


def _extract_text_from_gemini_response(payload: Dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                return str(text)
    return ""


def _normalize_intent(value: str) -> str:
    intent = (value or "").strip().lower()
    if intent in _GEMINI_INTENTS:
        return intent
    return "general"


def _gemini_intent(latest_text: str, api_key: str) -> Dict[str, Any]:
    prompt = (
        "Classifique a intencao do texto abaixo em apenas uma opcao: "
        "schedule, reschedule, cancel, handoff_off, handoff_on, general. "
        "Responda SOMENTE JSON valido no formato {\"intent\":\"...\"}.\n"
        f"texto: {latest_text}"
    )
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 32,
        },
    }
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-flash-latest:generateContent"
    )
    request = urllib.request.Request(
        f"{endpoint}?key={api_key}",
        data=json.dumps(body, ensure_ascii=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw_text = _extract_text_from_gemini_response(payload)
    parsed = json.loads(raw_text)
    return {"intent": _normalize_intent(str(parsed.get("intent", "general")))}


def build_intent_runner(llm_api_key: str = "") -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    # Optional LangGraph runtime. If unavailable, fallback runner is used.
    # If Gemini key exists, intent node attempts model-based classification.
    def _intent_with_optional_llm(state: Dict[str, Any]) -> Dict[str, Any]:
        if llm_api_key:
            try:
                return _gemini_intent(str(state.get("latest_text", "")), llm_api_key)
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, ValueError):
                return _fallback_runner(state)
        return _fallback_runner(state)

    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore

        def _intent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            return _intent_with_optional_llm(state)

        graph = StateGraph(dict)
        graph.add_node("intent", _intent_node)
        graph.add_edge(START, "intent")
        graph.add_edge("intent", END)
        compiled = graph.compile()

        def _run(state: Dict[str, Any]) -> Dict[str, Any]:
            result = compiled.invoke(state)
            if isinstance(result, dict):
                return result
            return _intent_with_optional_llm(state)

        return _run
    except Exception:
        return _intent_with_optional_llm

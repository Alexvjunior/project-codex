from typing import Any, Callable, Dict


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


def build_intent_runner() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    # Optional LangGraph runtime. If unavailable, fallback runner is used.
    try:
        from langgraph.graph import END, START, StateGraph  # type: ignore

        def _intent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            return _fallback_runner(state)

        graph = StateGraph(dict)
        graph.add_node("intent", _intent_node)
        graph.add_edge(START, "intent")
        graph.add_edge("intent", END)
        compiled = graph.compile()

        def _run(state: Dict[str, Any]) -> Dict[str, Any]:
            result = compiled.invoke(state)
            if isinstance(result, dict):
                return result
            return _fallback_runner(state)

        return _run
    except Exception:
        return _fallback_runner

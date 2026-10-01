"""Request router for the Example Showcase extension."""

from __future__ import annotations

from handlers.actions import ACTION_HANDLERS
from handlers.common import as_dict, as_text, fail
from handlers.queries import QUERY_HANDLERS


def _resolve_mode(request_payload: dict) -> str:
    mode = as_text(request_payload.get("mode")).lower()
    if mode:
        return mode
    if isinstance(request_payload.get("query"), dict):
        return "query"
    if isinstance(request_payload.get("action"), dict):
        return "action"
    if as_text(request_payload.get("action")):
        return "action"
    return ""


def handle_request(request_payload: dict) -> dict:
    mode = _resolve_mode(request_payload)
    if mode == "query":
        query = as_dict(request_payload.get("query"))
        query_id = as_text(query.get("query_id") or request_payload.get("query_id"))
        handler = QUERY_HANDLERS.get(query_id)
        if handler is None:
            return fail("invalid_payload", f"unknown_query:{query_id}")
        return handler(query)

    if mode == "action":
        action = as_dict(request_payload.get("action"))
        if not action and as_text(request_payload.get("action")):
            action = {
                "action_id": as_text(request_payload.get("action")),
                "input": {
                    "tool_name": request_payload.get("tool_name"),
                    "arguments": as_dict(request_payload.get("arguments")),
                },
            }
        for key in ("artifacts", "datasets", "runtime_context"):
            if key in request_payload:
                action[key] = request_payload[key]
        action_id = as_text(action.get("action_id") or request_payload.get("action_id"))
        handler = ACTION_HANDLERS.get(action_id)
        if handler is None:
            return fail("invalid_payload", f"unknown_action:{action_id}")
        return handler(action)

    return fail("invalid_payload", f"unsupported_request:{mode}")

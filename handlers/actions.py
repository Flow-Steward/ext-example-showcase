"""Action handlers for the Example Showcase extension."""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib
import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request

from flowsteward_extension_sdk import PinnedPeerError, open_pinned_url, parse_retry_after

from handlers.common import (
    DEMO_TOOLS,
    action_input,
    as_dict,
    as_list,
    as_text,
    fail,
    ok,
)

MAX_EXTERNAL_RESPONSE_BYTES = 65536
DEFAULT_ALLOWED_HOST = "api.example.test"
# The callback declared under `callbacks:` in extension.yaml.
CALLBACK_ID = "events"
DELIVERY_ID_HEADER = "X-Example-Showcase-Delivery"
MAX_EVENT_TEXT = 128
MAX_EVENT_KEYS = 20
RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
RETRY_FACT_KEYS = frozenset(
    {
        "failure_class",
        "retryable",
        "retry_after_seconds",
        "request_semantics",
        "operation_kind",
        "definitely_no_external_effect",
        "external_effect_status",
        "provider_error_code",
        "http_status",
    }
)


def _runtime_connection(action: dict[str, Any]) -> dict[str, Any]:
    target = as_dict(action.get("target"))
    return as_dict(target.get("connection"))


def _connection_config(action: dict[str, Any]) -> dict[str, Any]:
    payload = action_input(action)
    config = dict(as_dict(payload.get("connection_config") or payload.get("config")))
    config.update(as_dict(_runtime_connection(action).get("config")))
    return config


def _connection_token(action: dict[str, Any]) -> str:
    payload = action_input(action)
    secrets = as_dict(_runtime_connection(action).get("secrets"))
    for key in ("api_token", "access_token"):
        value = as_text(secrets.get(key))
        if value:
            return value
    for key in ("api_token", "access_token"):
        value = as_text(payload.get(key))
        if value:
            return value
    return ""


def _allowed_hosts(config: dict[str, Any]) -> set[str]:
    hosts = {
        as_text(item).lower() for item in as_list(config.get("allowed_hosts")) if as_text(item)
    }
    if not hosts:
        hosts.add(DEFAULT_ALLOWED_HOST)
    return hosts


def _external_url(config: dict[str, Any], resource_id: str) -> str:
    base_url = as_text(config.get("base_url"), f"https://{DEFAULT_ALLOWED_HOST}").rstrip("/")
    return f"{base_url}/status?{urlencode({'resource_id': resource_id})}"


def _validate_external_url(url: str, allowed_hosts: set[str]) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return False, "External requests must use HTTPS."
    if parsed.username or parsed.password:
        return False, "External request URLs must not include credentials."
    host = as_text(parsed.hostname).lower()
    if host not in allowed_hosts:
        return False, f"Host '{host}' is not in allowed_hosts."
    return True, ""


def _perform_external_get(url: str, token: str = "") -> dict[str, Any]:  # nosec B107
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with open_pinned_url(
            request,
            timeout_seconds=5,
            purpose="example_showcase external API request",
        ) as response:
            raw = response.read(MAX_EXTERNAL_RESPONSE_BYTES + 1)
            if len(raw) > MAX_EXTERNAL_RESPONSE_BYTES:
                return {"ok": False, "error": "external_response_too_large"}
            text = raw.decode("utf-8", errors="replace")
            try:
                body = json.loads(text)
            except json.JSONDecodeError:
                body = {"text": text[:1000]}
            return {
                "ok": True,
                "status_code": int(getattr(response, "status", 200)),
                "body": body,
            }
    except HTTPError as exc:
        status_code = int(exc.code)
        return {
            "ok": False,
            "error": "external_http_error",
            "status_code": status_code,
            "failure_class": "provider",
            "retryable": status_code in RETRYABLE_HTTP_STATUSES,
            "retry_after_seconds": parse_retry_after(
                exc.headers.get("Retry-After") if exc.headers is not None else None
            ),
            "request_semantics": "safe_read",
            "operation_kind": "source",
            "definitely_no_external_effect": True,
            "external_effect_status": "failed",
            "provider_error_code": "external_http_error",
            "http_status": status_code,
        }
    except PinnedPeerError as exc:
        return {
            "ok": False,
            "error": "external_request_failed",
            "detail": str(exc)[:200],
            "failure_class": "provider",
            "retryable": False,
            "request_semantics": "safe_read",
            "operation_kind": "source",
            "definitely_no_external_effect": True,
            "external_effect_status": "failed",
            "provider_error_code": "external_request_failed",
        }
    except OSError as exc:
        return {
            "ok": False,
            "error": "external_request_failed",
            "detail": str(exc)[:200],
            "failure_class": "transient",
            "retryable": True,
            "request_semantics": "safe_read",
            "operation_kind": "source",
            "definitely_no_external_effect": True,
            "external_effect_status": "failed",
            "provider_error_code": "external_request_failed",
        }


def test_external_request(action: dict[str, Any]) -> dict[str, Any]:
    payload = action_input(action)
    config = _connection_config(action)
    token = _connection_token(action)
    resource_id = as_text(payload.get("resource_id"), "demo-resource-1")
    url = _external_url(config, resource_id)
    allowed_hosts = _allowed_hosts(config)
    allowed, reason = _validate_external_url(url, allowed_hosts)
    request_summary = {
        "method": "GET",
        "url": url,
        "allowed_hosts": sorted(allowed_hosts),
        "resource_id": resource_id,
        "authorization": "bearer_token" if token else "none",
    }
    if not allowed:
        return fail("external_request_blocked", reason)
    perform_live_request = (
        bool(payload.get("perform_live_request")) and config.get("mock_mode") is not True
    )
    if not perform_live_request:
        return ok(
            {
                "status": "mocked",
                "external_request": request_summary,
                "external_response": {"ok": True, "body": {"state": "ready"}},
            },
            summary={"status": "mocked", "live_request": False, "authorized": bool(token)},
        )
    response = _perform_external_get(url, token)
    if not response.get("ok"):
        return fail(
            as_text(response.get("error"), "external_request_failed"),
            "External request failed",
            **{key: response[key] for key in RETRY_FACT_KEYS if key in response},
        )
    return ok(
        {"status": "live", "external_request": request_summary, "external_response": response},
        summary={
            "status": "live",
            "status_code": response.get("status_code"),
            "authorized": bool(token),
        },
    )


def send_review_notification(action: dict[str, Any]) -> dict[str, Any]:
    payload = action_input(action)
    message = as_text(payload.get("message"), "Example review requested.")
    severity = as_text(payload.get("severity"), "info")
    message_id = hashlib.sha256(message.encode("utf-8")).hexdigest()[:12]
    return ok(
        {
            "delivered": True,
            "provider_message_id": f"example-showcase:{message_id}",
            "severity": severity,
            "message_preview": message[:160],
        },
        summary={"delivered": True, "severity": severity},
    )


def batch_score_records(action: dict[str, Any]) -> dict[str, Any]:
    payload = action_input(action)
    records = [as_dict(item) for item in as_list(payload.get("records"))]
    scored: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        record_id = as_text(record.get("id") or record.get("record_id"))
        if not record_id:
            failed.append({"index": index, "error": "missing_id"})
            continue
        if record.get("active") is False:
            failed.append({"index": index, "id": record_id, "error": "inactive_record"})
            continue
        score = min(100, 25 + len(record_id) * 7)
        scored.append(
            {**record, "score": score, "routing_key": "review" if score >= 70 else "auto"}
        )
    return ok(
        {"scored_records": scored, "failed_records": failed},
        summary={"scored": len(scored), "failed": len(failed)},
    )


def run_demo_tool(action: dict[str, Any]) -> dict[str, Any]:
    payload = action_input(action)
    tool_id = as_text(payload.get("tool_id"), "demo_content_tools")
    tool = next((item for item in DEMO_TOOLS if item["tool_id"] == tool_id), None)
    if tool is None:
        return fail("unknown_tool", f"Unknown demo tool '{tool_id}'.")
    return ok(
        {
            "tool_result": {
                "tool_id": tool_id,
                "display_name": tool["display_name"],
                "coverage": tool["coverage"],
                "payload_echo": as_dict(payload.get("payload")),
            }
        },
        summary={"tool_id": tool_id, "status": "completed"},
    )


def invoke_tool(action: dict[str, Any]) -> dict[str, Any]:
    payload = action_input(action)
    tool_name = as_text(payload.get("tool_name"))
    allowed = {
        "demo_load_product_catalog",
        "demo_enrich_product_catalog",
        "demo_store_product_catalog_artifact",
        "demo_weather_brief",
        "demo_measure_text",
        "demo_compose_content_brief",
        "demo_merge_launch_review",
    }
    if tool_name not in allowed:
        return fail("unknown_tool", f"Unknown extension tool '{tool_name}'.")
    module = importlib.import_module("demo_workflow_tools")
    tool = getattr(module, tool_name)
    arguments = as_dict(payload.get("arguments"))
    if tool_name == "demo_store_product_catalog_artifact":
        arguments["runtime_payload"] = action
    result = tool.invoke(arguments) if hasattr(tool, "invoke") else tool(**arguments)
    return ok(result)


def oauth_profile(action: dict[str, Any]) -> dict[str, Any]:
    target = as_dict(action.get("target"))
    connection = as_dict(target.get("connection"))
    secrets = as_dict(connection.get("secrets"))
    access_token = as_text(secrets.get("access_token"))
    if not access_token:
        return fail(
            "missing_access_token", "OAuth access token was not injected into the runtime target."
        )
    return ok(
        {
            "connection_id": as_text(connection.get("connection_id")),
            "connection_type": as_text(connection.get("connection_type")),
            "environment": as_text(connection.get("environment")),
            "token_received": True,  # nosec B105
            "refresh_token_visible": "_oauth_refresh_token" in secrets
            or "refresh_token" in secrets,
        },
        summary={"token_received": True, "connection_id": as_text(connection.get("connection_id"))},  # nosec B105
    )


def _header(headers: dict[str, Any], name: str) -> str:
    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return as_text(value)
    return ""


def _bounded(value: Any, limit: int = MAX_EVENT_TEXT) -> str:
    return as_text(value)[:limit]


def receive_provider_event(action: dict[str, Any]) -> dict[str, Any]:
    """Handle one delivery on the ``events`` callback.

    Core has already checked the HMAC signature, the timestamp window and the
    delivery id before this runs, so the handler only reads the event. It
    returns a bounded summary: never the headers (they carry the signature),
    never the raw body, and at most ``MAX_EVENT_KEYS`` top-level keys.
    """
    envelope = as_dict(action.get("input"))
    callback = as_dict(envelope.get("callback"))
    request = as_dict(envelope.get("request"))
    if (
        as_text(callback.get("callback_id")) != CALLBACK_ID
        or callback.get("authenticated") is not True
    ):
        return fail(
            "unexpected_callback",
            "Only authenticated deliveries on the events callback are handled.",
        )
    if as_text(request.get("method")).upper() != "POST":
        return fail("invalid_payload", "Provider events arrive as POST requests.")
    event = request.get("json")
    if not isinstance(event, dict) or not event:
        return fail("invalid_payload", "The delivery body must be a non-empty JSON object.")
    event_type = _bounded(event.get("event_type") or event.get("type"))
    if not event_type:
        return fail("invalid_payload", "The provider event must name its event_type.")
    try:
        raw_body = base64.b64decode(as_text(request.get("raw_body_base64")), validate=True)
    except (binascii.Error, ValueError):
        raw_body = b""
    headers = as_dict(request.get("headers"))
    return ok(
        {
            "status": "received",
            "project_id": as_text(callback.get("project_id")),
            "event": {
                "event_type": event_type,
                "event_id": _bounded(event.get("event_id") or event.get("id")),
                "source": _bounded(event.get("source")),
                "keys": sorted(_bounded(key) for key in event)[:MAX_EVENT_KEYS],
                "key_count": len(event),
            },
            "delivery": {
                "delivery_id": _bounded(_header(headers, DELIVERY_ID_HEADER)),
                "body_bytes": len(raw_body),
                "body_sha256": hashlib.sha256(raw_body).hexdigest(),
            },
        },
        summary={"status": "received", "event_type": event_type},
    )


def configure_webhook(action: dict[str, Any]) -> dict[str, Any]:
    """Hand the callback URL and signing secret to the provider.

    A real extension calls the provider's "set webhook" API here with
    ``callback_url`` and ``callback_secret``. The example provider is a mock, so
    nothing is sent or stored, and neither value is echoed back.
    """
    payload = as_dict(action.get("input"))
    if not as_text(payload.get("callback_url")):
        return fail("callback_url_required", "Core did not pass the callback URL.")
    if not as_text(payload.get("callback_secret")):
        return fail("callback_secret_required", "Core did not pass the callback signing secret.")
    return ok(
        {
            "url_configured": True,
            "provider_mode": "mock",
            "signing": "hmac_sha256",
            "pending_update_count": 0,
        },
        summary={"url_configured": True, "provider_mode": "mock"},
    )


def get_webhook_status(action: dict[str, Any]) -> dict[str, Any]:
    """Report the provider-side webhook status; the mock provider keeps no state."""
    _ = action
    return ok(
        {"url_configured": True, "provider_mode": "mock", "pending_update_count": 0},
        summary={"url_configured": True, "provider_mode": "mock"},
    )


ACTION_HANDLERS = {
    "invoke_tool": invoke_tool,
    "receive_provider_event": receive_provider_event,
    "configure_webhook": configure_webhook,
    "get_webhook_status": get_webhook_status,
    "test_external_request": test_external_request,
    "send_review_notification": send_review_notification,
    "batch_score_records": batch_score_records,
    "run_demo_tool": run_demo_tool,
    "oauth_profile": oauth_profile,
}

"""Action handlers for the Example Showcase extension."""

from __future__ import annotations

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


ACTION_HANDLERS = {
    "invoke_tool": invoke_tool,
    "test_external_request": test_external_request,
    "send_review_notification": send_review_notification,
    "batch_score_records": batch_score_records,
    "run_demo_tool": run_demo_tool,
    "oauth_profile": oauth_profile,
}

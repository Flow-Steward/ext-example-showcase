"""Query handlers for the Example Showcase extension."""

from __future__ import annotations

from typing import Any

from handlers.common import (
    CONTRACT_OPERATIONS,
    DEMO_AGENTS,
    DEMO_TOOLS,
    DEMO_WORKFLOWS,
    EXTENSION_ID,
    as_dict,
    as_text,
    ok,
)


def _query_params(query: dict[str, Any]) -> dict[str, Any]:
    return as_dict(query.get("params"))


def _query_context(query: dict[str, Any]) -> dict[str, Any]:
    return as_dict(query.get("context"))


def provider_health(query: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(query)
    context = _query_context(query)
    project_id = as_text(context.get("project_id") or params.get("project_id"))
    checks = [
        {
            "name": "Subprocess runtime",
            "status": "healthy",
            "detail": "main.py handles query/action envelopes",
        },
        {
            "name": "Project scope",
            "status": "healthy" if project_id else "warning",
            "detail": project_id or "No project_id in query context",
        },
        {
            "name": "Artifact bundle",
            "status": "healthy",
            "detail": f"{len(DEMO_WORKFLOWS)} workflows, {len(DEMO_AGENTS)} agents, {len(DEMO_TOOLS)} tools",
        },
    ]
    artifact_stats = [
        {
            "label": "Workflows",
            "value": str(len(DEMO_WORKFLOWS)),
            "trend": "all demo workflow seed examples",
        },
        {
            "label": "Agents",
            "value": str(len(DEMO_AGENTS)),
            "trend": "specialist demo agents",
        },
        {
            "label": "Tools",
            "value": str(len(DEMO_TOOLS)),
            "trend": "deterministic tool artifacts",
        },
        {
            "label": "Operations",
            "value": str(len(CONTRACT_OPERATIONS)),
            "trend": "Contract v2 examples",
        },
    ]
    return ok(
        {
            "status": "healthy" if project_id else "degraded",
            "provider": EXTENSION_ID,
            "configured": bool(project_id),
            "runtime": "local_subprocess",
            "checks": checks,
        },
        items=artifact_stats,
        summary={
            "provider": EXTENSION_ID,
            "status": "healthy" if project_id else "degraded",
            "configured": bool(project_id),
            "workflows": len(DEMO_WORKFLOWS),
            "agents": len(DEMO_AGENTS),
            "tools": len(DEMO_TOOLS),
        },
    )


def load_connection_settings(query: dict[str, Any]) -> dict[str, Any]:
    _ = query
    return ok(
        {
            "settings": {
                "base_url": "https://api.example.test",
                "username": "demo-user",
                "tenant": "demo",
                "allowed_hosts": ["api.example.test"],
                "mock_mode": True,
                "default_priority": "medium",
                "notification_channel": "showcase-review",
                "labels": ["example", "showcase"],
            }
        },
        summary={"status": "loaded", "secret_values": "not returned"},  # nosec B105
    )


def connection_status(query: dict[str, Any]) -> dict[str, Any]:
    params = _query_params(query)
    base_url = as_text(params.get("base_url"), "https://api.example.test")
    username = as_text(params.get("username"), "demo-user")
    return ok(
        {
            "status": "ready",
            "configured": bool(base_url and username),
            "base_url": base_url,
            "username": username,
            "secrets": {"password": "<stored>", "api_token": "<stored>"},  # nosec B105
        },
        summary={"status": "ready", "configured": bool(base_url and username)},
    )


def list_demo_workflows(query: dict[str, Any]) -> dict[str, Any]:
    _ = query
    return ok(
        {"items": DEMO_WORKFLOWS},
        items=DEMO_WORKFLOWS,
        summary={"total": len(DEMO_WORKFLOWS), "artifact_type": "workflow"},
        total=len(DEMO_WORKFLOWS),
    )


def list_demo_agents(query: dict[str, Any]) -> dict[str, Any]:
    _ = query
    return ok(
        {"items": DEMO_AGENTS},
        items=DEMO_AGENTS,
        summary={"total": len(DEMO_AGENTS), "artifact_type": "agent"},
        total=len(DEMO_AGENTS),
    )


def list_demo_tools(query: dict[str, Any]) -> dict[str, Any]:
    _ = query
    return ok(
        {"items": DEMO_TOOLS},
        items=DEMO_TOOLS,
        summary={"total": len(DEMO_TOOLS), "artifact_type": "tool"},
        total=len(DEMO_TOOLS),
    )


def list_example_resources(query: dict[str, Any]) -> dict[str, Any]:
    _ = query
    items = [
        {"id": "demo-resource-1", "label": "Demo Resource 1", "status": "ready"},
        {"id": "demo-resource-2", "label": "Demo Resource 2", "status": "review"},
    ]
    return ok({"items": items}, items=items, summary={"total": len(items)})


def operation_contracts(query: dict[str, Any]) -> dict[str, Any]:
    _ = query
    return ok(
        {"items": CONTRACT_OPERATIONS},
        items=CONTRACT_OPERATIONS,
        summary={"total": len(CONTRACT_OPERATIONS), "artifact_type": "operation"},
        total=len(CONTRACT_OPERATIONS),
    )


QUERY_HANDLERS = {
    "provider_health": provider_health,
    "load_connection_settings": load_connection_settings,
    "connection_status": connection_status,
    "list_demo_workflows": list_demo_workflows,
    "list_demo_agents": list_demo_agents,
    "list_demo_tools": list_demo_tools,
    "list_example_resources": list_example_resources,
    "operation_contracts": operation_contracts,
}

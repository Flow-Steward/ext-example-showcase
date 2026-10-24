"""Shared helpers and bundle-local showcase catalog data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

EXTENSION_ID = "example_showcase"
BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _artifact_catalog(kind: str, *, id_key: str, detail_key: str) -> list[dict[str, str]]:
    descriptor = yaml.safe_load(
        (BUNDLE_ROOT / "extension-descriptor.yaml").read_text(encoding="utf-8")
    )
    rows: list[dict[str, str]] = []
    for artifact_ref in descriptor["artifacts"][kind]:
        artifact = yaml.safe_load(
            (BUNDLE_ROOT / str(artifact_ref["ref"])).read_text(encoding="utf-8")
        )
        detail = artifact.get(detail_key)
        if detail_key == "coverage":
            detail = (artifact.get("builder_metadata_jsonb") or {}).get("purpose")
        rows.append(
            {
                id_key: str(artifact[id_key]),
                "display_name": str(artifact["display_name"]),
                detail_key: str(detail or ""),
            }
        )
    return rows


DEMO_WORKFLOWS = _artifact_catalog("workflows", id_key="workflow_id", detail_key="coverage")
DEMO_AGENTS = _artifact_catalog("agents", id_key="agent_id", detail_key="base_skill")
DEMO_TOOLS = _artifact_catalog("tools", id_key="tool_id", detail_key="coverage")

CONTRACT_OPERATIONS: list[dict[str, str]] = [
    {"operation_id": "test_external_request", "operation_kind": "source"},
    {"operation_id": "send_review_notification", "operation_kind": "human_channel"},
    {"operation_id": "batch_score_records", "operation_kind": "bulk_action"},
    {"operation_id": "run_demo_tool", "operation_kind": "action"},
    {"operation_id": "oauth_profile", "operation_kind": "action"},
]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def ok(
    result: dict[str, Any] | None = None,
    *,
    items: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    reload: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "result": result or {},
        "items": items or [],
        "summary": summary or {},
        "commands": [],
        "events": [],
        "reload": reload or [],
        "errors": [],
    }
    payload.update(extra)
    return payload


def fail(
    code: str,
    message: str = "",
    *,
    status: int = 2,
    **extra: Any,
) -> dict[str, Any]:
    normalized_code = as_text(code, "internal_error")
    normalized_message = as_text(message, normalized_code)
    payload = {
        "ok": False,
        "error_code": normalized_code,
        "error": normalized_message,
        "status": status,
        "result": {},
        "items": [],
        "summary": {},
        "commands": [],
        "events": [],
        "reload": [],
        "errors": [{"code": normalized_code, "message": normalized_message}],
    }
    payload.update(extra)
    return payload


def action_input(action: dict[str, Any]) -> dict[str, Any]:
    payload = as_dict(action.get("input"))
    nested = as_dict(payload.get("payload"))
    return nested or payload


def redacted_secret_refs(payload: dict[str, Any]) -> dict[str, str]:
    refs = as_dict(payload.get("secret_refs") or payload.get("secrets"))
    values = as_dict(refs.get("refs")) or refs
    redacted: dict[str, str] = {}
    for key, value in values.items():
        if value in (None, ""):
            continue
        redacted[str(key)] = "<stored>"
    return redacted

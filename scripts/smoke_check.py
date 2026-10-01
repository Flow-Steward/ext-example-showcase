#!/usr/bin/env python3
"""Smoke check for the Example Showcase extension."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_TOKEN_MAIN_PY = "main.py"

ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=str(ROOT),
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    output = proc.stdout.strip()
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or output or f"{args} failed")
    return json.loads(output) if output else {}


def main() -> int:
    health = _run(["health.py"])
    if health.get("status") != "healthy":
        raise RuntimeError(f"health failed: {health}")

    provider_health = _run(
        [_TOKEN_MAIN_PY],
        {
            "mode": "query",
            "query": {
                "query_id": "provider_health",
                "context": {"project_id": "demo-project"},
            },
        },
    )
    if provider_health.get("ok") is not True:
        raise RuntimeError(f"provider_health failed: {provider_health}")

    workflows = _run(
        [_TOKEN_MAIN_PY],
        {"mode": "query", "query": {"query_id": "list_demo_workflows"}},
    )
    if workflows.get("total") != 10:
        raise RuntimeError(f"workflow artifact query failed: {workflows}")

    external = _run(
        [_TOKEN_MAIN_PY],
        {
            "mode": "action",
            "action": {
                "action_id": "test_external_request",
                "input": {
                    "resource_id": "demo-resource-1",
                    "connection_config": {
                        "base_url": "https://api.example.test",
                        "allowed_hosts": ["api.example.test"],
                        "mock_mode": True,
                    },
                },
            },
        },
    )
    if external.get("result", {}).get("status") != "mocked":
        raise RuntimeError(f"external request action failed: {external}")

    print(json.dumps({"ok": True, "checked": ["health", "queries", "actions"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

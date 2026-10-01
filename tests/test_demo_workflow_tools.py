from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "example_showcase_demo_workflow_tools", BUNDLE_ROOT / "demo_workflow_tools.py"
)
assert SPEC
assert SPEC.loader
demo_workflow_tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo_workflow_tools)


def _invoke(tool_obj, payload: dict):
    return tool_obj.invoke(payload) if hasattr(tool_obj, "invoke") else tool_obj(**payload)


def test_demo_tools_run_from_isolated_bundle(monkeypatch) -> None:
    rows = _invoke(demo_workflow_tools.demo_load_product_catalog, {"limit": 2})
    enriched = _invoke(
        demo_workflow_tools.demo_enrich_product_catalog,
        {"rows": rows["rows"], "tone": "friendly"},
    )
    captured: dict = {}

    def _write_artifact(payload, body, **kwargs):
        captured.update({"payload": payload, "body": body, **kwargs})
        return {
            "artifact_id": "artifact-1",
            "artifact_handle": "artifact:artifact-1",
            "binding_key": "catalog_artifact",
            "content_type": "text/csv",
            "size_bytes": len(body),
            "sha256": "host-digest",
        }

    monkeypatch.setattr(demo_workflow_tools, "write_artifact_bytes", _write_artifact)
    runtime_payload = {
        "artifacts": {
            "outputs": [
                {
                    "artifact_id": "artifact-1",
                    "artifact_handle": "artifact:artifact-1",
                    "binding_key": "catalog_artifact",
                    "role": "output",
                    "access": {"upload_url": "https://host.invalid/upload"},
                }
            ]
        }
    }
    stored = _invoke(
        demo_workflow_tools.demo_store_product_catalog_artifact,
        {
            "rows": enriched["rows"],
            "filename": "demo.csv",
            "runtime_payload": runtime_payload,
        },
    )

    assert rows["row_count"] == 2
    assert enriched["ready_count"] == 2
    assert captured["payload"] == runtime_payload
    assert captured["binding_key"] == "catalog_artifact"
    assert stored["artifact"]["artifact_handle"] == "artifact:artifact-1"
    assert stored["artifact"]["storage_backend"] == "host_managed"


def test_demo_tools_have_no_private_durable_file_writes() -> None:
    source = (BUNDLE_ROOT / "demo_workflow_tools.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "mkdir" not in called_attributes
    assert "write_bytes" not in called_attributes
    assert "write_text" not in called_attributes
    assert "ARTIFACT_LOCAL_ROOT_DIR" not in source
    assert "tempfile" not in source


def test_demo_weather_and_content_tools_return_required_outputs() -> None:
    weather = _invoke(
        demo_workflow_tools.demo_weather_brief,
        {"city": "Vilnius", "weather_response": {"current": {"temperature_2m": 12}}},
    )
    brief = _invoke(
        demo_workflow_tools.demo_compose_content_brief,
        {"topic": "Launch", "audience": "operators", "channel": "email", "tone": "clear"},
    )
    merged = _invoke(
        demo_workflow_tools.demo_merge_launch_review,
        {"agent_messages": [{"artifacts": {"launch_copy": "Copy", "risk_review": "Risk"}}]},
    )
    measured = _invoke(
        demo_workflow_tools.demo_measure_text,
        {"value": "Intentional stop_fail"},
    )

    assert "Vilnius" in weather["weather_summary"]
    assert brief["content_brief"]["channel"] == "email"
    assert merged["launch_readiness_report"]["status"] == "ready"
    assert measured == {"result": 21}

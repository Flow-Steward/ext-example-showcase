"""Deterministic tools used by the optional demo workflow extension."""

from __future__ import annotations

import csv
import hashlib
import json
from io import StringIO
from pathlib import Path
from typing import Any

from flowsteward_extension_sdk import write_artifact_bytes

try:  # pragma: no cover - dependency is present in the full runtime.
    from langchain_core.tools import tool
except Exception:  # pragma: no cover

    def tool(func=None, **_kwargs):
        return func if func is not None else (lambda wrapped: wrapped)


TEXT_CSV_VALUE = "text/csv"


CATALOG_SAMPLE_PATH = Path(__file__).resolve().parent / "fixtures" / "product_catalog_sample.csv"


def _coerce_rows(rows: Any) -> list[dict[str, Any]]:
    if isinstance(rows, list):
        return [dict(row) for row in rows if isinstance(row, dict)]
    if isinstance(rows, str):
        text = rows.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            return []
        return _coerce_rows(parsed)
    return []


def _string(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _object(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["message"]
        rows = [{"message": "No rows"}]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return buffer.getvalue().encode("utf-8")


def _save_job_attachment(
    *,
    job_id: str | None,
    filename: str,
    mime_type: str,
    content: bytes,
) -> dict[str, Any]:
    # Host-owned attachment persistence is intentionally unavailable to isolated tools.
    # The tool returns portable artifact metadata and lets the host bind it to a run.
    del content, filename, job_id, mime_type
    return {}


@tool
def demo_load_product_catalog(limit: int = 10, job_id: str | None = None) -> dict[str, Any]:
    """Load the bundled demo product catalog CSV."""
    if not CATALOG_SAMPLE_PATH.is_file():
        raise FileNotFoundError(str(CATALOG_SAMPLE_PATH))
    safe_limit = max(1, min(_safe_int(limit, 10), 100))
    source_body = CATALOG_SAMPLE_PATH.read_bytes()
    with CATALOG_SAMPLE_PATH.open("r", encoding="utf-8", newline="") as fh:
        rows = [dict(row) for row in csv.DictReader(fh)]
    selected = rows[:safe_limit]
    source_artifact: dict[str, Any] = {
        "filename": CATALOG_SAMPLE_PATH.name,
        "content_type": TEXT_CSV_VALUE,
        "size_bytes": len(source_body),
        "sha256": hashlib.sha256(source_body).hexdigest(),
        "row_count": len(rows),
        "retention_class": "run_window",
    }
    attachment = _save_job_attachment(
        job_id=job_id,
        filename=CATALOG_SAMPLE_PATH.name,
        mime_type=TEXT_CSV_VALUE,
        content=source_body,
    )
    if attachment:
        source_artifact["job_attachment"] = attachment
        if attachment.get("download_url"):
            source_artifact["download_url"] = attachment["download_url"]
            source_artifact["job_attachment_url"] = attachment["download_url"]
    return {
        "rows": selected,
        "catalog_rows": selected,
        "row_count": len(selected),
        "source_file": str(CATALOG_SAMPLE_PATH),
        "source_filename": CATALOG_SAMPLE_PATH.name,
        "source_artifact": source_artifact,
        "source_file_url": source_artifact.get("download_url", ""),
    }


@tool
def demo_enrich_product_catalog(
    rows: list[dict[str, Any]],
    tone: str = "friendly",
    batch_label: str = "demo-extension",
    max_rows: int = 100,
) -> dict[str, Any]:
    """Create deterministic marketing descriptions for product catalog rows."""
    safe_rows = _coerce_rows(rows)[: max(1, min(_safe_int(max_rows, 100), 500))]
    clean_tone = _string(tone, "friendly")
    label = _string(batch_label, "demo-extension")
    enriched: list[dict[str, Any]] = []
    for row in safe_rows:
        product = _string(row.get("product_name"), "Product")
        audience = _string(row.get("target_audience"), "busy teams")
        category = _string(row.get("category"), "General")
        keywords = _string(row.get("keywords"), "useful,practical")
        material = _string(row.get("material"), "durable materials")
        description = (
            f"{product} is a {clean_tone} {category.lower()} pick for {audience}. "
            f"Made with {material}, it is positioned around {keywords}."
        )
        enriched.append(
            {
                **row,
                "demo_batch": label,
                "short_description": description,
                "seo_title": f"{product} for {audience}".title()[:70],
                "readiness": "ready",
            }
        )
    ready_count = sum(1 for row in enriched if row.get("readiness") == "ready")
    return {
        "rows": enriched,
        "enriched_catalog_rows": enriched,
        "row_count": len(enriched),
        "ready_count": ready_count,
    }


@tool
def demo_store_product_catalog_artifact(
    rows: list[dict[str, Any]],
    filename: str = "demo_enriched_catalog.csv",
    workflow_id: str = "",
    step_id: str = "",
    job_id: str | None = None,
    retention_class: str = "run_window",
    runtime_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store enriched catalog rows as a CSV artifact."""
    safe_rows = _coerce_rows(rows)
    safe_filename = _string(filename, "demo_enriched_catalog.csv")
    safe_workflow_id = _string(workflow_id, "")
    csv_body = _rows_to_csv(safe_rows)
    digest = hashlib.sha256(csv_body).hexdigest()
    artifact: dict[str, Any] = {
        "filename": safe_filename,
        "content_type": TEXT_CSV_VALUE,
        "size_bytes": len(csv_body),
        "sha256": digest,
        "row_count": len(safe_rows),
        "retention_class": _string(retention_class, "run_window"),
        "workflow_id": safe_workflow_id,
    }

    uploaded = write_artifact_bytes(
        dict(runtime_payload or {}),
        csv_body,
        binding_key="catalog_artifact",
        content_type=TEXT_CSV_VALUE,
    )
    artifact.update(uploaded)
    artifact["storage_backend"] = "host_managed"

    attachment = _save_job_attachment(
        job_id=job_id,
        filename=safe_filename,
        mime_type=TEXT_CSV_VALUE,
        content=csv_body,
    )
    if attachment:
        if attachment.get("error"):
            artifact["job_attachment_error"] = attachment["error"]
        else:
            artifact["job_attachment"] = attachment
            if attachment.get("download_url"):
                artifact["download_url"] = attachment["download_url"]
                artifact["job_attachment_url"] = artifact["download_url"]

    return {
        "artifact": artifact,
        "catalog_artifact": artifact,
        "artifact_id": artifact.get("artifact_id", ""),
        "download_url": artifact.get("download_url", ""),
    }


@tool
def demo_weather_brief(city: str, weather_response: dict[str, Any]) -> dict[str, Any]:
    """Format an Open-Meteo response into a concise weather summary."""
    clean_city = _string(city, "selected city")
    payload = _object(weather_response)
    current = _object(payload.get("current"))
    units = _object(payload.get("current_units"))
    temp = current.get("temperature_2m")
    wind = current.get("wind_speed_10m")
    code = current.get("weather_code")
    temp_unit = _string(units.get("temperature_2m"), "C")
    wind_unit = _string(units.get("wind_speed_10m"), "km/h")
    condition = f"weather code {code}" if code is not None else "current conditions available"
    summary = f"{clean_city}: {temp}{temp_unit} with {wind} {wind_unit} wind ({condition})."
    return {
        "weather_summary": summary,
        "condition": condition,
        "temperature": temp,
        "wind_speed": wind,
    }


@tool
def demo_measure_text(value: str) -> dict[str, int]:
    """Return the deterministic character count used by guardrail demos."""
    return {"result": len(str(value or ""))}


@tool
def demo_compose_content_brief(
    topic: str = "Flow Steward demo workflow extension",
    audience: str = "new Flow Steward users",
    channel: str = "email",
    tone: str = "clear",
) -> dict[str, Any]:
    """Compose a deterministic content brief for demo workflows."""
    clean_topic = _string(topic, "Flow Steward demo workflow extension")
    clean_audience = _string(audience, "new Flow Steward users")
    clean_channel = _string(channel, "email")
    clean_tone = _string(tone, "clear")
    headline = f"{clean_topic}: a {clean_tone} {clean_channel} brief"
    body = (
        f"Audience: {clean_audience}. Lead with the practical outcome, show one "
        "working workflow result, and close with the next action."
    )
    brief = {
        "headline": headline,
        "body": body,
        "channel": clean_channel,
        "audience": clean_audience,
        "tone": clean_tone,
    }
    return {
        "headline": headline,
        "body": body,
        "content_brief": brief,
        "travel_plan_brief": {
            **brief,
            "weather_note": f"Use the mapped weather summary when planning {clean_topic}.",
        },
    }


@tool
def demo_merge_launch_review(agent_messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge parallel demo agent artifacts into one launch readiness report."""
    messages = [dict(row) for row in (agent_messages or []) if isinstance(row, dict)]
    launch_copy = ""
    risk_review = ""
    for message in messages:
        artifacts = _object(message.get("artifacts"))
        launch_copy = launch_copy or _string(artifacts.get("launch_copy"))
        risk_review = risk_review or _string(artifacts.get("risk_review"))
    report = {
        "status": "ready" if launch_copy and risk_review else "needs_followup",
        "launch_copy": launch_copy,
        "risk_review": risk_review,
        "recommendation": "Publish the demo extension with guided sample runs."
        if launch_copy and risk_review
        else "Review missing parallel artifacts before publishing.",
    }
    return {"launch_readiness_report": report}

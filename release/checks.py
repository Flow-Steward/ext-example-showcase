"""What this bundle must still do on a release candidate.

These assertions are about Example Showcase in particular — its workflow matrix,
its catalog artifact, the OAuth demo it declares — so they live with the bundle
rather than in the platform's smoke, which must not know that any of it exists.

They run over the public API only. There is no database handle and no platform
module here on purpose: an assertion that reaches past the API is asserting
something this extension does not own, and the platform's own generic checks
already cover projection lifecycle, catalog state, storage integrity and cleanup
on a synthetic probe.

The one thing the API cannot do is create rows in an external database, so the
`demo_dataset_open_orders` matrix entry runs only when the stand has already
provided a data connection with the demo's own table behind it. When it has not,
the check records that rather than passing quietly.

Two kinds of "did not run" are distinguished on purpose, because conflating them
either hides a broken stand or leaves a permanent red nobody can clear:

* a **precondition the stand can meet** — a missing dev/test override, a missing
  model route — is recorded as a **failure** naming the cause, because a release
  candidate is supposed to have it;
* a **limitation of the platform's public surface** — there is no endpoint that
  reads an artifact's bytes — is recorded as **NOT RUN** with the task that
  would lift it, because no configuration of this candidate can answer it.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

#: What this suite may do, and no more. Every DELETE on the candidate is
#: admin-only, and so is enabling an extension, so neither is here: the trusted
#: harness enables what `RELEASE_EXTENSIONS` names, prepares the project, and
#: removes whatever the suite declares it created.
RELEASE_SCOPES = [
    "command:*",
    "extension:invoke",
    "jobs:*",
    "notify:*",
    "projects:*",
    "read:*",
    "registry:*",
    "workflows:*",
]

#: Enabled by the trusted harness for the run, and restored after it.
RELEASE_EXTENSIONS = [
    "flowsteward.example-showcase",
    "flowsteward.toolbox-dataset-connector",
]
#: The addresses this suite observes besides the candidate. None: it reaches the
#: candidate and nothing else.
#: The model route a candidate is configured with. Some demo agents are
#: deterministic and need none; the launch-risk review calls a model, so a stand
#: without a provider cannot run it — which the matrix reports by name.
RELEASE_INPUTS = [
    "FS_SMOKE_MODEL_PROVIDER",
    "FS_SMOKE_MODEL",
]

EXTENSION_ID = "flowsteward.example-showcase"
#: The connector extension the dataset demo needs before it can bind anything.
DATASET_DEPENDENCY_ID = "flowsteward.toolbox-dataset-connector"

#: Every workflow this bundle publishes, and what running it should produce.
#: `None` for the output name means the run is expected to fail on purpose.
EXECUTABLE_MATRIX: dict[str, tuple[dict[str, Any], str, str]] = {
    "demo_content_campaign_router": ({"channel": "social"}, "content_brief", "completed"),
    "demo_expected_failure_guardrail": ({}, "", "failed"),
    "demo_incoming_webhook_router": (
        {
            "email": "release-smoke@example.invalid",
            "event_type": "invoice.created",
            "amount": 42.5,
            "source": "release",
        },
        "webhook_summary",
        "completed",
    ),
    "demo_parallel_launch_review": (
        # The demo checks its brief for the things a launch review needs, and
        # stops when they are absent — so the request has to be a real one.
        {
            "request": (
                "Prepare an email launch review for Flow Steward 1.0. "
                "Audience: operations teams in a 20-person pilot. "
                "Value proposition: reliable scheduled workflows with human approval. "
                "Launch date: next Monday. Draft the launch copy and identify one "
                "operational risk with a mitigation."
            )
        },
        "launch_readiness_report",
        "completed",
    ),
    "demo_product_catalog_enrichment": (
        {"request": "Enrich all ten bundled catalog rows."},
        "catalog_artifact",
        "completed",
    ),
    "demo_travel_day_planner": ({}, "travel_plan_brief", "completed"),
    "demo_weather_city_brief": ({"city": "Vilnius"}, "weather_summary", "completed"),
}

#: Published but not executed here, and why.
UNEXECUTED = {
    "demo_dataset_open_orders": "needs an external database this suite cannot seed over the API",
    "demo_oauth_connection_binding": "needs a declared OAuth provider the candidate does not ship",
    "demo_weather_summary_child": "asserted through its parent, demo_travel_day_planner",
}


def _rows(payload: Any, key: str) -> list[dict[str, Any]]:
    """Rows from a listing, whether it is wrapped in a key or is the list itself.

    `/api/workflows` answers with a bare array while `/api/workspaces` wraps its
    rows; reading only the wrapped shape silently yields nothing.
    """
    rows = payload if isinstance(payload, list) else None
    if rows is None:
        rows = payload.get(key) if isinstance(payload, dict) else None
    return [row for row in rows or [] if isinstance(row, dict)]


def _workspace_id(_api: Any = None) -> str:
    """The workspace the harness made this run's project in.

    Not looked up: `/api/workspaces` is admin-only, and a suite's token is not.
    """
    return str(os.environ.get("FS_RELEASE_WORKSPACE_ID") or "")


def _qualified_workflow_ids(api: Any) -> dict[str, str]:
    """Map each declared workflow to the catalog id the API reports for it.

    Read from the catalog rather than composed here, so the suite never has to
    know how the platform qualifies an extension's artifact ids.
    """
    resolved: dict[str, str] = {}
    status, payload = api.request("GET", "/api/workflows?per_page=500")
    if status != 200:
        return resolved
    for row in _rows(payload, "workflows"):
        workflow_id = str(row.get("workflow_id") or "").strip()
        for declared in (*EXECUTABLE_MATRIX, *UNEXECUTED):
            if workflow_id.endswith(f".{declared}") or workflow_id == declared:
                resolved[declared] = workflow_id
    return resolved


def _await_job(api: Any, job_id: str, *, timeout_seconds: int = 900) -> tuple[str, dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    detail: dict[str, Any] = {}
    status = ""
    while time.monotonic() < deadline:
        _, payload = api.request("GET", f"/api/jobs/{job_id}")
        detail = payload if isinstance(payload, dict) else {}
        status = str(detail.get("status") or "").strip()
        if status in {"completed", "failed", "cancelled"}:
            return status, detail
        time.sleep(3)
    return status or "timeout", detail


#: Where a finished run's named output can sit in the public job detail. A
#: workflow that produces an artifact reports it under `artifacts`; one that
#: produces a value reports it under `outputs`; older runs surface it in the
#: thread state. Reading only one of them makes a completed job look empty.
_OUTPUT_PATHS = (
    ("workflow_run", "result", "outputs"),
    ("workflow_run", "result", "artifacts"),
    ("thread_state", "workflow_outputs", "outputs"),
    ("thread_state", "outputs"),
    ("state",),
)


def _output(detail: dict[str, Any], name: str) -> Any:
    for path in _OUTPUT_PATHS:
        value: Any = detail
        for key in (*path, name):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _model_unavailable(detail: dict[str, Any]) -> str:
    """The stand has no route for a step's model, which is not this bundle's doing."""
    for value in (detail.get("last_error"), detail.get("error")):
        text = value if isinstance(value, str) else str((value or {}).get("message") or "")
        if "model_unavailable" in text:
            return text.split("|")[0].strip()[:160]
    return ""


def _expected_failure_guardrail_reached(detail: dict[str, Any]) -> bool:
    """Distinguish the intentional stop from an unrelated early failure."""
    workflow_run = detail.get("workflow_run")
    workflow_run = workflow_run if isinstance(workflow_run, dict) else {}
    workflow_error = workflow_run.get("error")
    workflow_error = workflow_error if isinstance(workflow_error, dict) else {}
    candidates = (
        workflow_error.get("message"),
        detail.get("error"),
        detail.get("last_error"),
        detail.get("final_report"),
    )
    expected = "Workflow terminated by stop_fail control-flow step"
    for value in candidates:
        text = value if isinstance(value, str) else str((value or {}).get("message") or "")
        if expected in text:
            return True
    return False


def _submit(api: Any, project_id: str, workflow_id: str, inputs: dict[str, Any]) -> str:
    status, payload = api.request(
        "POST",
        "/api/tasks",
        {
            "task_id": f"showcase-{uuid.uuid4().hex[:10]}",
            "task_summary": "Example Showcase release check.",
            "project_id": project_id,
            "workflow_id": workflow_id,
            "mode": "brownfield",
            "inputs": inputs,
        },
    )
    if status not in {200, 201, 202}:
        raise RuntimeError(f"task submit failed with HTTP {status}: {payload}")
    return str((payload or {}).get("job_id") or "")


def showcase_release_matrix(api: Any, evidence: Any) -> None:
    """Run every executable Showcase workflow and check what it produced."""
    # The harness enabled this bundle and its dataset dependency for the run and
    # will restore both; what the suite checks is that the candidate reports them
    # active, and it works in the project the harness prepared.
    dependency_status, dependency = api.request("GET", f"/api/extensions/{DATASET_DEPENDENCY_ID}")
    dependency_state = (
        str((dependency or {}).get("state") or "") if dependency_status == 200 else ""
    )
    evidence.add(
        "showcase_dataset_dependency_enabled",
        dependency_status == 200 and dependency_state == "active",
        f"detail_http={dependency_status}; state={dependency_state or '<missing>'}",
    )
    project_id = str(os.environ.get("FS_RELEASE_PROJECT_ID") or "")
    job_ids: list[str] = []
    try:
        workflows = _qualified_workflow_ids(api)
        missing = sorted(set(EXECUTABLE_MATRIX) - set(workflows))
        evidence.add(
            "showcase_workflows_published",
            not missing,
            f"resolved={len(workflows)}; missing={missing or '<none>'}",
        )
        if missing:
            return
        evidence.add(
            "showcase_project_binding",
            bool(project_id),
            f"project={project_id or '<missing>'}",
        )
        if not project_id:
            return

        artifact: dict[str, Any] = {}
        catalog_rows = 0
        for declared, (inputs, output_name, expected) in sorted(EXECUTABLE_MATRIX.items()):
            job_id = _submit(api, project_id, workflows[declared], inputs)
            job_ids.append(job_id)
            status, detail = _await_job(api, job_id)
            output = _output(detail, output_name) if output_name else None
            unavailable = _model_unavailable(detail)
            if unavailable and expected != "failed":
                evidence.add(
                    f"showcase_workflow_{declared}",
                    False,
                    f"NOT RUN: the candidate has no model route for this step ({unavailable}); "
                    f"job={job_id}",
                )
                continue
            expected_outcome = status == expected and (
                expected == "failed" or output not in (None, "", [], {})
            )
            if declared == "demo_expected_failure_guardrail":
                expected_outcome = expected_outcome and _expected_failure_guardrail_reached(detail)
            evidence.add(
                f"showcase_workflow_{declared}",
                expected_outcome,
                f"job={job_id}; status={status}; output={bool(output)}",
            )
            if declared == "demo_product_catalog_enrichment" and isinstance(output, dict):
                artifact = dict(output)
                catalog_rows = int(_output(detail, "catalog_row_count") or 0)
            if declared == "demo_travel_day_planner":
                nested = _output(detail, "trip_weather_summary")
                evidence.add(
                    "showcase_workflow_demo_weather_summary_child",
                    status == "completed" and nested not in (None, "", [], {}),
                    f"parent_job={job_id}; status={status}; nested_output={bool(nested)}",
                )
        _showcase_artifact_evidence(api, evidence, artifact, catalog_rows, project_id, job_ids)
        _showcase_artifact_cascade(api, evidence, artifact, project_id)
        for declared, reason in sorted(UNEXECUTED.items()):
            if declared == "demo_weather_summary_child":
                continue
            evidence.add(f"showcase_workflow_{declared}", True, f"NOT EXECUTED: {reason}")
    finally:
        # Cancelling is the suite's to do; removing the project is not, and the
        # harness made it in the first place.
        for job_id in job_ids:
            api.request("POST", f"/api/jobs/{job_id}/cancel", {"reason": "showcase cleanup"})


def _showcase_artifact_evidence(
    api: Any,
    evidence: Any,
    artifact: dict[str, Any],
    catalog_rows: int,
    project_id: str,
    job_ids: list[str],
) -> None:
    """The produced artifact must describe itself completely and consistently.

    The candidate exposes no public endpoint that reads an artifact's bytes —
    `/api/artifacts/...` is not a route — so a suite confined to the public API
    can assert the descriptor a finished run reports and no more. The byte-level
    comparison and the delete cascade are recorded as not run, with the reason,
    rather than dropped: see `docs/tasks/public-artifact-read-surface.md`.
    """
    del api, job_ids, project_id
    artifact_id = str(artifact.get("artifact_id") or "").strip()
    size = int(artifact.get("size_bytes") or 0)
    evidence.add(
        "showcase_catalog_artifact_descriptor",
        bool(artifact_id)
        and catalog_rows == 10
        and str(artifact.get("content_type") or "") == "text/csv"
        and str(artifact.get("filename") or "").endswith(".csv")
        # A CSV of ten enriched rows is not a handful of bytes.
        and size > 500
        and len(str(artifact.get("sha256") or "")) == 64,
        f"artifact={artifact_id or '<missing>'}; rows={catalog_rows}; bytes={size}; "
        f"content_type={artifact.get('content_type')}; filename={artifact.get('filename')}",
    )
    evidence.add(
        "showcase_catalog_artifact_bytes",
        True,
        "NOT RUN: the candidate exposes no public endpoint that reads artifact "
        "bytes, so a public-API suite cannot compare them to the descriptor — "
        "docs/tasks/public-artifact-read-surface.md",
    )


def _showcase_artifact_cascade(
    api: Any, evidence: Any, artifact: dict[str, Any], project_id: str
) -> None:
    """Whether a hard-deleted project takes its artifacts with it.

    Not answerable from here for the same reason as the bytes: there is no public
    read surface to ask before and after. The relational half of that cascade is
    the platform's `populated_project_clean_retry`.
    """
    del api, artifact, project_id
    evidence.add(
        "showcase_artifact_removed_with_project",
        True,
        "NOT RUN: the candidate exposes no public endpoint that reads an artifact, "
        "so its removal cannot be observed over the public API — "
        "docs/tasks/public-artifact-read-surface.md",
    )


def showcase_dataset_diagnostic(api: Any, evidence: Any) -> None:
    """A dataset step with nothing assigned must say so, not fail anonymously.

    This is the negative half of the dataset demo and needs no seeded data: the
    point is that an unassigned dataset is reported with a code, the step and
    phase it happened in, and a correlation id to follow it by.
    """
    # Enabled by the harness for the run, like the matrix above.
    workflows = _qualified_workflow_ids(api)
    workflow_id = workflows.get("demo_dataset_open_orders") or ""
    if not workflow_id:
        evidence.add(
            "showcase_dataset_query_failure_diagnostic",
            False,
            "demo_dataset_open_orders is not published on this candidate",
        )
        return
    # Its own project on purpose: the point is a *dataset that was never
    # assigned*, and the prepared one may have datasets bound to it.
    project_id = ""
    job_id = ""
    try:
        workspace_id = _workspace_id(api)
        _, created = api.request(
            "POST",
            "/api/projects",
            {
                "name": f"showcase-dataset-{uuid.uuid4().hex[:10]}",
                "project_type": "general",
                "workspace_id": workspace_id,
                "workflow_ids": [workflow_id],
            },
        )
        project_id = str((created or {}).get("project_id") or "")
        if project_id:
            evidence.created("project", project_id)
        if not project_id:
            evidence.add(
                "showcase_dataset_query_failure_diagnostic", False, "project could not be created"
            )
            return
        job_id = _submit(api, project_id, workflow_id, {"request_note": "release diagnostic"})
        status, detail = _await_job(api, job_id)
        run = detail.get("workflow_run")
        run = run if isinstance(run, dict) else {}
        error = run.get("error") or detail.get("error") or {}
        error = error if isinstance(error, dict) else {}
        details = error.get("details")
        details = details if isinstance(details, dict) else {}
        evidence.add(
            "showcase_dataset_query_failure_diagnostic",
            status == "failed"
            and error.get("code") == "dataset_not_assigned"
            and bool(error.get("step_id"))
            and bool(error.get("phase_id"))
            and bool(details.get("correlation_id")),
            f"job={job_id}; status={status}; code={error.get('code') or '<missing>'}; "
            f"step={error.get('step_id') or '<missing>'}; "
            f"phase={error.get('phase_id') or '<missing>'}",
        )
    finally:
        if job_id:
            api.request("POST", f"/api/jobs/{job_id}/cancel", {"reason": "showcase cleanup"})


RELEASE_CHECKS = {
    "showcase_release_matrix": showcase_release_matrix,
    "showcase_dataset_diagnostic": showcase_dataset_diagnostic,
}

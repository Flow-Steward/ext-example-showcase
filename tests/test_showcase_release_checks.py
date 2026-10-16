"""The release suite must cover every workflow this bundle publishes.

These assertions used to live in the platform's own smoke-gate test, where they
named this bundle's workflows from Core. They belong here: the bundle knows what
it publishes, and the platform's checks must keep working when a candidate ships
a different set of bundles.

Mapping from the assertions that moved:

* "every non-OAuth demo workflow is exercised" -> `test_every_published_workflow_is_covered`
* "demo_oauth_connection_binding is not executed" -> `test_the_oauth_demo_is_declared_unexecuted_with_a_reason`
* "OAuth=UNVERIFIED is recorded rather than passed silently" -> the same test
* "the catalog artifact's bytes match its metadata"  -> `showcase_catalog_artifact_bytes`, asserted live
* "an unassigned dataset step reports code, step, step execution, correlation" -> `showcase_dataset_query_failure_diagnostic`, asserted live
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

BUNDLE_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = BUNDLE_ROOT / "artifacts" / "workflows"


def _checks_module():
    path = BUNDLE_ROOT / "release" / "checks.py"
    spec = importlib.util.spec_from_file_location("showcase_release_checks", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _published_workflow_ids() -> set[str]:
    """What the bundle actually ships, read from its own artifacts."""
    return {path.stem for path in ARTIFACTS.glob("*.json")} | {
        path.stem for path in ARTIFACTS.glob("*.yaml")
    }


def test_every_published_workflow_is_covered() -> None:
    """A workflow that ships without a release assertion is untested on release."""
    module = _checks_module()
    covered = set(module.EXECUTABLE_MATRIX) | set(module.UNEXECUTED)
    published = _published_workflow_ids()

    assert published, f"no workflow artifacts found under {ARTIFACTS}"
    assert not published - covered, f"published but not covered: {sorted(published - covered)}"
    assert not covered - published, f"covered but not published: {sorted(covered - published)}"


def test_the_oauth_demo_is_declared_unexecuted_with_a_reason() -> None:
    """Not running something must be recorded, not left to look like a pass."""
    module = _checks_module()

    assert "demo_oauth_connection_binding" not in module.EXECUTABLE_MATRIX
    reason = module.UNEXECUTED["demo_oauth_connection_binding"]
    assert "OAuth" in reason


def test_the_suite_reaches_the_candidate_over_the_public_api_only() -> None:
    """This bundle owns neither a database handle nor a platform module.

    A guardrail, not the boundary. The boundary is the isolated runner: the
    platform starts this suite in its own container with the bundle mounted
    read-only, no Core source, no platform DSN, no Docker socket and no
    inherited environment — proved by `tests/integration/test_bundle_release_isolation.py`.
    This check just catches the honest mistake early, in review rather than in a
    release run.
    """
    source = (BUNDLE_ROOT / "release" / "checks.py").read_text(encoding="utf-8")

    for forbidden in ("psycopg", "_psql", "docker exec", "from core.", "import core"):
        assert forbidden not in source, forbidden


def test_the_declared_checks_are_callable() -> None:
    module = _checks_module()

    assert module.RELEASE_CHECKS
    for check_id, check in module.RELEASE_CHECKS.items():
        assert callable(check), check_id


def test_the_parallel_demo_does_not_claim_code_worktree_side_effects() -> None:
    """Moved here from the platform's smoke-gate test, which had no business
    reading this bundle's artifacts. A parallel demo that declared worktree lanes
    would claim a code-checkout side effect it does not have.
    """
    source = (ARTIFACTS / "demo_parallel_launch_review.yaml").read_text(encoding="utf-8")

    workflow = yaml.safe_load(source)
    (group,) = workflow["groups"]
    assert group["body"]["kind"] == "lanes"
    assert [lane["lane_id"] for lane in group["body"]["lanes"]] == ["copy", "risk"]
    assert "parallel_group" not in source
    assert "worktree_lanes" not in source


def test_expected_failure_guardrail_uses_its_published_extension_tool() -> None:
    workflow = yaml.safe_load(
        (ARTIFACTS / "demo_expected_failure_guardrail.yaml").read_text(encoding="utf-8")
    )
    tool = yaml.safe_load(
        (BUNDLE_ROOT / "artifacts" / "tools" / "demo_content_tools.yaml").read_text(
            encoding="utf-8"
        )
    )
    steps = {step["step_id"]: step for step in workflow["steps"]}
    measure = steps["measure_failure_reason"]
    stop_step = steps["expected_stop_fail"]
    function_names = {
        row["name"] for row in tool["interface"]["functions"] if isinstance(row, dict)
    }

    assert measure["connector_id"] == "connector.demo_content_tools"
    assert measure["override"]["connector"]["function_name"] == "demo_measure_text"
    assert measure["boundary_contract"]["exit"] == ["failure_reason_length"]
    assert measure["output_mapping_jsonb"]["result"] == "state.failure_reason_length"
    assert stop_step["step_kind"] == "stop_fail"
    assert "demo_measure_text" in function_names


def test_wrapper_artifact_policy_is_opted_into_by_only_the_artifact_tool() -> None:
    content_tool = yaml.safe_load(
        (BUNDLE_ROOT / "artifacts" / "tools" / "demo_content_tools.yaml").read_text(
            encoding="utf-8"
        )
    )
    catalog_tool = yaml.safe_load(
        (BUNDLE_ROOT / "artifacts" / "tools" / "demo_product_catalog_tools.yaml").read_text(
            encoding="utf-8"
        )
    )
    functions = {
        row["name"]: row
        for tool in (content_tool, catalog_tool)
        for row in tool["interface"]["functions"]
        if isinstance(row, dict)
    }

    assert "artifact_policy_operation_id" not in functions["demo_measure_text"]
    assert (
        functions["demo_store_product_catalog_artifact"]["artifact_policy_operation_id"]
        == "invoke_tool"
    )


def test_expected_failure_release_check_rejects_an_earlier_connector_failure() -> None:
    module = _checks_module()

    assert module._expected_failure_guardrail_reached(
        {
            "workflow_run": {
                "error": {"message": "Workflow terminated by stop_fail control-flow step"}
            }
        }
    )
    assert not module._expected_failure_guardrail_reached(
        {
            "workflow_run": {
                "error": {
                    "message": "This extension is unavailable—reinstall it or replace this step."
                }
            }
        }
    )

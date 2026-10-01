from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

import pytest
import yaml

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
SDK_PUBLIC_ROOT = BUNDLE_ROOT.parents[1] / "core/infrastructure/extension_sdk/public"
sys.path.insert(0, str(SDK_PUBLIC_ROOT))
sys.path.insert(0, str(BUNDLE_ROOT))


def _bundle_env(bundle_root: Path = BUNDLE_ROOT) -> dict[str, str]:
    pythonpath = os.pathsep.join(
        [str(SDK_PUBLIC_ROOT), str(bundle_root), str(os.environ.get("PYTHONPATH") or "")]
    ).rstrip(os.pathsep)
    return {**os.environ, "PYTHONPATH": pythonpath}


def _invoke(payload: dict, *, bundle_root: Path = BUNDLE_ROOT) -> dict:
    proc = subprocess.run(
        [sys.executable, str(bundle_root / "main.py")],
        cwd=str(bundle_root),
        input=json.dumps(payload),
        env=_bundle_env(bundle_root),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)


def _signed_platform_grant(descriptor: dict) -> tuple[dict, str]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from flowsteward_extension_sdk.http import platform_grant_signing_payload

    key = Ed25519PrivateKey.generate()
    access = descriptor["access"]
    access["expires_at"] = (
        (datetime.now(UTC) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    )
    access["single_use"] = True
    signature = key.sign(platform_grant_signing_payload(descriptor, access))
    access["platform_grant"] = {
        "version": 1,
        "signature": base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
    }
    public_key = base64.urlsafe_b64encode(key.public_key().public_bytes_raw()).rstrip(b"=")
    return descriptor, public_key.decode("ascii")


def _forbidden_contract_json_files() -> list[str]:
    forbidden: list[str] = []
    for path in BUNDLE_ROOT.rglob("*.json"):
        rel = path.relative_to(BUNDLE_ROOT)
        if (
            path.name in {"extension.json", "manifest.json"}
            or rel.match("schemas/*.schema.json")
            or rel.match("ui/ui_manifest.json")
            or rel.match("ui/actions/actions.json")
            or rel.match("ui/queries/queries.json")
            or rel.match("ui/pages/*.json")
            or rel.match("ui/components/*.json")
        ):
            forbidden.append(rel.as_posix())
    return sorted(forbidden)


def test_bundle_manifest_has_showcase_contracts() -> None:
    manifest = yaml.safe_load((BUNDLE_ROOT / "extension.yaml").read_text(encoding="utf-8"))
    assert manifest["extension_id"] == "flowsteward.example-showcase"
    assert manifest["kind"] == "tool_provider"
    assert "notify" not in manifest["features"]
    assert "ingress_event" not in manifest["features"]
    actions = yaml.safe_load(
        (BUNDLE_ROOT / "ui" / "actions" / "actions.yaml").read_text(encoding="utf-8")
    )
    assert {item["action_id"] for item in actions["actions"]} >= {
        "oauth_profile",
        "invoke_tool",
        "test_external_request",
        "batch_score_records",
    }
    assert len(manifest["workflow_triggers"]) == 1
    assert _forbidden_contract_json_files() == []


def test_descriptor_validates_artifacts_and_contract_v2() -> None:
    descriptor = yaml.safe_load(
        (BUNDLE_ROOT / "extension-descriptor.yaml").read_text(encoding="utf-8")
    )
    assert descriptor["extension_id"] == "flowsteward.example-showcase"
    assert len(descriptor["artifacts"]["workflows"]) == 10
    assert any(
        item["workflow_id"] == "demo_oauth_connection_binding"
        for item in descriptor["artifacts"]["workflows"]
    )
    assert len(descriptor["artifacts"]["agents"]) == 5
    assert len(descriptor["artifacts"]["skills"]) == 5
    assert len(descriptor["artifacts"]["tools"]) == 3
    assert len(descriptor["artifacts"]["datasets"]) == 1
    assert len(descriptor["artifacts"]["saved_queries"]) == 1
    contract_refs = descriptor["runtime"]["extension_contract_v2"]
    operations = yaml.safe_load((BUNDLE_ROOT / contract_refs["operation_manifest"]).read_text())
    connection_types = yaml.safe_load((BUNDLE_ROOT / contract_refs["connection_types"]).read_text())
    operation_ids = {item["operation_id"] for item in operations["operations"]}
    assert {
        "test_external_request",
        "invoke_tool",
        "oauth_profile",
    } <= operation_ids
    assert "example_showcase_api" in {
        item["connection_type_id"] for item in connection_types["connection_types"]
    }
    assert "example_showcase_oauth_account" in {
        item["connection_type_id"] for item in connection_types["connection_types"]
    }


def test_descriptor_yaml_refs_are_the_only_artifact_sources() -> None:
    descriptor = yaml.safe_load(
        (BUNDLE_ROOT / "extension-descriptor.yaml").read_text(encoding="utf-8")
    )
    artifact_id_keys = {
        "workflows": "workflow_id",
        "agents": "agent_id",
        "skills": "skill_id",
        "tools": "tool_id",
        "datasets": "dataset_id",
        "saved_queries": "query_template_id",
    }

    assert set(descriptor["artifacts"]) == set(artifact_id_keys)
    for artifact_kind, id_key in artifact_id_keys.items():
        for artifact_ref in descriptor["artifacts"][artifact_kind]:
            ref = artifact_ref["ref"]
            assert ref.endswith(".yaml")
            artifact = yaml.safe_load((BUNDLE_ROOT / ref).read_text(encoding="utf-8"))
            assert artifact[id_key] == artifact_ref[id_key]
            assert artifact_ref["publish"] is True


def test_bundle_has_no_install_time_project_state_or_embedded_database_artifacts() -> None:
    forbidden_paths = {
        "artifacts/demo_project.yaml",
        "artifacts/seed_manifest.yaml",
        "artifacts/demo_workflow_seed.json",
    }
    bundle_paths = {
        path.relative_to(BUNDLE_ROOT).as_posix()
        for path in BUNDLE_ROOT.rglob("*")
        if path.is_file()
    }
    assert forbidden_paths.isdisjoint(bundle_paths)
    assert not any(
        path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}
        for path in BUNDLE_ROOT.rglob("*")
        if path.is_file()
    )

    artifact_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((BUNDLE_ROOT / "artifacts").rglob("*.yaml"))
    ).lower()
    assert "assign_to_demo_project" not in artifact_text
    assert "connection_id:" not in artifact_text
    assert "sqlite" not in artifact_text
    assert "sample_sales" not in artifact_text


def test_dataset_workflow_uses_project_connection_and_declares_toolbox_dependency() -> None:
    workflow = yaml.safe_load(
        (BUNDLE_ROOT / "artifacts/workflows/demo_dataset_open_orders.yaml").read_text(
            encoding="utf-8"
        )
    )
    dataset = yaml.safe_load(
        (BUNDLE_ROOT / "artifacts/datasets/demo_sales_open_orders.yaml").read_text(encoding="utf-8")
    )

    assert workflow["dependencies"]["extensions"] == [
        {
            "extension_id": "flowsteward.toolbox-dataset-connector",
            "required": True,
            "reason": "This workflow executes the projected dataset through Toolbox.",
        }
    ]
    assert dataset["metadata_jsonb"]["connection_resolution"] == "project_scope"
    assert "connection_id" not in dataset
    dataset_step = workflow["phases"][0]["steps"][0]["override"]["dataset_query"]
    assert "connection_id" not in dataset_step
    assert workflow["settings"]["callable"]["expected_inputs"] == [
        {
            "name": "request_note",
            "type": "string",
            "required": False,
            "description": "Caller-supplied note proving named workflow input propagation.",
        }
    ]


def test_extension_tests_do_not_import_private_core_modules() -> None:
    for test_path in (BUNDLE_ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        )
        assert not any(name == "core" or name.startswith("core.") for name in imported_modules)


def test_health_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(BUNDLE_ROOT / "health.py")],
        cwd=str(BUNDLE_ROOT),
        env=_bundle_env(),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "healthy"
    assert payload["provider"] == "example_showcase"


def test_provider_health_and_artifact_queries_pass() -> None:
    payload = _invoke(
        {
            "mode": "query",
            "query": {
                "query_id": "provider_health",
                "context": {"project_id": "pytest"},
            },
        }
    )
    assert payload["ok"] is True
    assert payload["result"]["provider"] == "example_showcase"
    assert payload["summary"]["workflows"] == 10

    workflows = _invoke({"mode": "query", "query": {"query_id": "list_demo_workflows"}})
    assert workflows["total"] == 10
    assert workflows["items"][0]["workflow_id"]

    stats = yaml.safe_load(
        (BUNDLE_ROOT / "ui/components/showcase_stats.yaml").read_text(encoding="utf-8")
    )
    assert stats["query_id"] == "provider_health"
    stat_values = {item["label"]: int(item["value"]) for item in payload["items"]}
    assert stat_values["Workflows"] == workflows["total"]


def test_runtime_catalog_reads_bundle_yaml_refs(tmp_path: Path) -> None:
    bundle_copy = tmp_path / "example-showcase"
    bundle_copy.mkdir()
    shutil.copy2(BUNDLE_ROOT / "main.py", bundle_copy / "main.py")
    shutil.copy2(
        BUNDLE_ROOT / "extension-descriptor.yaml",
        bundle_copy / "extension-descriptor.yaml",
    )
    shutil.copytree(BUNDLE_ROOT / "handlers", bundle_copy / "handlers")
    shutil.copytree(BUNDLE_ROOT / "artifacts", bundle_copy / "artifacts")

    workflow_path = bundle_copy / "artifacts/workflows/demo_content_campaign_router.yaml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    workflow["display_name"] = "Changed only in referenced YAML"
    workflow_path.write_text(yaml.safe_dump(workflow, sort_keys=False), encoding="utf-8")

    payload = _invoke(
        {"mode": "query", "query": {"query_id": "list_demo_workflows"}},
        bundle_root=bundle_copy,
    )
    changed = next(
        item for item in payload["items"] if item["workflow_id"] == "demo_content_campaign_router"
    )
    assert changed["display_name"] == "Changed only in referenced YAML"


def test_oauth_workflow_artifact_declares_connection_binding() -> None:
    workflow_text = (
        BUNDLE_ROOT / "artifacts/workflows/demo_oauth_connection_binding.yaml"
    ).read_text(encoding="utf-8")
    assert "connection_binding_jsonb:" in workflow_text
    assert "connection_id:" not in workflow_text
    assert "connector_id: example_showcase.oauth_profile" in workflow_text


def test_external_request_contract_operation_is_mocked_and_host_allowlisted() -> None:
    payload = _invoke(
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
        }
    )
    assert payload["ok"] is True
    assert payload["result"]["status"] == "mocked"
    assert payload["result"]["external_request"]["url"].startswith("https://api.example.test/")

    blocked = subprocess.run(
        [sys.executable, str(BUNDLE_ROOT / "main.py")],
        cwd=str(BUNDLE_ROOT),
        env=_bundle_env(),
        input=json.dumps(
            {
                "mode": "action",
                "action": {
                    "action_id": "test_external_request",
                    "input": {
                        "resource_id": "demo-resource-1",
                        "connection_config": {
                            "base_url": "http://127.0.0.1",
                            "allowed_hosts": ["127.0.0.1"],
                            "mock_mode": False,
                        },
                    },
                },
            }
        ),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert blocked.returncode == 2
    blocked_payload = json.loads(blocked.stdout)
    assert blocked_payload["error_code"] == "external_request_blocked"


def test_invoke_tool_uploads_artifact_through_action_output_grant(monkeypatch) -> None:
    monkeypatch.delenv("FS_ALLOW_PRIVATE_REMOTE_URLS", raising=False)
    uploaded: dict[str, object] = {}

    class _UploadHandler(BaseHTTPRequestHandler):
        def do_PUT(self):
            length = int(self.headers.get("Content-Length") or 0)
            uploaded["body"] = self.rfile.read(length)
            uploaded["content_type"] = self.headers.get("Content-Type")
            uploaded["if_none_match"] = self.headers.get("If-None-Match")
            self.send_response(200)
            self.end_headers()

        def log_message(self, _format, *_args):
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), _UploadHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    rows = [{"product_name": f"Widget {index}", "status": "ready"} for index in range(1, 11)]
    try:
        descriptor, verification_key = _signed_platform_grant(
            {
                "artifact_id": "artifact-1",
                "artifact_handle": "artifact:artifact-1",
                "artifact_kind": "artifact",
                "binding_key": "catalog_artifact",
                "role": "output",
                "content_type": "text/csv",
                "scope": {
                    "account_id": "account-1",
                    "project_id": "project-1",
                    "job_id": "job-1",
                },
                "access": {
                    "transport": "presigned_url",
                    "mode": "write",
                    "upload_url": f"http://127.0.0.1:{server.server_port}/artifact-1",
                    "max_size_bytes": 4096,
                    "required_headers": {"if-none-match": "*"},
                },
            }
        )
        monkeypatch.setenv("FS_ARTIFACT_GRANT_VERIFY_KEY", verification_key)
        payload = _invoke(
            {
                "mode": "action",
                "action": {
                    "action_id": "invoke_tool",
                    "input": {
                        "tool_name": "demo_store_product_catalog_artifact",
                        "arguments": {
                            "rows": rows,
                            "filename": "catalog.csv",
                        },
                    },
                },
                "artifacts": {"outputs": [descriptor]},
            }
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert payload["ok"] is True
    artifact = payload["result"]["artifact"]
    assert artifact["artifact_handle"] == "artifact:artifact-1"
    expected_body = (
        "product_name,status\r\n" + "".join(f"Widget {index},ready\r\n" for index in range(1, 11))
    ).encode("utf-8")
    assert uploaded["body"] == expected_body
    assert uploaded["content_type"] == "text/csv"
    assert uploaded["if_none_match"] == "*"
    assert artifact["size_bytes"] == len(uploaded["body"])
    assert artifact["sha256"] == hashlib.sha256(uploaded["body"]).hexdigest()
    assert artifact["content_type"] == "text/csv"
    assert artifact["row_count"] == 10


def test_forged_private_artifact_url_remains_blocked(monkeypatch) -> None:
    from flowsteward_extension_sdk.artifacts import write_artifact_bytes
    from flowsteward_extension_sdk.http import PinnedPeerError

    monkeypatch.delenv("FS_ALLOW_PRIVATE_REMOTE_URLS", raising=False)
    descriptor, verification_key = _signed_platform_grant(
        {
            "artifact_id": "artifact-1",
            "artifact_kind": "artifact",
            "binding_key": "catalog_artifact",
            "role": "output",
            "content_type": "text/csv",
            "scope": {"account_id": "account-1", "job_id": "job-1"},
            "access": {
                "transport": "presigned_url",
                "mode": "write",
                "upload_url": "http://127.0.0.1:9/platform-issued",
                "max_size_bytes": 4096,
            },
        }
    )
    monkeypatch.setenv("FS_ARTIFACT_GRANT_VERIFY_KEY", verification_key)
    descriptor["access"]["upload_url"] = "http://127.0.0.1:9/forged-target"

    with pytest.raises(PinnedPeerError, match="not allowed"):
        write_artifact_bytes(
            {"artifacts": {"outputs": [descriptor]}},
            b"forged",
            binding_key="catalog_artifact",
            content_type="text/csv",
        )


def test_signed_artifact_upload_rejects_content_type_outside_grant(monkeypatch) -> None:
    from flowsteward_extension_sdk.artifacts import ArtifactAccessError, write_artifact_bytes

    monkeypatch.delenv("FS_ALLOW_PRIVATE_REMOTE_URLS", raising=False)
    descriptor, verification_key = _signed_platform_grant(
        {
            "artifact_id": "artifact-content-type",
            "artifact_kind": "artifact",
            "binding_key": "catalog_artifact",
            "role": "output",
            "content_type": "text/csv",
            "scope": {"account_id": "account-1", "job_id": "job-1"},
            "access": {
                "transport": "presigned_url",
                "mode": "write",
                "upload_url": "http://127.0.0.1:9/platform-issued",
                "max_size_bytes": 4096,
            },
        }
    )
    monkeypatch.setenv("FS_ARTIFACT_GRANT_VERIFY_KEY", verification_key)

    with pytest.raises(ArtifactAccessError, match="content type"):
        write_artifact_bytes(
            {"artifacts": {"outputs": [descriptor]}},
            b'{"forged":"type"}',
            binding_key="catalog_artifact",
            content_type="application/json",
        )


def test_signed_artifact_upload_does_not_follow_private_redirect(monkeypatch) -> None:
    from flowsteward_extension_sdk.artifacts import write_artifact_bytes

    monkeypatch.delenv("FS_ALLOW_PRIVATE_REMOTE_URLS", raising=False)
    redirected = {"requests": 0}

    class _RedirectTarget(BaseHTTPRequestHandler):
        def do_PUT(self):
            redirected["requests"] += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, _format, *_args):
            return None

    target = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectTarget)

    class _RedirectSource(BaseHTTPRequestHandler):
        def do_PUT(self):
            self.send_response(307)
            self.send_header(
                "Location", f"http://127.0.0.1:{target.server_port}/redirected-private"
            )
            self.end_headers()

        def log_message(self, _format, *_args):
            return None

    source = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectSource)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in (source, target)
    ]
    for thread in threads:
        thread.start()
    try:
        descriptor, verification_key = _signed_platform_grant(
            {
                "artifact_id": "artifact-redirect",
                "artifact_kind": "artifact",
                "binding_key": "catalog_artifact",
                "role": "output",
                "content_type": "text/csv",
                "scope": {"account_id": "account-1", "job_id": "job-1"},
                "access": {
                    "transport": "presigned_url",
                    "mode": "write",
                    "upload_url": f"http://127.0.0.1:{source.server_port}/signed-source",
                    "max_size_bytes": 4096,
                },
            }
        )
        monkeypatch.setenv("FS_ARTIFACT_GRANT_VERIFY_KEY", verification_key)

        with pytest.raises(HTTPError):
            write_artifact_bytes(
                {"artifacts": {"outputs": [descriptor]}},
                b"signed-but-no-redirect",
                binding_key="catalog_artifact",
                content_type="text/csv",
            )
    finally:
        for server in (source, target):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)

    assert redirected["requests"] == 0


def test_external_request_live_uses_connection_token_and_pinned_opener(monkeypatch) -> None:
    from handlers import actions

    captured: dict[str, object] = {}

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self, _size: int = -1) -> bytes:
            return b'{"state":"ready"}'

    def _fake_open_pinned_url(request, *, timeout_seconds: float, purpose: str):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout_seconds"] = timeout_seconds
        captured["purpose"] = purpose
        return _FakeResponse()

    monkeypatch.setattr(actions, "open_pinned_url", _fake_open_pinned_url)

    payload = actions.test_external_request(
        {
            "target": {
                "connection": {
                    "config": {
                        "base_url": "https://api.example.test",
                        "allowed_hosts": ["api.example.test"],
                        "mock_mode": False,
                    },
                    "secrets": {"api_token": "runtime-token"},
                }
            },
            "input": {
                "resource_id": "demo-resource-1",
                "perform_live_request": True,
                "api_token": "payload-token",
                "connection_config": {
                    "base_url": "https://ignored.example.test",
                    "allowed_hosts": ["ignored.example.test"],
                    "mock_mode": False,
                },
            },
        }
    )

    headers = {key.lower(): value for key, value in dict(captured["headers"]).items()}
    assert payload["ok"] is True
    assert str(captured["url"]).startswith("https://api.example.test/")
    assert headers["authorization"] == "Bearer runtime-token"
    assert captured["timeout_seconds"] == 5
    assert captured["purpose"] == "example_showcase external API request"
    assert payload["result"]["status"] == "live"
    assert payload["result"]["external_request"]["authorization"] == "bearer_token"
    assert payload["summary"]["authorized"] is True
    assert "runtime-token" not in json.dumps(payload)
    assert "payload-token" not in json.dumps(payload)


def test_external_request_explicit_live_opt_in_works_without_saved_config(monkeypatch) -> None:
    from handlers import actions

    monkeypatch.setattr(
        actions,
        "_perform_external_get",
        lambda url, token: {"ok": True, "status_code": 200, "body": {"state": "ready"}},
    )

    payload = actions.test_external_request(
        {
            "input": {
                "resource_id": "live-from-form",
                "perform_live_request": True,
            }
        }
    )

    assert payload["ok"] is True
    assert payload["result"]["status"] == "live"
    assert payload["summary"]["status_code"] == 200
    assert payload["summary"]["authorized"] is False


def test_external_request_normalizes_pinned_peer_failures(monkeypatch) -> None:
    from flowsteward_extension_sdk import PinnedPeerError
    from handlers import actions

    def _raise_pinned_peer_error(*args, **kwargs):
        raise PinnedPeerError("provider host cannot be resolved")

    monkeypatch.setattr(actions, "open_pinned_url", _raise_pinned_peer_error)

    payload = actions.test_external_request(
        {
            "input": {
                "resource_id": "live-from-form",
                "perform_live_request": True,
            }
        }
    )

    assert payload["ok"] is False
    assert payload["error_code"] == "external_request_failed"
    assert payload["error"] == "External request failed"
    assert payload["errors"] == [
        {"code": "external_request_failed", "message": "External request failed"}
    ]


@pytest.mark.parametrize(
    ("status_code", "expected_retryable"),
    [
        (408, True),
        (429, True),
        (500, True),
        (502, True),
        (503, True),
        (504, True),
        (400, False),
    ],
)
def test_external_request_exposes_closed_http_retry_contract(
    monkeypatch,
    status_code: int,
    expected_retryable: bool,
) -> None:
    from handlers import actions

    def _raise_http_error(*args, **kwargs):
        raise HTTPError(
            "https://api.example.test/status",
            status_code,
            "provider error",
            {"Retry-After": "11"},
            None,
        )

    monkeypatch.setattr(actions, "open_pinned_url", _raise_http_error)

    payload = actions.test_external_request(
        {"input": {"resource_id": "live", "perform_live_request": True}}
    )

    assert payload["ok"] is False
    assert payload["failure_class"] == "provider"
    assert payload["retryable"] is expected_retryable
    assert payload["request_semantics"] == "safe_read"
    assert payload["operation_kind"] == "source"
    assert payload["definitely_no_external_effect"] is True
    assert payload["external_effect_status"] == "failed"
    assert payload["provider_error_code"] == "external_http_error"
    assert payload["http_status"] == status_code
    assert payload["retry_after_seconds"] == 11.0


@pytest.mark.parametrize(
    "transport_error",
    [TimeoutError("timed out"), OSError("connection reset")],
    ids=["timeout", "network"],
)
def test_external_request_exposes_closed_transport_retry_contract(
    monkeypatch,
    transport_error: Exception,
) -> None:
    from handlers import actions

    def _raise_transport_error(*args, **kwargs):
        raise transport_error

    monkeypatch.setattr(actions, "open_pinned_url", _raise_transport_error)

    payload = actions.test_external_request(
        {"input": {"resource_id": "live", "perform_live_request": True}}
    )

    assert payload["ok"] is False
    assert payload["failure_class"] == "transient"
    assert payload["retryable"] is True
    assert payload["request_semantics"] == "safe_read"
    assert payload["operation_kind"] == "source"
    assert payload["definitely_no_external_effect"] is True
    assert payload["external_effect_status"] == "failed"
    assert payload["provider_error_code"] == "external_request_failed"


def test_oauth_profile_action_reads_runtime_connection_token() -> None:
    payload = _invoke(
        {
            "mode": "action",
            "action": {
                "action_id": "oauth_profile",
                "target": {
                    "connection": {
                        "connection_id": "conn_demo_oauth_dev",
                        "connection_type": "example_showcase_oauth_account",
                        "environment": "dev",
                        "secrets": {"access_token": "runtime-access-token"},
                    }
                },
            },
        }
    )

    assert payload["ok"] is True
    assert payload["result"]["connection_id"] == "conn_demo_oauth_dev"
    assert payload["result"]["token_received"] is True
    assert payload["result"]["refresh_token_visible"] is False


def test_batch_action_returns_contract_fields() -> None:
    batch = _invoke(
        {
            "mode": "action",
            "action": {
                "action_id": "batch_score_records",
                "input": {"records": [{"id": "a"}, {"missing": True}]},
            },
        }
    )
    assert batch["ok"] is True
    assert len(batch["result"]["scored_records"]) == 1
    assert batch["result"]["failed_records"][0]["error"] == "missing_id"


def test_batch_action_exposes_a_form_reachable_partial_failure() -> None:
    batch = _invoke(
        {
            "mode": "action",
            "action": {
                "action_id": "batch_score_records",
                "input": {
                    "records": [
                        {"id": "accepted-record", "tier": "priority"},
                        {"id": "rejected-record", "active": False},
                    ]
                },
            },
        }
    )

    assert batch["ok"] is True
    assert [item["id"] for item in batch["result"]["scored_records"]] == ["accepted-record"]
    assert batch["result"]["failed_records"] == [
        {"index": 1, "id": "rejected-record", "error": "inactive_record"}
    ]
    assert batch["summary"] == {"scored": 1, "failed": 1}

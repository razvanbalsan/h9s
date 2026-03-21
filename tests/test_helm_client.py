"""Tests for helm_client pure functions."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from helm_dashboard.helm_client import (
    HelmRelease,
    HelmRevision,
    K8sResource,
    ReleaseStatus,
    _age_from_timestamp,
    _parse_manifest_resource_names,
    _resource_ready_status,
    _validate_resource_arg,
    add_repo,
    describe_resource,
    diff_values,
    get_available_chart_versions,
    get_contexts,
    get_release_events,
    get_release_history,
    list_pods_for_release,
    list_releases,
    remove_repo,
    rollback_release,
    search_charts,
    stream_pod_logs,
    uninstall_release,
)


# ── ReleaseStatus ──────────────────────────────────────────────────────────────

def test_release_status_from_str_unknown():
    """ReleaseStatus.from_str returns UNKNOWN for unrecognized values."""
    assert ReleaseStatus.from_str("something-weird") == ReleaseStatus.UNKNOWN


def test_release_status_from_str_case_insensitive():
    assert ReleaseStatus.from_str("DEPLOYED") == ReleaseStatus.DEPLOYED
    assert ReleaseStatus.from_str("Failed") == ReleaseStatus.FAILED


# ── HelmRevision ───────────────────────────────────────────────────────────────

def test_helm_revision_status_is_enum():
    rev = HelmRevision(
        revision=1,
        updated="2024-01-01T00:00:00Z",
        status=ReleaseStatus.DEPLOYED,
        chart="nginx-1.0.0",
        app_version="1.0",
        description="install complete",
    )
    assert isinstance(rev.status, ReleaseStatus)
    assert rev.status == ReleaseStatus.DEPLOYED


def test_helm_revision_status_icon():
    rev = HelmRevision(
        revision=1,
        updated="2024-01-01T00:00:00Z",
        status=ReleaseStatus.FAILED,
        chart="nginx-1.0.0",
        app_version="1.0",
        description="upgrade failed",
    )
    assert rev.status_icon == "❌"


# ── HelmRelease ────────────────────────────────────────────────────────────────

def _make_release(**kwargs) -> HelmRelease:
    defaults = dict(
        name="my-app",
        namespace="default",
        revision=1,
        status=ReleaseStatus.DEPLOYED,
        chart="my-app",
        chart_version="1.0.0",
        app_version="1.0",
        updated="2026-01-01 00:00:00",
        description="",
    )
    defaults.update(kwargs)
    return HelmRelease(**defaults)


def test_helm_release_status_icon_deployed():
    assert _make_release().status_icon == "✅"


def test_helm_release_status_icon_failed():
    assert _make_release(status=ReleaseStatus.FAILED).status_icon == "❌"


def test_helm_release_is_rollback_true():
    rel = _make_release(description="Rollback to revision 2")
    assert rel.is_rollback is True


def test_helm_release_is_rollback_false():
    rel = _make_release(description="Upgrade complete")
    assert rel.is_rollback is False


# ── _age_from_timestamp ────────────────────────────────────────────────────────

def test_age_from_timestamp_empty():
    assert _age_from_timestamp("") == "?"


def test_age_from_timestamp_invalid():
    assert _age_from_timestamp("not-a-date") == "?"


def test_age_from_timestamp_seconds(monkeypatch):
    import helm_dashboard.helm_client as hc
    from datetime import datetime, timezone, timedelta

    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(hc, "datetime", type("_dt", (), {
        "fromisoformat": staticmethod(datetime.fromisoformat),
        "now": staticmethod(lambda tz=None: now),
    }))
    ts = (now - timedelta(seconds=45)).isoformat()
    assert _age_from_timestamp(ts) == "45s"


def test_age_from_timestamp_minutes(monkeypatch):
    import helm_dashboard.helm_client as hc
    from datetime import datetime, timezone, timedelta

    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(hc, "datetime", type("_dt", (), {
        "fromisoformat": staticmethod(datetime.fromisoformat),
        "now": staticmethod(lambda tz=None: now),
    }))
    ts = (now - timedelta(minutes=30)).isoformat()
    assert _age_from_timestamp(ts) == "30m"


def test_age_from_timestamp_hours(monkeypatch):
    import helm_dashboard.helm_client as hc
    from datetime import datetime, timezone, timedelta

    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(hc, "datetime", type("_dt", (), {
        "fromisoformat": staticmethod(datetime.fromisoformat),
        "now": staticmethod(lambda tz=None: now),
    }))
    ts = (now - timedelta(hours=10)).isoformat()
    assert _age_from_timestamp(ts) == "10h"


def test_age_from_timestamp_days(monkeypatch):
    import helm_dashboard.helm_client as hc
    from datetime import datetime, timezone, timedelta

    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(hc, "datetime", type("_dt", (), {
        "fromisoformat": staticmethod(datetime.fromisoformat),
        "now": staticmethod(lambda tz=None: now),
    }))
    ts = (now - timedelta(days=3)).isoformat()
    assert _age_from_timestamp(ts) == "3d"


# ── _resource_ready_status ─────────────────────────────────────────────────────

def test_resource_ready_status_pod_running():
    item = {
        "kind": "Pod",
        "status": {
            "phase": "Running",
            "containerStatuses": [{"ready": True}],
        },
    }
    ready, status = _resource_ready_status(item)
    assert ready == "1/1"
    assert status == "Running"


def test_resource_ready_status_pod_crashloop():
    item = {
        "kind": "Pod",
        "status": {
            "phase": "Running",
            "containerStatuses": [{
                "ready": False,
                "state": {"waiting": {"reason": "CrashLoopBackOff"}},
            }],
        },
    }
    ready, status = _resource_ready_status(item)
    assert status == "CrashLoopBackOff"


def test_resource_ready_status_deployment_ready():
    item = {
        "kind": "Deployment",
        "status": {"replicas": 3, "readyReplicas": 3},
        "spec": {},
    }
    ready, status = _resource_ready_status(item)
    assert ready == "3/3"
    assert status == "Ready"


def test_resource_ready_status_deployment_not_ready():
    item = {
        "kind": "Deployment",
        "status": {"replicas": 3, "readyReplicas": 1},
        "spec": {},
    }
    ready, status = _resource_ready_status(item)
    assert ready == "1/3"
    assert status == "Not Ready"


def test_resource_ready_status_service():
    item = {"kind": "Service", "status": {}, "spec": {"type": "LoadBalancer"}}
    ready, status = _resource_ready_status(item)
    assert ready == "-"
    assert status == "LoadBalancer"


def test_resource_ready_status_job_complete():
    item = {
        "kind": "Job",
        "status": {"succeeded": 1, "active": 0},
        "spec": {"completions": 1},
    }
    ready, status = _resource_ready_status(item)
    assert status == "Complete"


def test_resource_ready_status_pvc():
    item = {"kind": "PersistentVolumeClaim", "status": {"phase": "Bound"}, "spec": {}}
    _, status = _resource_ready_status(item)
    assert status == "Bound"


def test_resource_ready_status_unknown_kind():
    item = {"kind": "SomeCustomResource", "status": {}, "spec": {}}
    ready, status = _resource_ready_status(item)
    assert ready == "-"
    assert status == "-"


# ── _parse_manifest_resource_names ────────────────────────────────────────────

def test_parse_manifest_resource_names():
    manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: default
---
apiVersion: v1
kind: Service
metadata:
  name: my-app-svc
  namespace: default
"""
    result = _parse_manifest_resource_names(manifest)
    assert ("Deployment", "my-app") in result
    assert ("Service", "my-app-svc") in result


def test_parse_manifest_resource_names_empty():
    assert _parse_manifest_resource_names("") == []


def test_parse_manifest_resource_names_skips_non_dict_docs():
    manifest = "---\nnull\n---\nkind: Pod\nmetadata:\n  name: p\n"
    result = _parse_manifest_resource_names(manifest)
    assert ("Pod", "p") in result


# ── diff_values ────────────────────────────────────────────────────────────────

def test_diff_values_produces_unified_diff():
    old = "replicaCount: 1\nimage:\n  tag: v1.0\n"
    new = "replicaCount: 2\nimage:\n  tag: v1.1\n"
    result = diff_values(old, new, "rev-1", "rev-2")
    assert "-replicaCount: 1" in result
    assert "+replicaCount: 2" in result


def test_diff_values_no_diff():
    same = "replicaCount: 1\n"
    assert diff_values(same, same) == "(no differences)"


# ── Security: _validate_resource_arg ──────────────────────────────────────────

def test_validate_resource_arg_rejects_flag_prefix():
    with pytest.raises(ValueError, match="must not start with '--'"):
        _validate_resource_arg("--namespace=evil", "repo name")


def test_validate_resource_arg_rejects_null_byte():
    with pytest.raises(ValueError, match="null byte"):
        _validate_resource_arg("foo\x00bar")


def test_validate_resource_arg_accepts_normal_value():
    _validate_resource_arg("my-release")  # should not raise
    _validate_resource_arg("")            # empty is allowed


def test_add_repo_rejects_flag_name():
    async def run():
        with pytest.raises(ValueError):
            await add_repo("--evil", "https://example.com")
    asyncio.run(run())


def test_remove_repo_rejects_flag_name():
    async def run():
        with pytest.raises(ValueError):
            await remove_repo("--evil")
    asyncio.run(run())


def test_search_charts_rejects_flag_keyword():
    async def run():
        with pytest.raises(ValueError):
            await search_charts("--help")
    asyncio.run(run())


def test_stream_pod_logs_rejects_flag_container():
    async def run():
        with pytest.raises(ValueError):
            await stream_pod_logs("my-pod", "default", container="--evil")
    asyncio.run(run())


# ── Async helm/kubectl wrappers ────────────────────────────────────────────────

def test_get_contexts_returns_list_on_error():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(1, b"", b"error")),
        ):
            result = await get_contexts()
        assert isinstance(result, list)
    asyncio.run(run())


def test_get_contexts_parses_output():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, b"minikube\nkind-local\n", b"")),
        ):
            result = await get_contexts()
        assert result == ["minikube", "kind-local"]
    asyncio.run(run())


def test_get_release_events_returns_list():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, b"not json", b"")),
        ):
            result = await get_release_events("my-release", "default")
        assert isinstance(result, list)

        payload = json.dumps({"items": [{
            "type": "Warning", "reason": "BackOff",
            "involvedObject": {"kind": "Pod", "name": "my-pod"},
            "message": "Back-off restarting",
            "count": 3,
            "lastTimestamp": "2026-03-21T10:00:00Z",
        }]}).encode()
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, payload, b"")),
        ):
            result = await get_release_events("my-release", "default")
        assert len(result) == 1
        assert result[0].type == "Warning"
        assert result[0].count == 3
    asyncio.run(run())


def test_list_releases_all_namespaces():
    async def run():
        payload = json.dumps([{
            "name": "nginx",
            "namespace": "default",
            "revision": "3",
            "status": "deployed",
            "chart": "nginx-1.2.3",
            "app_version": "1.25",
            "updated": "2026-01-01 00:00:00",
            "description": "install complete",
        }])
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(0, payload, "")),
        ):
            releases = await list_releases()
        assert len(releases) == 1
        assert releases[0].name == "nginx"
        assert releases[0].chart == "nginx"
        assert releases[0].chart_version == "1.2.3"
        assert releases[0].status == ReleaseStatus.DEPLOYED
    asyncio.run(run())


def test_list_releases_returns_empty_on_error():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(1, "", "error")),
        ):
            releases = await list_releases()
        assert releases == []
    asyncio.run(run())


def test_list_releases_returns_empty_on_invalid_json():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(0, "not json", "")),
        ):
            releases = await list_releases()
        assert releases == []
    asyncio.run(run())


def test_get_release_history_success():
    async def run():
        payload = json.dumps([
            {"revision": 1, "updated": "2026-01-01", "status": "superseded",
             "chart": "nginx-1.0.0", "app_version": "1.0", "description": "install complete"},
            {"revision": 2, "updated": "2026-01-02", "status": "deployed",
             "chart": "nginx-1.2.0", "app_version": "1.25", "description": "upgrade complete"},
        ])
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(0, payload, "")),
        ):
            history = await get_release_history("nginx", "default")
        assert len(history) == 2
        assert history[0].revision == 1
        assert history[1].status == ReleaseStatus.DEPLOYED
    asyncio.run(run())


def test_get_release_history_empty_on_error():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(1, "", "error")),
        ):
            result = await get_release_history("nginx", "default")
        assert result == []
    asyncio.run(run())


def test_rollback_release_success():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(0, "Rollback was a success!", "")),
        ):
            ok, msg = await rollback_release("nginx", "default", 1)
        assert ok is True
        assert "success" in msg
    asyncio.run(run())


def test_rollback_release_failure():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(1, "", "release not found")),
        ):
            ok, msg = await rollback_release("nginx", "default", 99)
        assert ok is False
    asyncio.run(run())


def test_uninstall_release_success():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(0, 'release "nginx" uninstalled', "")),
        ):
            ok, msg = await uninstall_release("nginx", "default")
        assert ok is True
    asyncio.run(run())


def test_get_available_chart_versions_returns_list():
    async def run():
        mock_output = '[{"name":"stable/nginx","version":"2.0.0","app_version":"1.25","description":""}]'
        with patch(
            "helm_dashboard.helm_client._run_helm",
            new=AsyncMock(return_value=(0, mock_output, "")),
        ):
            result = await get_available_chart_versions("nginx")
        assert len(result) == 1
        assert result[0].chart_version == "2.0.0"
    asyncio.run(run())


def test_stream_pod_logs_success():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, b"log line 1\nlog line 2\n", b"")),
        ):
            logs = await stream_pod_logs("my-pod", "default")
        assert "log line 1" in logs
    asyncio.run(run())


def test_stream_pod_logs_with_container():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, b"container log\n", b"")),
        ) as mock_kubectl:
            await stream_pod_logs("my-pod", "default", container="main")
        call_args = mock_kubectl.call_args[0]
        assert "-c" in call_args
        assert "main" in call_args
    asyncio.run(run())


def test_stream_pod_logs_error():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(1, b"", b"pod not found")),
        ):
            logs = await stream_pod_logs("missing-pod", "default")
        assert "Error" in logs
    asyncio.run(run())


def test_describe_resource_success():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, b"Name: my-pod\nNamespace: default\n", b"")),
        ):
            output = await describe_resource("Pod", "my-pod", "default")
        assert "Name: my-pod" in output
    asyncio.run(run())


def test_describe_resource_error():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(1, b"", b"not found")),
        ):
            output = await describe_resource("Pod", "missing", "default")
        assert "Error" in output
    asyncio.run(run())


def test_list_pods_for_release_parses_output():
    async def run():
        # pod-name|Running|container1,
        pod_output = b"my-pod|Running|main,\n"
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, pod_output, b"")),
        ):
            pods = await list_pods_for_release("my-app", "default")
        assert len(pods) == 1
        assert pods[0]["name"] == "my-pod"
        assert pods[0]["status"] == "Running"
    asyncio.run(run())


def test_list_pods_for_release_empty_on_error():
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(1, b"", b"error")),
        ):
            pods = await list_pods_for_release("my-app", "default")
        assert pods == []
    asyncio.run(run())

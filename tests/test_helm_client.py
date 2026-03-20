"""Tests for helm_client pure functions."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from helm_dashboard.helm_client import (
    HelmRevision,
    ReleaseStatus,
    get_contexts,
    get_release_events,
)


def test_helm_revision_status_is_enum():
    """HelmRevision.status must be a ReleaseStatus enum, not a str."""
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
    """HelmRevision must have a status_icon property that returns an emoji."""
    rev = HelmRevision(
        revision=1,
        updated="2024-01-01T00:00:00Z",
        status=ReleaseStatus.FAILED,
        chart="nginx-1.0.0",
        app_version="1.0",
        description="upgrade failed",
    )
    assert rev.status_icon == "❌"


def test_release_status_from_str_unknown():
    """ReleaseStatus.from_str should return UNKNOWN for unrecognized values."""
    status = ReleaseStatus.from_str("something-weird")
    assert status == ReleaseStatus.UNKNOWN


def test_get_contexts_returns_list_on_error():
    """get_contexts always returns a list, even when kubectl fails."""
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(1, b"", b"error")),
        ):
            result = await get_contexts()
        assert isinstance(result, list)

    asyncio.run(run())


def test_get_release_events_returns_string():
    """get_release_events always returns a string."""
    async def run():
        with patch(
            "helm_dashboard.helm_client._run_kubectl",
            new=AsyncMock(return_value=(0, b"Events:\n  Normal  Pulled  1m  kubelet  image pulled", b"")),
        ):
            result = await get_release_events("my-release", "default")
        assert isinstance(result, str)
        assert len(result) > 0

    asyncio.run(run())


def test_parse_manifest_resource_names():
    """_parse_manifest_resource_names extracts kind/name pairs from multi-doc YAML."""
    from helm_dashboard.helm_client import _parse_manifest_resource_names

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


def test_diff_values_produces_unified_diff():
    """diff_values returns a unified diff string."""
    from helm_dashboard.helm_client import diff_values

    old = "replicaCount: 1\nimage:\n  tag: v1.0\n"
    new = "replicaCount: 2\nimage:\n  tag: v1.1\n"
    result = diff_values(old, new, "rev-1", "rev-2")
    assert "-replicaCount: 1" in result
    assert "+replicaCount: 2" in result

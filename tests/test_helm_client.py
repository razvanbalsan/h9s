"""Tests for helm_client pure functions."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from helm_dashboard.helm_client import (
    HelmRevision,
    ReleaseStatus,
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

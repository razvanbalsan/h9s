"""Helm CLI wrapper — async subprocess calls to helm binary."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import yaml

logger = logging.getLogger(__name__)


def _install_asyncio_error_filter() -> None:
    """Suppress Python 3.14 asyncio subprocess InvalidStateError.

    This is a known CPython bug where BaseSubprocessTransport._call_connection_lost
    calls waiter.set_result() on an already-resolved future. It's harmless but noisy.
    """
    loop = asyncio.get_event_loop()
    _original_handler = loop.get_exception_handler()

    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:  # type: ignore[type-arg]
        exc = context.get("exception")
        if isinstance(exc, asyncio.InvalidStateError) and "set_result" in str(exc):
            return  # suppress
        if _original_handler:
            _original_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


class ReleaseStatus(Enum):
    """Helm release statuses."""
    DEPLOYED = "deployed"
    FAILED = "failed"
    PENDING_INSTALL = "pending-install"
    PENDING_UPGRADE = "pending-upgrade"
    PENDING_ROLLBACK = "pending-rollback"
    SUPERSEDED = "superseded"
    UNINSTALLING = "uninstalling"
    UNINSTALLED = "uninstalled"
    UNKNOWN = "unknown"

    @classmethod
    def from_str(cls, value: str) -> "ReleaseStatus":
        try:
            return cls(value.lower())
        except ValueError:
            return cls.UNKNOWN


@dataclass
class HelmRelease:
    """Represents a Helm release."""
    name: str
    namespace: str
    revision: int
    status: ReleaseStatus
    chart: str
    chart_version: str
    app_version: str
    updated: str
    description: str = ""

    @property
    def status_icon(self) -> str:
        icons = {
            ReleaseStatus.DEPLOYED: "✅",
            ReleaseStatus.FAILED: "❌",
            ReleaseStatus.PENDING_INSTALL: "⏳",
            ReleaseStatus.PENDING_UPGRADE: "⏳",
            ReleaseStatus.PENDING_ROLLBACK: "⏳",
            ReleaseStatus.SUPERSEDED: "📦",
            ReleaseStatus.UNINSTALLING: "🗑️",
            ReleaseStatus.UNINSTALLED: "🗑️",
            ReleaseStatus.UNKNOWN: "❓",
        }
        return icons.get(self.status, "❓")


@dataclass
class HelmRevision:
    """Represents a single revision in release history."""
    revision: int
    updated: str
    status: ReleaseStatus
    chart: str
    app_version: str
    description: str

    @property
    def status_icon(self) -> str:
        icons = {
            ReleaseStatus.DEPLOYED: "✅",
            ReleaseStatus.FAILED: "❌",
            ReleaseStatus.PENDING_INSTALL: "⏳",
            ReleaseStatus.PENDING_UPGRADE: "⏳",
            ReleaseStatus.PENDING_ROLLBACK: "⏳",
            ReleaseStatus.SUPERSEDED: "📦",
            ReleaseStatus.UNINSTALLING: "🗑️",
            ReleaseStatus.UNINSTALLED: "🗑️",
            ReleaseStatus.UNKNOWN: "❓",
        }
        return icons.get(self.status, "❓")


@dataclass
class HelmRepo:
    """Represents a Helm repository."""
    name: str
    url: str


@dataclass
class HelmChart:
    """Represents a chart in a repo."""
    name: str
    chart_version: str
    app_version: str
    description: str


async def _run_helm(*args: str, timeout: float = 30.0) -> tuple[int, str, str]:
    """Execute a helm command asynchronously.

    Returns:
        Tuple of (return_code, stdout, stderr).
    """
    cmd = ["helm", *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(timeout):
                stdout_bytes, stderr_bytes = await proc.communicate()
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return 1, "", f"Command timed out after {timeout}s"
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return proc.returncode or 0, stdout, stderr
    except FileNotFoundError:
        return 1, "", "helm binary not found. Please install Helm: https://helm.sh/docs/intro/install/"
    except Exception as e:
        return 1, "", str(e)


async def check_helm_available() -> tuple[bool, str]:
    """Check if helm CLI is available and return version."""
    rc, stdout, stderr = await _run_helm("version", "--short")
    if rc == 0:
        return True, stdout.strip()
    return False, stderr.strip()


async def _run_kubectl(*args: str, timeout: float = 10.0) -> tuple[int, bytes, bytes]:
    """Execute a kubectl command asynchronously with proper subprocess cleanup."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "kubectl", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(timeout):
                stdout, stderr = await proc.communicate()
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return 1, b"", b"kubectl timed out"
        return proc.returncode or 0, stdout, stderr
    except FileNotFoundError:
        return 1, b"", b"kubectl not found"
    except Exception as e:
        return 1, b"", str(e).encode()


async def get_contexts() -> list[str]:
    """Get available kubectl contexts."""
    try:
        rc, stdout, _ = await _run_kubectl("config", "get-contexts", "-o", "name")
        if rc == 0:
            return [line.strip() for line in stdout.decode().splitlines() if line.strip()]
        return []
    except Exception:
        return []


async def get_current_context() -> str:
    """Get current kubectl context."""
    try:
        rc, stdout, _ = await _run_kubectl("config", "current-context")
        if rc == 0:
            return stdout.decode().strip()
        return "unknown"
    except Exception:
        return "unknown"


async def get_namespaces() -> list[str]:
    """Get all namespaces from the cluster."""
    try:
        rc, stdout, _ = await _run_kubectl(
            "get", "namespaces", "-o", "jsonpath={.items[*].metadata.name}"
        )
        if rc == 0:
            return sorted(stdout.decode().split())
        return []
    except Exception:
        return []


async def list_releases(namespace: str | None = None) -> list[HelmRelease]:
    """List all Helm releases, optionally filtered by namespace."""
    args = ["list", "--output", "json"]
    if namespace and namespace != "All Namespaces":
        args.extend(["--namespace", namespace])
    else:
        args.append("--all-namespaces")

    rc, stdout, stderr = await _run_helm(*args)
    if rc != 0 or not stdout.strip():
        logger.warning("helm list failed: %s", stderr)
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning("Failed to parse helm list output")
        return []

    releases = []
    for item in data:
        chart_full = item.get("chart", "")
        # Parse chart name and version: e.g. "nginx-1.2.3"
        parts = chart_full.rsplit("-", 1)
        chart_name = parts[0] if parts else chart_full
        chart_version = parts[1] if len(parts) > 1 else ""

        releases.append(HelmRelease(
            name=item.get("name", ""),
            namespace=item.get("namespace", ""),
            revision=int(item.get("revision", "0")),
            status=ReleaseStatus.from_str(item.get("status", "unknown")),
            chart=chart_name,
            chart_version=chart_version,
            app_version=item.get("app_version", ""),
            updated=item.get("updated", ""),
            description=item.get("description", ""),
        ))

    return sorted(releases, key=lambda r: (r.namespace, r.name))


async def get_release_history(name: str, namespace: str) -> list[HelmRevision]:
    """Get revision history for a release."""
    rc, stdout, stderr = await _run_helm(
        "history", name, "--namespace", namespace, "--output", "json"
    )
    if rc != 0 or not stdout.strip():
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []

    return [
        HelmRevision(
            revision=int(item.get("revision", 0)),
            updated=item.get("updated", ""),
            status=ReleaseStatus.from_str(item.get("status", "unknown")),
            chart=item.get("chart", ""),
            app_version=item.get("app_version", ""),
            description=item.get("description", ""),
        )
        for item in data
    ]


async def get_release_values(name: str, namespace: str, all_values: bool = False) -> str:
    """Get values for a release."""
    args = ["get", "values", name, "--namespace", namespace, "--output", "yaml"]
    if all_values:
        args.append("--all")
    rc, stdout, stderr = await _run_helm(*args)
    if rc != 0:
        return f"# Error fetching values:\n# {stderr}"
    return stdout


async def get_release_manifest(name: str, namespace: str) -> str:
    """Get the rendered manifest for a release."""
    rc, stdout, stderr = await _run_helm(
        "get", "manifest", name, "--namespace", namespace
    )
    if rc != 0:
        return f"# Error fetching manifest:\n# {stderr}"
    return stdout


async def get_release_notes(name: str, namespace: str) -> str:
    """Get the notes for a release."""
    rc, stdout, stderr = await _run_helm(
        "get", "notes", name, "--namespace", namespace
    )
    if rc != 0:
        return f"# No notes available\n# {stderr}"
    return stdout


async def get_release_hooks(name: str, namespace: str) -> str:
    """Get hooks for a release."""
    rc, stdout, stderr = await _run_helm(
        "get", "hooks", name, "--namespace", namespace
    )
    if rc != 0:
        return f"# No hooks available\n# {stderr}"
    return stdout or "# No hooks defined for this release"


async def rollback_release(name: str, namespace: str, revision: int) -> tuple[bool, str]:
    """Rollback a release to a specific revision."""
    rc, stdout, stderr = await _run_helm(
        "rollback", name, str(revision), "--namespace", namespace
    )
    output = stdout + stderr
    return rc == 0, output.strip()


async def uninstall_release(name: str, namespace: str) -> tuple[bool, str]:
    """Uninstall a Helm release."""
    rc, stdout, stderr = await _run_helm(
        "uninstall", name, "--namespace", namespace
    )
    output = stdout + stderr
    return rc == 0, output.strip()


async def list_repos() -> list[HelmRepo]:
    """List configured Helm repositories."""
    rc, stdout, stderr = await _run_helm("repo", "list", "--output", "json")
    if rc != 0 or not stdout.strip():
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []

    return [HelmRepo(name=r.get("name", ""), url=r.get("url", "")) for r in data]


async def update_repos() -> tuple[bool, str]:
    """Update all Helm repos."""
    rc, stdout, stderr = await _run_helm("repo", "update", timeout=60.0)
    output = stdout + stderr
    return rc == 0, output.strip()


async def add_repo(name: str, url: str) -> tuple[bool, str]:
    """Add a Helm repository."""
    rc, stdout, stderr = await _run_helm("repo", "add", name, url)
    output = stdout + stderr
    return rc == 0, output.strip()


async def remove_repo(name: str) -> tuple[bool, str]:
    """Remove a Helm repository."""
    rc, stdout, stderr = await _run_helm("repo", "remove", name)
    output = stdout + stderr
    return rc == 0, output.strip()


async def search_charts(keyword: str) -> list[HelmChart]:
    """Search for charts in configured repos."""
    rc, stdout, stderr = await _run_helm(
        "search", "repo", keyword, "--output", "json"
    )
    if rc != 0 or not stdout.strip():
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []

    return [
        HelmChart(
            name=c.get("name", ""),
            chart_version=c.get("version", ""),
            app_version=c.get("app_version", ""),
            description=c.get("description", ""),
        )
        for c in data
    ]


async def get_release_resources(name: str, namespace: str) -> str:
    """Get Kubernetes resources for a release using kubectl."""
    try:
        rc, stdout_bytes, _ = await _run_kubectl(
            "get", "all",
            "-l", f"app.kubernetes.io/instance={name}",
            "--namespace", namespace,
            "-o", "wide",
            timeout=15.0,
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        if stdout.strip():
            return stdout
        # Try alternative label
        rc2, stdout2_bytes, _ = await _run_kubectl(
            "get", "all",
            "-l", f"release={name}",
            "--namespace", namespace,
            "-o", "wide",
            timeout=15.0,
        )
        stdout2 = stdout2_bytes.decode("utf-8", errors="replace")
        return stdout2 if stdout2.strip() else f"No resources found for release '{name}'"
    except Exception as e:
        return f"Error fetching resources: {e}"

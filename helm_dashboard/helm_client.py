"""Helm CLI wrapper — async subprocess calls to helm binary."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

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

    @property
    def is_rollback(self) -> bool:
        """True when this revision was created by a helm rollback."""
        return "rollback" in self.description.lower()


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


@dataclass
class K8sResource:
    """A Kubernetes resource belonging to a release."""
    kind: str
    name: str
    namespace: str
    ready: str    # e.g. "1/1", "-"
    status: str   # e.g. "Running", "ClusterIP"
    age: str      # e.g. "2d", "5m"


@dataclass
class K8sEvent:
    """A Kubernetes event."""
    age: str          # relative age, e.g. "3m"
    last_seen: str    # absolute, truncated: "2026-03-21 14:05:01"
    type: str         # "Normal" or "Warning"
    reason: str
    object_ref: str   # "Pod/my-pod-xxx"
    message: str
    count: int


# ── Kubernetes helpers ─────────────────────────────────────────────────────────

_KIND_ICONS: dict[str, str] = {
    "Pod": "🫛",
    "Deployment": "🚀",
    "ReplicaSet": "📋",
    "StatefulSet": "🗄️",
    "DaemonSet": "👾",
    "Service": "🔗",
    "Ingress": "🌐",
    "ConfigMap": "📄",
    "Secret": "🔒",
    "PersistentVolumeClaim": "💾",
    "Job": "⚙️",
    "CronJob": "🕐",
    "ServiceAccount": "👤",
    "HorizontalPodAutoscaler": "📊",
    "NetworkPolicy": "🛡️",
}


def _age_from_timestamp(ts: str) -> str:
    """Convert an ISO 8601 timestamp to a human-readable age string."""
    if not ts:
        return "?"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(tz=timezone.utc)
        secs = int((now - dt).total_seconds())
        if secs < 90:
            return f"{secs}s"
        mins = secs // 60
        if mins < 90:
            return f"{mins}m"
        hours = mins // 60
        if hours < 48:
            return f"{hours}h"
        return f"{hours // 24}d"
    except Exception:
        return "?"


def _resource_ready_status(item: dict[str, Any]) -> tuple[str, str]:
    """Return (ready, status) strings for any resource kind."""
    kind = item.get("kind", "")
    status = item.get("status", {}) or {}
    spec = item.get("spec", {}) or {}

    if kind == "Pod":
        phase = status.get("phase", "Unknown")
        cs_list = status.get("containerStatuses", []) or []
        ready_n = sum(1 for cs in cs_list if cs.get("ready"))
        total_n = len(cs_list)
        ready = f"{ready_n}/{total_n}" if total_n else "0/?"
        for cs in cs_list:
            reason = cs.get("state", {}).get("waiting", {}).get("reason", "")
            if reason in ("CrashLoopBackOff", "Error", "ImagePullBackOff", "ErrImagePull", "OOMKilled"):
                return ready, reason
        return ready, phase

    if kind in ("Deployment", "ReplicaSet", "StatefulSet"):
        desired = status.get("replicas") or spec.get("replicas") or 0
        ready_n = status.get("readyReplicas") or 0
        label = "Ready" if ready_n == desired and desired > 0 else "Not Ready"
        return f"{ready_n}/{desired}", label

    if kind == "DaemonSet":
        desired = status.get("desiredNumberScheduled") or 0
        ready_n = status.get("numberReady") or 0
        return f"{ready_n}/{desired}", "Ready" if ready_n == desired else "Not Ready"

    if kind == "Service":
        return "-", spec.get("type", "ClusterIP")

    if kind == "Job":
        succeeded = status.get("succeeded") or 0
        completions = spec.get("completions") or 1
        active = status.get("active") or 0
        if succeeded >= completions:
            return f"{succeeded}/{completions}", "Complete"
        return f"{succeeded}/{completions}", "Active" if active else "Failed"

    if kind == "CronJob":
        last = status.get("lastScheduleTime", "")
        active_n = len(status.get("active") or [])
        return str(active_n), f"Last: {last[:10]}" if last else "Never"

    if kind == "PersistentVolumeClaim":
        return "-", status.get("phase", "-")

    return "-", "-"


def _parse_resource_item(item: dict[str, Any]) -> K8sResource:
    kind = item.get("kind", "Unknown")
    meta = item.get("metadata", {}) or {}
    ready, status = _resource_ready_status(item)
    return K8sResource(
        kind=kind,
        name=meta.get("name", ""),
        namespace=meta.get("namespace", ""),
        ready=ready,
        status=status,
        age=_age_from_timestamp(meta.get("creationTimestamp", "")),
    )


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


async def switch_context(context_name: str) -> tuple[bool, str]:
    """Switch the active kubectl context."""
    rc, stdout, stderr = await _run_kubectl(
        "config", "use-context", context_name
    )
    output = (stdout + stderr).decode("utf-8", errors="replace").strip()
    return rc == 0, output


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


async def get_values_for_revision(name: str, namespace: str, revision: int) -> str:
    """Get computed values for a specific historical revision."""
    rc, stdout, stderr = await _run_helm(
        "get", "values", name,
        "--namespace", namespace,
        "--revision", str(revision),
        "--all",
        "--output", "yaml",
    )
    if rc != 0:
        return f"# Error fetching values for revision {revision}:\n# {stderr}"
    return stdout


def diff_values(old: str, new: str, old_label: str = "old", new_label: str = "new") -> str:
    """Return a unified diff of two YAML values strings."""
    diff = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=old_label,
        tofile=new_label,
    ))
    return "".join(diff) if diff else "(no differences)"


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


async def get_available_chart_versions(chart_name: str) -> list[HelmChart]:
    """Search repos for available versions of a chart (by base chart name).

    Returns versions sorted by the repo's default order (typically newest first).
    """
    rc, stdout, stderr = await _run_helm(
        "search", "repo", chart_name, "--output", "json", "--versions"
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


async def get_release_events(name: str, namespace: str) -> list[K8sEvent]:
    """Get Kubernetes events in the release namespace, newest first."""
    rc, stdout, _ = await _run_kubectl(
        "get", "events",
        "--namespace", namespace,
        "--sort-by=.lastTimestamp",
        "-o", "json",
        timeout=15.0,
    )
    if rc != 0:
        return []
    try:
        data = json.loads(stdout.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, AttributeError):
        return []

    events: list[K8sEvent] = []
    for item in data.get("items", []):
        last_ts = (
            item.get("lastTimestamp")
            or item.get("eventTime")
            or item.get("firstTimestamp")
            or ""
        )
        obj = item.get("involvedObject", {}) or {}
        events.append(K8sEvent(
            age=_age_from_timestamp(last_ts),
            last_seen=last_ts[:19].replace("T", " ") if last_ts else "?",
            type=item.get("type", "Normal"),
            reason=item.get("reason", ""),
            object_ref=f"{obj.get('kind', '?')}/{obj.get('name', '?')}",
            message=item.get("message", ""),
            count=item.get("count", 1) or 1,
        ))
    # Newest first
    return list(reversed(events))


async def list_pods_for_release(name: str, namespace: str) -> list[dict[str, str]]:
    """List pods belonging to a release via label selectors.

    Returns list of dicts with keys: name, status, containers.
    """
    pods: list[dict[str, str]] = []

    for label in (f"app.kubernetes.io/instance={name}", f"release={name}"):
        rc, stdout, _ = await _run_kubectl(
            "get", "pods",
            "-l", label,
            "--namespace", namespace,
            "-o", "jsonpath={range .items[*]}{.metadata.name}|{.status.phase}|{range .status.containerStatuses[*]}{.name},{end}\\n{end}",
            timeout=15.0,
        )
        text = stdout.decode("utf-8", errors="replace")
        if rc == 0 and text.strip():
            for line in text.strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 2:
                    pods.append({
                        "name": parts[0],
                        "status": parts[1],
                        "containers": parts[2].rstrip(",") if len(parts) > 2 else "",
                    })
            if pods:
                return pods

    return pods


async def stream_pod_logs(
    pod_name: str,
    namespace: str,
    container: str = "",
    tail_lines: int = 200,
) -> str:
    """Fetch recent pod logs (non-streaming snapshot, last N lines)."""
    args: list[str] = [
        "logs", pod_name,
        "--namespace", namespace,
        f"--tail={tail_lines}",
    ]
    if container:
        args.extend(["-c", container])
    rc, stdout, stderr = await _run_kubectl(*args, timeout=30.0)
    output = stdout.decode("utf-8", errors="replace")
    if rc != 0:
        return f"Error fetching logs: {stderr.decode('utf-8', errors='replace')}"
    return output or "(no log output)"


async def describe_resource(kind: str, name: str, namespace: str) -> str:
    """Run kubectl describe on a specific resource."""
    rc, stdout, stderr = await _run_kubectl(
        "describe", kind, name,
        "--namespace", namespace,
        timeout=15.0,
    )
    output = stdout.decode("utf-8", errors="replace")
    if rc != 0:
        return f"Error: {stderr.decode('utf-8', errors='replace')}"
    return output or f"No describe output for {kind}/{name}"


def _parse_manifest_resource_names(manifest: str) -> list[tuple[str, str]]:
    """Parse a multi-document YAML manifest and extract (kind, name) pairs."""
    results: list[tuple[str, str]] = []
    try:
        for doc in yaml.safe_load_all(manifest):
            if not isinstance(doc, dict):
                continue
            kind = doc.get("kind", "")
            name = doc.get("metadata", {}).get("name", "")
            if kind and name:
                results.append((kind, name))
    except Exception:
        pass
    return results


async def get_release_resources(name: str, namespace: str) -> list[K8sResource]:
    """Get Kubernetes resources for a release as structured data.

    Tries three strategies in order:
    1. Label selector: app.kubernetes.io/instance=<name>
    2. Label selector: release=<name>
    3. Parse manifest to get explicit resource names, then kubectl get each type.
    """
    from collections import defaultdict

    def _parse_items(raw: bytes) -> list[K8sResource]:
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
            return [_parse_resource_item(i) for i in data.get("items", [])]
        except (json.JSONDecodeError, AttributeError):
            return []

    # Strategy 1 & 2: label selectors
    for label in (f"app.kubernetes.io/instance={name}", f"release={name}"):
        rc, stdout, _ = await _run_kubectl(
            "get", "all", "-l", label,
            "--namespace", namespace, "-o", "json",
            timeout=15.0,
        )
        if rc == 0 and stdout:
            items = _parse_items(stdout)
            if items:
                return sorted(items, key=lambda r: (r.kind, r.name))

    # Strategy 3: parse manifest
    rc, manifest, _ = await _run_helm("get", "manifest", name, "--namespace", namespace)
    if rc != 0:
        return []

    resource_pairs = _parse_manifest_resource_names(manifest)
    if not resource_pairs:
        return []

    by_kind: dict[str, list[str]] = defaultdict(list)
    for kind, res_name in resource_pairs:
        by_kind[kind].append(res_name)

    results: list[K8sResource] = []
    for kind, names in by_kind.items():
        rc, out, _ = await _run_kubectl(
            "get", kind, *names,
            "--namespace", namespace, "-o", "json",
            timeout=15.0,
        )
        if rc == 0 and out:
            results.extend(_parse_items(out))

    return sorted(results, key=lambda r: (r.kind, r.name))

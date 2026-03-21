"""InfoHeader widget — k9s-style cluster information panel."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

_LOGO_LINES = [
    " _  _  ___  ___ ",
    "| || |/ _ \\/ __| ",
    "| __ \\\\  9 /\\__ \\ ",
    "|_||_|\\___/|___/ ",
]


class InfoHeader(Widget):
    """k9s-style header showing cluster info, namespace shortcuts, key hints, and logo."""

    DEFAULT_CSS = """
    InfoHeader {
        height: 6;
        background: $primary-darken-3;
        layout: horizontal;
    }

    #info-left {
        width: 36;
        padding: 0 1;
        color: $text;
    }

    #info-ns {
        width: 26;
        padding: 0 1;
        border-left: tall $primary-darken-1;
        color: $text;
    }

    #info-keys {
        width: 1fr;
        padding: 0 1;
        border-left: tall $primary-darken-1;
        color: $text-muted;
    }

    #info-logo {
        width: 22;
        padding: 0 1;
        border-left: tall $primary-darken-1;
        color: $success;
        text-style: bold;
    }
    """

    context_name: reactive[str] = reactive("loading…")
    cluster_name: reactive[str] = reactive("…")
    user_name: reactive[str] = reactive("…")
    helm_version: reactive[str] = reactive("…")
    k8s_version: reactive[str] = reactive("…")
    cpu_pct: reactive[str] = reactive("…")
    mem_pct: reactive[str] = reactive("…")
    namespaces: reactive[list[str]] = reactive(list)
    auto_refresh_label: reactive[str] = reactive("off")

    def compose(self) -> ComposeResult:
        yield Static("", id="info-left")
        yield Static("", id="info-ns")
        yield Static("", id="info-keys")
        yield Static("", id="info-logo")

    def on_mount(self) -> None:
        self._refresh_left()
        self._refresh_ns()
        self._refresh_keys()
        self._refresh_logo()

    # ── Watchers ──────────────────────────────────────────────────────────────

    def watch_context_name(self, _: str) -> None:
        self._refresh_left()

    def watch_cluster_name(self, _: str) -> None:
        self._refresh_left()

    def watch_user_name(self, _: str) -> None:
        self._refresh_left()

    def watch_helm_version(self, _: str) -> None:
        self._refresh_left()

    def watch_k8s_version(self, _: str) -> None:
        self._refresh_left()

    def watch_cpu_pct(self, _: str) -> None:
        self._refresh_left()

    def watch_mem_pct(self, _: str) -> None:
        self._refresh_left()

    def watch_namespaces(self, _: list[str]) -> None:
        self._refresh_ns()

    def watch_auto_refresh_label(self, _: str) -> None:
        self._refresh_keys()

    # ── Renderers ─────────────────────────────────────────────────────────────

    def _refresh_left(self) -> None:
        t = Text()
        t.append(" Context: ", style="dim")
        # Truncate long names to fit the column
        t.append(_trunc(self.context_name, 24), style="bold yellow")
        t.append("\n Cluster: ", style="dim")
        t.append(_trunc(self.cluster_name, 24), style="bold cyan")
        t.append("\n    User: ", style="dim")
        t.append(_trunc(self.user_name, 24), style="cyan")
        t.append("\n     K8s: ", style="dim")
        t.append(self.k8s_version, style="green")
        t.append("\n    Helm: ", style="dim")
        t.append(self.helm_version, style="green")
        t.append("\n  CPU: ", style="dim")
        t.append(self.cpu_pct, style=_pct_style(self.cpu_pct))
        t.append("  MEM: ", style="dim")
        t.append(self.mem_pct, style=_pct_style(self.mem_pct))
        try:
            self.query_one("#info-left", Static).update(t)
        except Exception:
            pass

    def _refresh_ns(self) -> None:
        t = Text()
        t.append(" Namespaces\n", style="bold dim")
        t.append(" <0>", style="bold yellow")
        t.append(" all\n", style="white")
        for i, ns in enumerate(self.namespaces[:7], start=1):
            t.append(f" <{i}>", style="bold yellow")
            t.append(f" {_trunc(ns, 16)}\n", style="white")
        try:
            self.query_one("#info-ns", Static).update(t)
        except Exception:
            pass

    def _refresh_keys(self) -> None:
        ar = self.auto_refresh_label
        pairs = [
            ("<r>", "Refresh"),
            ("<enter>", "Detail"),
            ("<n>", "Namespace"),
            ("<c>", "Context"),
            ("<B>", "Rollback"),
            ("<D>", "Delete"),
            ("<R>", "Repos"),
            (f"<A>", f"Auto:{ar}"),
            ("</>", "Search"),
            ("<q>", "Quit"),
        ]
        t = Text()
        for idx, (key, label) in enumerate(pairs):
            t.append(f" {key}", style="bold yellow")
            t.append(f" {label:<12}", style="white")
            if idx % 2 == 1:
                t.append("\n")
        try:
            self.query_one("#info-keys", Static).update(t)
        except Exception:
            pass

    def _refresh_logo(self) -> None:
        t = Text()
        for line in _LOGO_LINES:
            t.append(line + "\n", style="bold green")
        t.append("\n ⎈  helm TUI", style="dim")
        try:
            self.query_one("#info-logo", Static).update(t)
        except Exception:
            pass


def _trunc(value: str, max_len: int) -> str:
    """Truncate a string and append '…' if it exceeds max_len."""
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"


def _pct_style(pct_str: str) -> str:
    """Return 'red' for percentages >= 80, otherwise 'green'."""
    try:
        return "red" if int(pct_str.rstrip("%")) >= 80 else "green"
    except (ValueError, AttributeError):
        return "dim"

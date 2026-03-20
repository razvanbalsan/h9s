from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class HelpScreen(ModalScreen[None]):
    """Keyboard shortcuts help overlay."""

    BINDINGS = [Binding("escape", "dismiss_help", "Close")]

    def compose(self) -> ComposeResult:
        help_text = """\
[bold cyan]⎈ Helm Dashboard — Keyboard Shortcuts[/bold cyan]

[bold]Navigation[/bold]
  [yellow]↑/↓  k/j[/yellow]     Navigate release list
  [yellow]Enter[/yellow]        Select release / view details
  [yellow]Tab[/yellow]          Switch between panels
  [yellow]1-6[/yellow]          Switch detail tabs

[bold]Actions[/bold]
  [yellow]r[/yellow]            Refresh releases
  [yellow]/[/yellow]            Focus search filter
  [yellow]n[/yellow]            Select namespace
  [yellow]B[/yellow]            Rollback selected release
  [yellow]D[/yellow]            Uninstall (delete) selected release
  [yellow]R[/yellow]            Repositories view
  [yellow]U[/yellow]            Update all repos
  [yellow]c[/yellow]            Switch Kubernetes context
  [yellow]A[/yellow]            Toggle auto-refresh (off/30s/1m/5m)
  [yellow]l[/yellow]            (in Detail view) Open pod log viewer

[bold]Views[/bold]
  [yellow]?[/yellow]            Show this help
  [yellow]q / Ctrl+C[/yellow]   Quit

[dim]Press Escape to close this help.[/dim]"""

        with Vertical(id="help-box"):
            yield Static(help_text)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)

    def key_escape(self) -> None:
        self.dismiss(None)

    def key_question_mark(self) -> None:
        self.dismiss(None)

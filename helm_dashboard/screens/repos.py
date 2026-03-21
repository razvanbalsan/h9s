from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from helm_dashboard.screens.dialogs import ConfirmDialog, InputDialog
from helm_dashboard.helm_client import add_repo, list_repos, remove_repo, update_repos


class RepoScreen(ModalScreen[None]):
    """Screen to manage Helm repositories."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Close"),
        Binding("a", "add_repo", "Add Repo"),
        Binding("d", "remove_repo", "Remove"),
        Binding("u", "update_repos", "Update All"),
        Binding("r", "refresh_repos", "Refresh"),
    ]

    CSS = """
    RepoScreen {
        align: center middle;
    }

    #repo-box {
        width: 90;
        height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #repo-header {
        height: 3;
        layout: horizontal;
    }

    #repo-title {
        width: 1fr;
        text-style: bold;
        color: $accent;
        padding: 1 0;
    }

    #repo-actions {
        width: auto;
        layout: horizontal;
    }

    #repo-actions Button {
        margin: 0 1;
    }

    #repo-table {
        height: 1fr;
    }

    #repo-footer {
        height: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="repo-box"):
            with Horizontal(id="repo-header"):
                yield Static("⎈ Helm Repositories", id="repo-title")
                with Horizontal(id="repo-actions"):
                    yield Button("Add", variant="success", id="btn-add-repo")
                    yield Button("Update All", variant="primary", id="btn-update-repos")
                    yield Button("Close", variant="default", id="btn-close-repos")
            yield DataTable(id="repo-table", cursor_type="row", zebra_stripes=True)
            yield Static(
                "[dim]a: Add  |  d: Delete selected  |  u: Update  |  Esc: Close[/dim]",
                id="repo-footer",
            )

    async def on_mount(self) -> None:
        table = self.query_one("#repo-table", DataTable)
        table.add_columns("Name", "URL")
        await self._load_repos()

    async def _load_repos(self) -> None:
        table = self.query_one("#repo-table", DataTable)
        table.clear()
        repos = await list_repos()
        for repo in repos:
            table.add_row(repo.name, repo.url, key=repo.name)

    @on(Button.Pressed, "#btn-close-repos")
    def on_close(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-add-repo")
    def on_add_repo_btn(self) -> None:
        self.action_add_repo()

    @on(Button.Pressed, "#btn-update-repos")
    def on_update_repos_btn(self) -> None:
        self.action_update_repos()

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def action_add_repo(self) -> None:
        self.app.push_screen(
            InputDialog("Add Helm Repository", "Repository Name", "Repository URL"),
            callback=self._handle_add_repo,
        )

    def _handle_add_repo(self, result: tuple[str, str] | None) -> None:
        if result:
            self._do_add_repo(result[0], result[1])

    @work(thread=False)
    async def _do_add_repo(self, name: str, url: str) -> None:
        success, msg = await add_repo(name, url)
        if success:
            self.notify(f"✅ Added repo: {name}", severity="information")
            await self._load_repos()
        else:
            self.notify(f"❌ Failed: {msg}", severity="error", timeout=8)

    def action_remove_repo(self) -> None:
        table = self.query_one("#repo-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.get_row_at(table.cursor_row)
            repo_name = str(row_key[0]) if row_key else None
            if repo_name:
                self.app.push_screen(
                    ConfirmDialog(f"Remove repository [bold]{repo_name}[/bold]?", "Remove Repo"),
                    callback=lambda confirmed, n=repo_name: self._do_remove_repo(n) if confirmed else None,  # type: ignore[arg-type]
                )

    @work(thread=False)
    async def _do_remove_repo(self, name: str) -> None:
        success, msg = await remove_repo(name)
        if success:
            self.notify(f"🗑️ Removed repo: {name}", severity="information")
            await self._load_repos()
        else:
            self.notify(f"❌ Failed: {msg}", severity="error", timeout=8)

    @work(thread=False)
    async def action_update_repos(self) -> None:
        self.notify("Updating all repos...", timeout=3)
        success, msg = await update_repos()
        if success:
            self.notify("✅ Repos updated", severity="information")
            await self._load_repos()
        else:
            self.notify(f"❌ Update failed: {msg}", severity="error", timeout=8)

    @work(thread=False)
    async def action_refresh_repos(self) -> None:
        await self._load_repos()

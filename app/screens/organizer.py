"""
MacSweep — Smart File Organizer Screen
Rule-based file organization using extension pattern matching.
"""

from pathlib import Path
from textual.screen import Screen
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Input, Button, Label, DataTable
from textual.binding import Binding
from textual import work
from rich.text import Text

from ..core.organizer import load_rules, plan_moves, execute_moves


class OrganizerScreen(Screen):
    """Screen for rule-based file organization."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("p", "preview_org", "Preview", show=True),
        Binding("o", "execute_org", "Organize Now", show=True),
        Binding("u", "undo_last", "Undo Last", show=True),
    ]

    def compose(self):
        yield Header()
        with Container(id="organizer-container"):
            yield Label("Smart File Organizer", classes="screen-title")

            with Horizontal(id="org-controls-row"):
                yield Input(value=str(Path.home() / "Downloads"), placeholder="Target folder to organize...", id="org-path-input")
                yield Button("Preview", variant="default", id="org-preview-btn")
                yield Button("Organize Now", variant="success", id="org-run-btn")

            # Status label
            self.status_lbl = Label("Select folder and click Preview to view sorting plan.", id="org-status-lbl")
            yield self.status_lbl

            # Table for moves preview
            self.table = DataTable(id="org-table")
            yield self.table

        yield Footer()

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        self.table.add_column("Rule Match", key="rule_col")
        self.table.add_column("Source Path", key="src_col")
        self.table.add_column("→", key="arrow_col")
        self.table.add_column("Destination Path", key="dst_col")

        # Load rules
        self.rules = load_rules()
        self.planned_moves = []

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "org-preview-btn":
            self.action_preview_org()
        elif event.button.id == "org-run-btn":
            self.action_execute_org()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_preview_org(self) -> None:
        path_str = self.query_one("#org-path-input", Input).value.strip()
        path = Path(path_str).expanduser().resolve()

        if not path.exists() or not path.is_dir():
            self.app.notify(f"Invalid path: {path_str}", severity="error")
            return

        # Load rules and plan
        self.rules = load_rules()
        self.planned_moves = plan_moves(path, self.rules, date_mode=False)

        self.table.clear()
        for move in self.planned_moves:
            try:
                dst_display = str(move.dst.relative_to(path))
            except ValueError:
                dst_display = str(move.dst)
            self.table.add_row(
                Text(move.rule_name, style="cyan"),
                Text(move.src.name, style="dim white"),
                Text("→", style="bold green"),
                Text(dst_display, style="green")
            )

        count = len(self.planned_moves)
        self.status_lbl.update(f"Found [bold cyan]{count}[/bold cyan] files that can be organized.")
        self.app.notify(f"Planned {count} file movements.")

    def action_execute_org(self) -> None:
        if not self.planned_moves:
            self.app.notify("No moves planned. Run Preview first.", severity="warning")
            return

        self.run_organization_task()

    @work(exclusive=True, thread=True)
    def run_organization_task(self) -> None:
        self.app.call_from_thread(self.set_busy, True)

        try:
            results = execute_moves(
                self.planned_moves,
                self.app.history_manager,
                dry_run=False
            )

            self.app.call_from_thread(self.app.notify, f"Moved {len(self.planned_moves)} files!")
            self.app.call_from_thread(self.clear_plan)
        except Exception as exc:
            self.app.call_from_thread(self.app.notify, f"Organization failed: {exc}", severity="error")
        finally:
            self.app.call_from_thread(self.set_busy, False)

    def set_busy(self, busy: bool) -> None:
        self.query_one("#org-preview-btn", Button).disabled = busy
        self.query_one("#org-run-btn", Button).disabled = busy

    def clear_plan(self) -> None:
        self.planned_moves.clear()
        self.table.clear()
        self.status_lbl.update("Organization complete! Select a folder and click Preview.")

    def action_undo_last(self) -> None:
        history = self.app.history_manager

        last_entry = history.get_recent(1)
        if not last_entry:
            self.app.notify("No actions to undo", severity="warning")
            return

        batch_id = last_entry[0].batch_id
        if batch_id and batch_id.startswith("org-"):
            results = history.undo_batch(batch_id)
            self.app.notify(f"✓ Restored {len(results)} organized files!")
        else:
            results = history.undo_last(1)
            if results:
                self.app.notify(results[0])
            else:
                self.app.notify("No actions to undo", severity="warning")

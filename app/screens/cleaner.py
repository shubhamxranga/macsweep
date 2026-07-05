"""
MacSweep — Cache & Junk Cleaner Screen
Allows scanning and selective removal of caches (npm, pip, brew) and developer junk (Xcode).
"""

from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Label, DataTable
from textual.binding import Binding
from textual import work
from rich.text import Text

from ..core.cleaner import scan_junk, clean_targets
from ..widgets.confirm_modal import ConfirmModal
from ..core.utils import format_size

class CleanerScreen(Screen):
    """Screen for identifying and clearing system cache and junk directories."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("s", "start_scan", "Scan Junk", show=True),
        Binding("c", "clean_selected", "Clean Selected", show=True),
        Binding("space", "toggle_row", "Toggle Select", show=True),
        Binding("a", "toggle_all", "Select All/None", show=True),
    ]

    def compose(self):
        yield Header()
        with Container(id="cleaner-container"):
            yield Label("Cache & Junk Cleaner", classes="screen-title")

            with Horizontal(id="cleaner-controls-row"):
                yield Button("Scan System", variant="primary", id="clean-scan-btn")
                yield Button("Clean Selected", variant="error", id="clean-run-btn")

            self.status_lbl = Label("Press Scan System to discover caches and cleanable directories.", id="clean-status-lbl")
            yield self.status_lbl

            # Table for checklist
            self.table = DataTable(id="clean-table")
            yield self.table

        yield Footer()

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        self.table.add_column("Clean?", key="clean_col")
        self.table.add_column("Target Name", key="name_col")
        self.table.add_column("Cleanable Size", key="size_col")
        self.table.add_column("Safety", key="safety_col")
        self.table.add_column("Path", key="path_col")

        # Internal state
        self.targets = []        # List of JunkTarget objects
        self.clean_selections = {}     # Map target index to Boolean

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clean-scan-btn":
            self.action_start_scan()
        elif event.button.id == "clean-run-btn":
            self.action_clean_selected()

    def action_back(self) -> None:
        self.app.pop_screen()

    @work(exclusive=True, thread=True)
    def action_start_scan(self) -> None:
        self.app.call_from_thread(self.set_loading, True)
        self.app.call_from_thread(self.status_lbl.update, "Scanning caches and logs...")

        try:
            targets = scan_junk()
            self.app.call_from_thread(self.populate_table, targets)
        except Exception as exc:
            self.app.call_from_thread(self.app.notify, f"Scan failed: {exc}", severity="error")
            self.app.call_from_thread(self.status_lbl.update, "Scan failed.")
        finally:
            self.app.call_from_thread(self.set_loading, False)

    def set_loading(self, loading: bool) -> None:
        self.query_one("#clean-scan-btn", Button).disabled = loading
        self.query_one("#clean-run-btn", Button).disabled = loading

    def populate_table(self, targets: list) -> None:
        self.targets = targets
        self.table.clear()
        self.clean_selections.clear()

        total_size = sum(t.size_bytes for t in targets)
        self.status_lbl.update(f"Found [bold cyan]{len(targets)}[/bold cyan] cleaning targets. Wasted space: [bold red]{format_size(total_size)}[/bold red]")

        for idx, t in enumerate(targets):
            # Safe defaults: select safe, unselect caution
            is_safe = (t.safe_level == "safe")
            self.clean_selections[idx] = is_safe

            cb_text = Text("[x]", style="bold red") if is_safe else Text("[ ]", style="white")
            name_text = Text(t.name, style="bold white")
            size_text = Text(format_size(t.size_bytes), style="green" if is_safe else "yellow")
            
            safety_style = "bold green" if is_safe else "bold yellow"
            safety_text = Text(t.safe_level.upper(), style=safety_style)
            
            path_text = Text(t.path, style="dim white")

            self.table.add_row(
                cb_text, name_text, size_text, safety_text, path_text
            )

        self.app.notify(f"Scan finished. Found {format_size(total_size)} junk.")

    def action_toggle_row(self) -> None:
        cursor_row = self.table.cursor_row
        if cursor_row is None or cursor_row >= len(self.targets):
            return

        current = self.clean_selections[cursor_row]
        new_val = not current
        self.clean_selections[cursor_row] = new_val

        # Update cell visual
        cell_text = Text("[x]", style="bold red") if new_val else Text("[ ]", style="white")
        self.table.update_cell_at((cursor_row, 0), cb_text := cell_text)

    def action_toggle_all(self) -> None:
        """Select all or deselect all rows."""
        if not self.targets:
            return

        # If any is unselected, select all. Else, deselect all.
        any_unselected = any(not val for val in self.clean_selections.values())
        new_state = any_unselected

        for idx in range(len(self.targets)):
            self.clean_selections[idx] = new_state
            cell_text = Text("[x]", style="bold red") if new_state else Text("[ ]", style="white")
            self.table.update_cell_at((idx, 0), cb_text := cell_text)

        self.app.notify("Selected all" if new_state else "Deselected all")

    def action_clean_selected(self) -> None:
        selected_targets = [self.targets[idx] for idx, sel in self.clean_selections.items() if sel]
        
        if not selected_targets:
            self.app.notify("No targets selected.", severity="warning")
            return

        total_size = sum(t.size_bytes for t in selected_targets)

        # Confirm modal
        desc = f"You are about to delete {len(selected_targets)} cache/junk locations, freeing {format_size(total_size)}."
        modal = ConfirmModal(
            title="Confirm System Cleanup",
            description=desc,
            require_yes=(total_size >= 1_073_741_824) # Require type 'yes' if >= 1GB
        )

        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                self.execute_cleaning(selected_targets)

        self.app.push_screen(modal, handle_confirm)

    @work(exclusive=True, thread=True)
    def execute_cleaning(self, targets: list) -> None:
        self.app.call_from_thread(self.set_loading, True)
        self.app.call_from_thread(self.status_lbl.update, "Cleaning selected targets...")

        try:
            results = clean_targets(targets, self.app.history_manager)
            
            # Show summary
            cleaned_size = sum(t.size_bytes for t in targets)
            self.app.call_from_thread(self.app.notify, f"Cleaned {len(targets)} folders, reclaimed {format_size(cleaned_size)}!")
            
            # Auto re-scan on main thread
            self.app.call_from_thread(self.action_start_scan)
        except Exception as exc:
            self.app.call_from_thread(self.app.notify, f"Cleanup failed: {exc}", severity="error")
        finally:
            self.app.call_from_thread(self.set_loading, False)

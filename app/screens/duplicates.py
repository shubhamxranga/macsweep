"""
MacSweep — Duplicate Finder Screen
Locates and displays identical files by hashing, offering automated resolution rules.
"""

from pathlib import Path
from datetime import datetime
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, Label, DataTable, Switch, ProgressBar
from textual.binding import Binding
from textual import work
from rich.text import Text

from ..core.duplicates import find_duplicates, resolve_group
from ..widgets.confirm_modal import ConfirmModal
from ..core.utils import format_size, safe_delete

class DuplicatesScreen(Screen):
    """Screen for finding and deleting duplicate files."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("s", "start_scan", "Scan", show=True),
        Binding("d", "delete_selected", "Delete Selected", show=True),
        Binding("n", "auto_select_newest", "Keep Newest", show=True),
        Binding("o", "auto_select_oldest", "Keep Oldest", show=True),
        Binding("space", "toggle_row", "Toggle Select", show=True),
    ]

    def compose(self):
        yield Header()
        with Container(id="duplicates-container"):
            yield Label("Duplicate Finder (Hash-based)", classes="screen-title")
            
            with Horizontal(id="dup-controls-row"):
                yield Input(value=str(Path.home()), placeholder="Enter folder path to check...", id="dup-path-input")
                yield Button("Find Duplicates", variant="primary", id="dup-scan-btn")

            with Horizontal(id="dup-options-row"):
                yield Label("Dry Run (Preview only): ", classes="switch-lbl")
                yield Switch(value=True, id="dup-dryrun-switch")
                self.wasted_lbl = Label("Wasted Space: 0 B", id="dup-wasted-lbl")
                yield self.wasted_lbl

            # Progress overlay
            with Vertical(id="dup-progress-box"):
                yield Label("Scanning for duplicates... Hashing size matches...", id="dup-status-lbl")
                yield ProgressBar(total=100, show_percentage=False, id="dup-progress-bar")

            # Table for duplicates
            self.table = DataTable(id="dup-table")
            yield self.table

        yield Footer()

    def on_mount(self) -> None:
        self.table.cursor_type = "row"
        self.table.add_column("Delete?", key="delete_col")
        self.table.add_column("Group Hash", key="hash_col")
        self.table.add_column("Name", key="name_col")
        self.table.add_column("Size", key="size_col")
        self.table.add_column("Modified", key="mtime_col")
        self.table.add_column("Full Path", key="path_col")

        self.query_one("#dup-progress-box", Vertical).display = False
        
        # Internal state
        self.groups = []        # List of DuplicateGroup objects
        self.row_selections = {} # Map table row index to Boolean (should delete)
        self.row_paths = []     # List of paths in the table matching row indices

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dup-scan-btn":
            self.action_start_scan()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_start_scan(self) -> None:
        path_str = self.query_one("#dup-path-input", Input).value.strip()
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            self.app.notify(f"Path does not exist: {path_str}", severity="error")
            return

        self.run_duplicate_scan(path)

    @work(exclusive=True, thread=True)
    def run_duplicate_scan(self, path: Path) -> None:
        self.app.call_from_thread(self.show_progress, True)
        self.app.call_from_thread(self.update_status, "Finding candidate files...")

        def progress_callback(phase, current, total):
            self.app.call_from_thread(
                self.update_status, f"Phase: {phase} ({current}/{total})"
            )

        try:
            groups = find_duplicates(path, callback=progress_callback)
            self.app.call_from_thread(self.populate_table, groups)
        except Exception as exc:
            self.app.call_from_thread(self.app.notify, f"Scan failed: {exc}", severity="error")
        finally:
            self.app.call_from_thread(self.show_progress, False)

    def show_progress(self, show: bool) -> None:
        self.query_one("#dup-progress-box", Vertical).display = show
        self.query_one("#dup-scan-btn", Button).disabled = show
        self.query_one("#dup-dryrun-switch", Switch).disabled = show

    def update_status(self, text: str) -> None:
        self.query_one("#dup-status-lbl", Label).update(text)

    def populate_table(self, groups: list) -> None:
        self.groups = groups
        self.table.clear()
        self.row_selections.clear()
        self.row_paths.clear()

        total_wasted = sum(g.wasted_bytes for g in groups)
        self.wasted_lbl.update(f"Total Wasted Space: [bold red]{format_size(total_wasted)}[/bold red]")

        row_idx = 0
        for g in groups:
            # We display each file in the group
            hash_short = g.hash[:8]
            for file_path in g.paths:
                p = Path(file_path)
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    mtime = "N/A"
                
                # Checkbox state
                self.row_selections[row_idx] = False
                self.row_paths.append(file_path)

                cb_text = Text("[ ]", style="white")
                hash_text = Text(hash_short, style="cyan")
                name_text = Text(p.name, style="bold white")
                size_text = Text(format_size(g.size), style="green")
                mtime_text = Text(mtime, style="dim")
                path_text = Text(file_path, style="dim white")

                self.table.add_row(
                    cb_text, hash_text, name_text, size_text, mtime_text, path_text
                )
                row_idx += 1

        self.app.notify(f"Found {len(groups)} duplicate groups.")

    def action_toggle_row(self) -> None:
        """Toggle deletion selection on the highlighted row."""
        cursor_row = self.table.cursor_row
        if cursor_row is None or cursor_row >= len(self.row_paths):
            return

        current_val = self.row_selections[cursor_row]
        new_val = not current_val
        self.row_selections[cursor_row] = new_val

        # Update cell visual
        cell_text = Text("[x]", style="bold red") if new_val else Text("[ ]", style="white")
        self.table.update_cell_at((cursor_row, 0), cb_text := cell_text)

    def action_auto_select_newest(self) -> None:
        """Select older duplicates, leaving only the newest one intact."""
        self._apply_auto_select("keep_newest")

    def action_auto_select_oldest(self) -> None:
        """Select newer duplicates, leaving only the oldest one intact."""
        self._apply_auto_select("keep_oldest")

    def _apply_auto_select(self, strategy: str) -> None:
        if not self.groups:
            self.app.notify("No duplicates found yet. Scan first.", severity="warning")
            return

        self.row_selections = {k: False for k in self.row_selections}
        
        # Mark paths for deletion based on strategy
        paths_to_delete = set()
        for g in self.groups:
            to_delete = resolve_group(g, strategy=strategy)
            paths_to_delete.update(to_delete)

        # Update table rows
        for idx, path in enumerate(self.row_paths):
            if path in paths_to_delete:
                self.row_selections[idx] = True
                self.table.update_cell_at((idx, 0), Text("[x]", style="bold red"))
            else:
                self.table.update_cell_at((idx, 0), Text("[ ]", style="white"))

        self.app.notify(f"Selected {len(paths_to_delete)} files for deletion.")

    def action_delete_selected(self) -> None:
        selected_paths = [self.row_paths[idx] for idx, sel in self.row_selections.items() if sel]
        
        if not selected_paths:
            self.app.notify("No files selected.", severity="warning")
            return

        dry_run = self.query_one("#dup-dryrun-switch", Switch).value
        total_size = 0
        for path_str in selected_paths:
            try:
                total_size += Path(path_str).stat().st_size
            except OSError:
                pass

        if dry_run:
            self.app.notify(f"[DRY-RUN] Would delete {len(selected_paths)} files ({format_size(total_size)})")
            return

        # Trigger confirm modal
        desc = f"You are about to delete {len(selected_paths)} duplicate files, freeing {format_size(total_size)}."
        modal = ConfirmModal(
            title="Confirm Duplicate Deletion",
            description=desc,
            require_yes=(total_size >= 1_073_741_824) # Require type 'yes' if >= 1GB
        )

        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                self.execute_deletions(selected_paths)

        self.app.push_screen(modal, handle_confirm)

    @work(exclusive=True, thread=True)
    def execute_deletions(self, paths: list) -> None:
        history = self.app.history_manager
        success_count = 0
        batch_id = f"dup-del-{int(datetime.now().timestamp())}"

        for idx, path_str in enumerate(paths):
            try:
                p = Path(path_str)
                size = p.stat().st_size if p.exists() else 0
                
                # Safe delete moves file to ~/.macsweep/trash/
                trash_path = safe_delete(p)
                
                # Log to history
                history.log_delete(
                    source=path_str,
                    trash_path=str(trash_path),
                    size_bytes=size,
                    description=f"Duplicate removed: {p.name}",
                    batch_id=batch_id
                )
                success_count += 1
            except Exception as exc:
                self.app.call_from_thread(self.app.notify, f"Error deleting {Path(path_str).name}: {exc}", severity="error")

        self.app.call_from_thread(self.app.notify, f"Successfully removed {success_count} files.")
        
        # Re-scan current folder to refresh results
        def _rescan():
            path_str = self.query_one("#dup-path-input", Input).value.strip()
            self.run_duplicate_scan(Path(path_str).expanduser().resolve())
        self.app.call_from_thread(_rescan)

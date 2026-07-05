"""
MacSweep — Storage Scanner Screen
Provides visual breakdown of storage usage, top files, top directories, and file types.
"""

from pathlib import Path
from datetime import datetime
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Button, Label, TabbedContent, TabPane, DataTable, ProgressBar
from textual.binding import Binding
from textual import work
from rich.text import Text

from ..core.scanner import scan_directory, get_top_files, get_top_dirs, get_type_breakdown
from ..core.utils import format_size, size_color

class ScannerScreen(Screen):
    """Screen for scanning directory sizes."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("s", "start_scan", "Scan", show=True),
    ]

    def compose(self):
        yield Header()
        with Container(id="scanner-container"):
            yield Label("Storage Scanner", classes="screen-title")
            
            with Horizontal(id="path-selector-row"):
                yield Input(value=str(Path.home()), placeholder="Enter folder path to scan...", id="scan-path-input")
                yield Button("Scan Folder", variant="primary", id="scan-btn")

            # Progress overlay
            with Vertical(id="scan-progress-box"):
                yield Label("Scanning storage... Please wait.", id="scan-status-lbl")
                yield ProgressBar(total=100, show_percentage=False, id="scan-progress-bar")

            with TabbedContent(initial="top-files-tab", id="scanner-tabs"):
                with TabPane("Top Files", id="top-files-tab"):
                    self.files_table = DataTable(id="files-table")
                    yield self.files_table
                with TabPane("Top Folders", id="top-folders-tab"):
                    self.folders_table = DataTable(id="folders-table")
                    yield self.folders_table
                with TabPane("File Types", id="type-breakdown-tab"):
                    self.types_table = DataTable(id="types-table")
                    yield self.types_table

        yield Footer()

    def on_mount(self) -> None:
        self.files_table.cursor_type = "row"
        self.files_table.add_column("File Name", key="name")
        self.files_table.add_column("Size", key="size")
        self.files_table.add_column("Modified", key="modified")
        self.files_table.add_column("Full Path", key="path")

        self.folders_table.cursor_type = "row"
        self.folders_table.add_column("Folder Name", key="name")
        self.folders_table.add_column("Total Size", key="size")
        self.folders_table.add_column("Full Path", key="path")

        self.types_table.cursor_type = "row"
        self.types_table.add_column("Extension", key="ext")
        self.types_table.add_column("Count", key="count")
        self.types_table.add_column("Total Size", key="size")

        # Hide progress by default
        self.query_one("#scan-progress-box", Vertical).display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan-btn":
            self.action_start_scan()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_start_scan(self) -> None:
        path_str = self.query_one("#scan-path-input", Input).value.strip()
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            self.app.notify(f"Path does not exist: {path_str}", severity="error")
            return
        if not path.is_dir():
            self.app.notify(f"Path is not a directory: {path_str}", severity="error")
            return

        self.run_scanner_task(path)

    @work(exclusive=True, thread=True)
    def run_scanner_task(self, path: Path) -> None:
        """Run the scanning engine in a background thread."""
        self.app.call_from_thread(self.show_progress, True)
        self.app.call_from_thread(self.update_status, "Walking directories...")

        files = []
        count = 0

        def scan_callback(current_count):
            nonlocal count
            count = current_count
            self.app.call_from_thread(self.update_status, f"Found {count} files...")

        try:
            # We do a fast scan yield
            for file_entry in scan_directory(path, callback=scan_callback):
                files.append(file_entry)

            self.app.call_from_thread(self.update_status, "Compiling metrics...")

            # Extract top files, top folders, and type breakdowns
            top_files = get_top_files(path, n=50)
            top_dirs = get_top_dirs(path, n=50)
            type_breakdown = get_type_breakdown(path)

            self.app.call_from_thread(
                self.populate_results, top_files, top_dirs, type_breakdown
            )
            self.app.call_from_thread(self.app.notify, f"Scan completed! Analyzed {len(files)} files.")

        except Exception as exc:
            self.app.call_from_thread(self.app.notify, f"Scan failed: {exc}", severity="error")

        finally:
            self.app.call_from_thread(self.show_progress, False)

    def show_progress(self, show: bool) -> None:
        self.query_one("#scan-progress-box", Vertical).display = show
        self.query_one("#scan-btn", Button).disabled = show
        self.query_one("#scanner-tabs", TabbedContent).disabled = show

    def update_status(self, text: str) -> None:
        self.query_one("#scan-status-lbl", Label).update(text)

    def populate_results(self, top_files: list, top_dirs: list, type_breakdown: dict) -> None:
        # 1. Top Files
        self.files_table.clear()
        for f in top_files:
            mtime_str = f.mtime.strftime("%Y-%m-%d %H:%M") if isinstance(f.mtime, datetime) else str(f.mtime)
            self.files_table.add_row(
                Text(f.name, style="bold white"),
                Text(format_size(f.size), style=size_color(f.size)),
                Text(mtime_str, style="dim"),
                Text(str(f.path), style="dim")
            )

        # 2. Top Folders
        self.folders_table.clear()
        for d_path, d_size in top_dirs:
            name = Path(d_path).name or d_path
            self.folders_table.add_row(
                Text(name, style="bold white"),
                Text(format_size(d_size), style=size_color(d_size)),
                Text(str(d_path), style="dim")
            )

        # 3. Type Breakdown
        self.types_table.clear()
        # Sort type_breakdown by total_bytes desc
        sorted_types = sorted(type_breakdown.items(), key=lambda x: x[1][1], reverse=True)
        for ext, (count, total_bytes) in sorted_types:
            ext_label = ext if ext else "(no extension)"
            self.types_table.add_row(
                Text(ext_label, style="cyan"),
                Text(str(count), style="white"),
                Text(format_size(total_bytes), style=size_color(total_bytes))
            )

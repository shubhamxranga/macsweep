"""
MacSweep — Dashboard Screen
Home screen showing disk statistics, quick actions, and recent activity.
"""

from textual.screen import Screen
from textual.containers import Container, Grid, Vertical, Horizontal
from textual.widgets import Header, Footer, Label, Static, DataTable
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel

from ..widgets.size_bar import SizeBar
from ..core.utils import format_size
from ..core.scanner import get_disk_usage

class Dashboard(Screen):
    """Main home dashboard screen."""

    BINDINGS = [
        Binding("1", "switch_screen('scanner')", "Scanner", show=True),
        Binding("2", "switch_screen('duplicates')", "Duplicates", show=True),
        Binding("3", "switch_screen('organizer')", "Organizer", show=True),
        Binding("4", "switch_screen('cleaner')", "Cleaner", show=True),
        Binding("u", "undo_last", "Undo Last", show=True),
        Binding("r", "refresh_stats", "Refresh Stats", show=True),
        Binding("escape", "quit", "Quit", show=False),
    ]

    def compose(self):
        yield Header()
        with Container(id="dashboard-container"):
            # Title banner
            title_art = """
 ╔╦╗╔═╗╔═╗╔═╗╦ ╦╔═╗╔═╗╔═╗
 ║║║╠═╣║  ╚═╗║║║║╣ ║╣ ╠═╝
 ╩ ╩╩ ╩╚═╝╚═╝╚╩╝╚═╝╚═╝╩  
 100% Local macOS Storage Manager
            """
            yield Static(Panel(Text(title_art, style="cyan bold", justify="center"), border_style="cyan"))

            # Disk usage bar
            self.size_bar = SizeBar()
            yield self.size_bar

            # Stats Grid
            with Grid(id="stats-grid"):
                self.stats_files = Static("Files Logged: 0", classes="stat-box")
                self.stats_saved = Static("Space Saved: 0 B", classes="stat-box")
                yield self.stats_files
                yield self.stats_saved

            # Recent Activity Title
            yield Label("Recent Activity:", classes="section-title")

            # Recent Operations Table
            self.history_table = DataTable(id="history-table")
            yield self.history_table

            # Help box
            yield Static(
                "Use number keys [bold cyan]1-4[/bold cyan] to jump to screens. "
                "Press [bold cyan]u[/bold cyan] to undo the last move/delete.",
                classes="help-box"
            )
        yield Footer()

    def on_mount(self) -> None:
        self.history_table.cursor_type = "row"
        self.history_table.add_column("Time", key="time")
        self.history_table.add_column("Action", key="action")
        self.history_table.add_column("Details", key="details")
        self.history_table.add_column("Size", key="size")
        self.history_table.add_column("Status", key="status")
        
        self.refresh_all()

    def refresh_all(self) -> None:
        # Load disk usage
        try:
            total, used, free = get_disk_usage()
            self.size_bar.update_sizes(total, used, free)
        except Exception:
            pass

        # Load historical statistics
        history = self.app.history_manager
        self.stats_files.update(f"🧹 Total Operations: [bold cyan]{history.operation_count}[/bold cyan]")
        self.stats_saved.update(f"🌱 Total Space Saved: [bold green]{format_size(history.total_space_reclaimed)}[/bold green]")

        # Populate history table
        self.history_table.clear()
        recent_entries = history.get_recent(5)
        for entry in recent_entries:
            time_str = entry.timestamp.split("T")[1][:5] if "T" in entry.timestamp else entry.timestamp[:5]
            action_badge = Text(entry.action.upper(), style="bold red" if entry.action == "delete" else "bold green")
            
            desc = entry.description
            size_str = format_size(entry.size_bytes) if entry.size_bytes > 0 else "-"
            
            status = Text("UNDONE", style="strike dim red") if entry.undone else Text("ACTIVE", style="green")

            self.history_table.add_row(
                Text(time_str, style="dim"),
                action_badge,
                Text(desc, overflow="ellipsis"),
                Text(size_str, style="cyan"),
                status
            )

    def action_switch_screen(self, screen_name: str) -> None:
        self.app.push_screen(screen_name)

    def action_undo_last(self) -> None:
        results = self.app.history_manager.undo_last(1)
        if results:
            self.app.notify(results[0])
            self.refresh_all()
        else:
            self.app.notify("No actions to undo", severity="warning")

    def action_refresh_stats(self) -> None:
        self.refresh_all()
        self.app.notify("Stats refreshed")

    def on_screen_resume(self) -> None:
        self.refresh_all()

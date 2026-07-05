"""
MacSweep — Size Bar Widget
Visualizes disk usage (used vs free) using a color-coded bar chart.
"""

from textual.widgets import Static
from rich.text import Text
from ..core.utils import format_size

class SizeBar(Static):
    """A widget to display used vs free disk space as a horizontal bar."""

    DEFAULT_CSS = """
    SizeBar {
        background: $surface;
        border: solid $primary-darken-2;
        padding: 1 2;
        margin: 1 0;
        height: auto;
    }
    
    .title {
        text-style: bold;
        color: $accent;
    }
    """

    def __init__(self, total_bytes: int = 0, used_bytes: int = 0, free_bytes: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.total = total_bytes
        self.used = used_bytes
        self.free = free_bytes

    def update_sizes(self, total: int, used: int, free: int):
        self.total = total
        self.used = used
        self.free = free
        self.refresh()

    def render(self) -> Text:
        if self.total == 0:
            return Text("Disk details loading...")

        pct = (self.used / self.total) * 100
        
        # Color based on severity
        if pct >= 90:
            bar_color = "red"
        elif pct >= 75:
            bar_color = "yellow"
        else:
            bar_color = "green"

        width = 50
        used_chars = int((self.used / self.total) * width)
        free_chars = width - used_chars

        bar_text = Text()
        bar_text.append("█" * used_chars, style=bar_color)
        bar_text.append("░" * free_chars, style="dim white")

        summary = Text()
        summary.append("Disk Space Usage:\n", style="bold cyan")
        summary.append(f"{bar_text}\n\n")
        summary.append("Used: ", style="bold")
        summary.append(f"{format_size(self.used)} ({pct:.1f}%)", style=bar_color)
        summary.append("  |  Free: ", style="bold")
        summary.append(f"{format_size(self.free)}", style="green")
        summary.append("  |  Total: ", style="bold")
        summary.append(f"{format_size(self.total)}", style="white")

        return summary

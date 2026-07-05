"""
MacSweep — File Table Widget
Wrapper around DataTable to display file lists with custom color rendering.
"""

from textual.widgets import DataTable
from rich.text import Text
from datetime import datetime
from ..core.utils import format_size, size_color

class FileTable(DataTable):
    """Custom table widget for file entries."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_column("Name", key="name")
        self.add_column("Size", key="size")
        self.add_column("Modified", key="modified")
        self.add_column("Type/Ext", key="ext")
        self.add_column("Full Path", key="path")

    def load_files(self, entries: list) -> None:
        """
        Populate table with file entries.
        Each entry can be an object with properties or a dict.
        """
        self.clear()
        
        # Sort entries by size desc by default
        sorted_entries = sorted(
            entries,
            key=lambda e: getattr(e, "size", e.get("size", 0)) if not isinstance(e, dict) else e.get("size", 0),
            reverse=True
        )

        for e in sorted_entries:
            if isinstance(e, dict):
                path = e.get("path", "")
                name = e.get("name", "")
                size = e.get("size", 0)
                mtime = e.get("mtime", "")
                ext = e.get("ext", "")
            else:
                path = str(e.path)
                name = e.name
                size = e.size
                mtime = e.mtime
                ext = e.ext

            # Format modified time
            if isinstance(mtime, (int, float)):
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            elif isinstance(mtime, datetime):
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
            else:
                mtime_str = str(mtime)

            # Apply size-based color coding
            color = size_color(size)
            name_text = Text(name, style="bold white")
            size_text = Text(format_size(size), style=color)
            mtime_text = Text(mtime_str, style="dim white")
            ext_text = Text(ext, style="cyan")
            path_text = Text(path, style="dim white")

            self.add_row(name_text, size_text, mtime_text, ext_text, path_text)

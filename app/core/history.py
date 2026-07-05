"""
MacSweep — History & Undo System
Every file operation is logged. Every operation can be undone.
Storage: ~/.macsweep/history.json
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional

from .utils import (
    HISTORY_FILE,
    MACSWEEP_DIR,
    ensure_dirs,
    restore_from_trash,
    safe_move,
)


@dataclass
class HistoryEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    action: str = ""          # "move" | "delete" | "organize" | "clean"
    source: str = ""          # original path
    destination: str = ""     # new path or trash path
    size_bytes: int = 0
    description: str = ""     # human-readable summary
    undone: bool = False
    batch_id: str = ""        # group related ops (e.g., one "organize" run)


class HistoryManager:
    """Thread-safe history manager with undo support."""

    def __init__(self):
        ensure_dirs()
        self._entries: list[HistoryEntry] = []
        self._load()

    def _load(self):
        """Load history from disk."""
        if HISTORY_FILE.exists():
            try:
                data = json.loads(HISTORY_FILE.read_text())
                self._entries = [HistoryEntry(**e) for e in data]
            except (json.JSONDecodeError, TypeError):
                self._entries = []
        else:
            self._entries = []

    def _save(self):
        """Persist history to disk."""
        ensure_dirs()
        data = [asdict(e) for e in self._entries]
        HISTORY_FILE.write_text(json.dumps(data, indent=2))

    def log_move(self, source: str, destination: str,
                 size_bytes: int = 0, description: str = "",
                 batch_id: str = "") -> HistoryEntry:
        """Log a file move operation."""
        entry = HistoryEntry(
            action="move",
            source=str(source),
            destination=str(destination),
            size_bytes=size_bytes,
            description=description or f"Moved {Path(source).name}",
            batch_id=batch_id,
        )
        self._entries.append(entry)
        self._save()
        return entry

    def log_delete(self, source: str, trash_path: str,
                   size_bytes: int = 0, description: str = "",
                   batch_id: str = "") -> HistoryEntry:
        """Log a file deletion (moved to trash staging)."""
        entry = HistoryEntry(
            action="delete",
            source=str(source),
            destination=str(trash_path),
            size_bytes=size_bytes,
            description=description or f"Deleted {Path(source).name}",
            batch_id=batch_id,
        )
        self._entries.append(entry)
        self._save()
        return entry

    def log_clean(self, target_name: str, path: str,
                  size_bytes: int, batch_id: str = "") -> HistoryEntry:
        """Log a cache/junk cleanup operation."""
        entry = HistoryEntry(
            action="clean",
            source=str(path),
            destination="",
            size_bytes=size_bytes,
            description=f"Cleaned {target_name} ({path})",
            batch_id=batch_id,
        )
        self._entries.append(entry)
        self._save()
        return entry

    def undo_last(self, n: int = 1) -> list[str]:
        """Undo the last N operations. Returns list of result messages."""
        results = []
        undoable = [e for e in reversed(self._entries) if not e.undone]

        for entry in undoable[:n]:
            msg = self._undo_entry(entry)
            results.append(msg)

        self._save()
        return results

    def undo_by_id(self, entry_id: str) -> str:
        """Undo a specific operation by its ID."""
        for entry in self._entries:
            if entry.id == entry_id and not entry.undone:
                msg = self._undo_entry(entry)
                self._save()
                return msg
        return f"No undoable entry found with id: {entry_id}"

    def undo_batch(self, batch_id: str) -> list[str]:
        """Undo all operations in a batch."""
        results = []
        batch_entries = [
            e for e in reversed(self._entries)
            if e.batch_id == batch_id and not e.undone
        ]
        for entry in batch_entries:
            msg = self._undo_entry(entry)
            results.append(msg)
        self._save()
        return results

    def _undo_entry(self, entry: HistoryEntry) -> str:
        """Execute the undo for a single entry."""
        try:
            if entry.action == "move":
                # Move the file back to its original location
                src = Path(entry.destination)
                dst = Path(entry.source)
                if src.exists():
                    safe_move(src, dst)
                    entry.undone = True
                    return f"✓ Restored: {dst.name} → {dst.parent}"
                else:
                    return f"✗ Cannot undo: file no longer at {src}"

            elif entry.action == "delete":
                # Restore from trash
                trash_path = Path(entry.destination)
                original = Path(entry.source)
                if trash_path.exists():
                    restore_from_trash(trash_path, original)
                    entry.undone = True
                    return f"✓ Restored from trash: {original.name}"
                else:
                    return f"✗ Cannot undo: trash file missing at {trash_path}"

            elif entry.action == "clean":
                entry.undone = True
                return f"⚠ Cache cleanup cannot be undone: {entry.description}"

            else:
                return f"✗ Unknown action type: {entry.action}"

        except Exception as exc:
            return f"✗ Undo failed: {exc}"

    def get_recent(self, n: int = 20) -> list[HistoryEntry]:
        """Get the N most recent history entries."""
        return list(reversed(self._entries[-n:]))

    def get_all(self) -> list[HistoryEntry]:
        """Get all history entries (newest first)."""
        return list(reversed(self._entries))

    def clear_history(self):
        """Clear all history entries."""
        self._entries = []
        self._save()

    @property
    def total_space_reclaimed(self) -> int:
        """Total bytes reclaimed across all non-undone operations."""
        return sum(
            e.size_bytes for e in self._entries
            if not e.undone and e.action in ("delete", "clean")
        )

    @property
    def operation_count(self) -> int:
        """Total number of operations logged."""
        return len(self._entries)

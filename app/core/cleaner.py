"""
MacSweep — Cache & Junk Cleaner
Scans known macOS cache locations, developer caches, and junk files.
Computes sizes and provides safe cleanup with full history logging.
"""

import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

from .utils import get_dir_size, is_safe_path
from .history import HistoryManager


@dataclass
class JunkTarget:
    """A detected cache/junk location that can be cleaned."""
    name: str
    path: str
    size_bytes: int
    safe_level: str  # 'safe' | 'caution'
    description: str


# ── Junk location definitions ───────────────────────────────────────

_HOME = Path.home()

_JUNK_LOCATIONS = [
    {
        "name": "pip cache",
        "path": _HOME / ".cache" / "pip",
        "safe_level": "safe",
        "description": "Python pip download cache. Safe to remove; pip will re-download as needed.",
    },
    {
        "name": "npm cache",
        "path": _HOME / ".npm" / "_cacache",
        "safe_level": "safe",
        "description": "Node.js npm cache. Safe to remove; npm will rebuild as needed.",
    },
    {
        "name": "Homebrew cache",
        "path": _HOME / "Library" / "Caches" / "Homebrew",
        "safe_level": "safe",
        "description": "Homebrew downloaded bottles and source tarballs.",
    },
    {
        "name": "Xcode DerivedData",
        "path": _HOME / "Library" / "Developer" / "Xcode" / "DerivedData",
        "safe_level": "caution",
        "description": "Xcode build artifacts. Removing forces full rebuilds of all projects.",
    },
    {
        "name": "Yarn cache",
        "path": _HOME / ".cache" / "yarn",
        "safe_level": "safe",
        "description": "Yarn package manager cache. Safe to remove.",
    },
    {
        "name": "CocoaPods cache",
        "path": _HOME / "Library" / "Caches" / "CocoaPods",
        "safe_level": "safe",
        "description": "CocoaPods spec and download cache.",
    },
    {
        "name": "System Trash",
        "path": _HOME / ".Trash",
        "safe_level": "caution",
        "description": "macOS Trash. Files here are already 'deleted' but still using disk space.",
    },
]


def _scan_directory_targets() -> list[JunkTarget]:
    """Scan the standard directory-based junk locations."""
    targets: list[JunkTarget] = []

    for loc in _JUNK_LOCATIONS:
        p = Path(loc["path"])
        if p.exists() and p.is_dir():
            try:
                size = get_dir_size(p)
                if size > 0:
                    targets.append(JunkTarget(
                        name=loc["name"],
                        path=str(p),
                        size_bytes=size,
                        safe_level=loc["safe_level"],
                        description=loc["description"],
                    ))
            except (PermissionError, OSError):
                continue

    return targets


def _scan_ds_store() -> Optional[JunkTarget]:
    """
    Find .DS_Store files recursively from home, limited to depth 5.
    Returns a single JunkTarget representing all found .DS_Store files.
    """
    home = str(_HOME)
    total_size = 0
    count = 0

    for dirpath, dirnames, filenames in os.walk(home):
        # Enforce depth limit
        rel = os.path.relpath(dirpath, home)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= 5:
            dirnames.clear()
            continue

        # Skip hidden directories (except home itself) and library dirs
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d != "Library"
        ]

        for fname in filenames:
            if fname == ".DS_Store":
                fpath = os.path.join(dirpath, fname)
                try:
                    total_size += os.path.getsize(fpath)
                    count += 1
                except (PermissionError, OSError):
                    continue

    if count > 0:
        return JunkTarget(
            name=".DS_Store files",
            path=str(_HOME),
            size_bytes=total_size,
            safe_level="safe",
            description=f"Found {count} .DS_Store files. These are Finder metadata and safe to remove.",
        )
    return None


def _scan_old_logs() -> Optional[JunkTarget]:
    """
    Find .log files older than 30 days under ~/Library/Logs.
    Returns a single JunkTarget representing all old logs found.
    """
    logs_dir = _HOME / "Library" / "Logs"
    if not logs_dir.exists():
        return None

    cutoff = datetime.now() - timedelta(days=30)
    total_size = 0
    count = 0

    for dirpath, dirnames, filenames in os.walk(str(logs_dir)):
        for fname in filenames:
            if not fname.endswith(".log"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(fpath)
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if mtime < cutoff:
                    total_size += stat.st_size
                    count += 1
            except (PermissionError, OSError):
                continue

    if count > 0:
        return JunkTarget(
            name="Old log files",
            path=str(logs_dir),
            size_bytes=total_size,
            safe_level="safe",
            description=f"Found {count} log files older than 30 days in ~/Library/Logs.",
        )
    return None


def scan_junk() -> list[JunkTarget]:
    """
    Scan all known junk/cache locations on macOS.

    Returns:
        List of JunkTarget objects, sorted by size descending.
    """
    targets = _scan_directory_targets()

    ds_target = _scan_ds_store()
    if ds_target:
        targets.append(ds_target)

    log_target = _scan_old_logs()
    if log_target:
        targets.append(log_target)

    # Sort by size, largest first
    targets.sort(key=lambda t: t.size_bytes, reverse=True)
    return targets


def _remove_ds_store_files(base_path: str) -> tuple[int, int]:
    """Remove .DS_Store files recursively (depth limited to 5). Returns (count, bytes)."""
    home = base_path
    total_removed = 0
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(home):
        rel = os.path.relpath(dirpath, home)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= 5:
            dirnames.clear()
            continue

        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d != "Library"
        ]

        for fname in filenames:
            if fname == ".DS_Store":
                fpath = os.path.join(dirpath, fname)
                try:
                    size = os.path.getsize(fpath)
                    os.remove(fpath)
                    total_removed += 1
                    total_bytes += size
                except (PermissionError, OSError):
                    continue

    return total_removed, total_bytes


def _remove_old_logs(logs_dir: str) -> tuple[int, int]:
    """Remove .log files older than 30 days. Returns (count, bytes)."""
    cutoff = datetime.now() - timedelta(days=30)
    total_removed = 0
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(logs_dir):
        for fname in filenames:
            if not fname.endswith(".log"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(fpath)
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if mtime < cutoff:
                    size = stat.st_size
                    os.remove(fpath)
                    total_removed += 1
                    total_bytes += size
            except (PermissionError, OSError):
                continue

    return total_removed, total_bytes


def clean_targets(
    targets: list[JunkTarget],
    history_manager: HistoryManager,
) -> list[str]:
    """
    Remove selected junk targets and log to history.

    Args:
        targets: List of JunkTarget objects to clean.
        history_manager: HistoryManager for logging operations.

    Returns:
        List of result strings describing what was cleaned.
    """
    results: list[str] = []
    batch_id = str(uuid.uuid4())[:8]
    total_freed = 0

    for target in targets:
        try:
            if target.name == ".DS_Store files":
                count, freed = _remove_ds_store_files(target.path)
                results.append(f"✓ Removed {count} .DS_Store files")
                total_freed += freed

                history_manager.log_clean(
                    target_name=target.name,
                    path=target.path,
                    size_bytes=freed,
                    batch_id=batch_id,
                )

            elif target.name == "Old log files":
                count, freed = _remove_old_logs(target.path)
                results.append(f"✓ Removed {count} old log files")
                total_freed += freed

                history_manager.log_clean(
                    target_name=target.name,
                    path=target.path,
                    size_bytes=freed,
                    batch_id=batch_id,
                )

            else:
                # Directory-based target — remove entire directory
                p = Path(target.path)
                if p.exists() and p.is_dir():
                    if not is_safe_path(target.path):
                        results.append(f"✗ Skipped (unsafe path): {target.name}")
                        continue

                    shutil.rmtree(str(p), ignore_errors=True)
                    results.append(f"✓ Cleaned {target.name}")
                    total_freed += target.size_bytes

                    history_manager.log_clean(
                        target_name=target.name,
                        path=target.path,
                        size_bytes=target.size_bytes,
                        batch_id=batch_id,
                    )
                else:
                    results.append(f"⊘ Skipped (not found): {target.name}")

        except Exception as exc:
            results.append(f"✗ Error cleaning {target.name}: {exc}")

    # Summary
    from .utils import format_size
    results.append(
        f"\n{'─' * 40}\n"
        f"Freed {format_size(total_freed)} total, batch: {batch_id}"
    )

    return results

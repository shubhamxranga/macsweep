"""
MacSweep — Storage Scanner Engine
Fast recursive directory scanning using os.scandir() (optimized for APFS).
Provides top files/dirs by size, type breakdowns, and disk usage info.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Callable, Optional
from collections import defaultdict

from .utils import is_safe_path, get_extension, get_dir_size


@dataclass
class FileEntry:
    """Represents a single file or directory discovered during scanning."""
    path: str
    name: str
    size: int
    mtime: datetime
    ext: str
    is_dir: bool


def scan_directory(
    path: str | Path,
    max_depth: Optional[int] = None,
    callback: Optional[Callable[[int], None]] = None,
):
    """
    Recursively scan a directory, yielding FileEntry objects.

    Uses os.scandir() for fast traversal on APFS. Skips symlinks and
    paths that fail is_safe_path(). Calls callback(current_count) every
    100 files for progress reporting.

    Args:
        path: Root directory to scan.
        max_depth: Maximum recursion depth (None = unlimited).
        callback: Progress callback, called every 100 files with the
                  current file count.

    Yields:
        FileEntry for each file/directory discovered.
    """
    path = str(Path(path).resolve())
    count = 0

    def _scan(dir_path: str, current_depth: int):
        nonlocal count

        try:
            entries = os.scandir(dir_path)
        except PermissionError:
            return
        except OSError:
            return

        with entries:
            for entry in entries:
                try:
                    # Skip symlinks
                    if entry.is_symlink():
                        continue

                    full_path = entry.path

                    # Skip unsafe paths
                    if not is_safe_path(full_path):
                        continue

                    stat_info = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=False)

                    file_entry = FileEntry(
                        path=full_path,
                        name=entry.name,
                        size=stat_info.st_size if not is_dir else 0,
                        mtime=datetime.fromtimestamp(stat_info.st_mtime),
                        ext=get_extension(entry.name) if not is_dir else "",
                        is_dir=is_dir,
                    )

                    count += 1
                    yield file_entry

                    # Progress callback every 100 files
                    if callback and count % 100 == 0:
                        callback(count)

                    # Recurse into subdirectories
                    if is_dir:
                        if max_depth is None or current_depth < max_depth:
                            yield from _scan(full_path, current_depth + 1)

                except PermissionError:
                    continue
                except OSError:
                    continue

    yield from _scan(path, 0)


def get_top_files(path: str | Path, n: int = 20) -> list[FileEntry]:
    """
    Get the N largest files under a directory, sorted by size descending.

    Args:
        path: Directory to scan.
        n: Number of top files to return.

    Returns:
        List of FileEntry objects sorted by size (largest first).
    """
    files: list[FileEntry] = []

    for entry in scan_directory(path):
        if not entry.is_dir and entry.size > 0:
            files.append(entry)

    files.sort(key=lambda f: f.size, reverse=True)
    return files[:n]


def get_top_dirs(path: str | Path, n: int = 20) -> list[tuple[str, int]]:
    """
    Get the N largest immediate subdirectories, sorted by total size descending.

    Aggregates file sizes per immediate subdirectory of the given path.

    Args:
        path: Parent directory to analyze.
        n: Number of top directories to return.

    Returns:
        List of (dir_path, total_size_bytes) tuples sorted by size.
    """
    path = Path(path).resolve()
    dir_sizes: list[tuple[str, int]] = []

    try:
        with os.scandir(str(path)) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if not is_safe_path(entry.path):
                            continue
                        total = get_dir_size(entry.path)
                        dir_sizes.append((entry.path, total))
                except PermissionError:
                    continue
                except OSError:
                    continue
    except PermissionError:
        pass
    except OSError:
        pass

    dir_sizes.sort(key=lambda x: x[1], reverse=True)
    return dir_sizes[:n]


def get_type_breakdown(path: str | Path) -> dict[str, tuple[int, int]]:
    """
    Get a breakdown of file types (extensions) under a directory.

    Args:
        path: Directory to analyze.

    Returns:
        Dict mapping extension string (e.g. '.pdf') to (count, total_bytes).
        Files with no extension use '' as the key.
    """
    breakdown: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    for entry in scan_directory(path):
        if not entry.is_dir:
            ext = entry.ext or "(no extension)"
            breakdown[ext][0] += 1
            breakdown[ext][1] += entry.size

    # Convert to immutable tuples
    return {ext: (vals[0], vals[1]) for ext, vals in breakdown.items()}


def get_disk_usage() -> tuple[int, int, int]:
    """
    Get overall disk usage for the boot volume.

    Returns:
        Tuple of (total_bytes, used_bytes, free_bytes).
    """
    usage = shutil.disk_usage("/")
    return (usage.total, usage.used, usage.free)

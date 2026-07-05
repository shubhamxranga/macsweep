"""
MacSweep — Duplicate Finder Engine
Two-phase duplicate detection: size grouping → quick hash → full hash.
Supports multiple resolution strategies for choosing which copy to keep.
"""

import os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Optional
from collections import defaultdict

from .utils import hash_file, is_safe_path


@dataclass
class DuplicateGroup:
    """A group of files that are byte-identical duplicates."""
    hash: str
    size: int
    paths: list[str] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        """Space wasted by keeping all copies (all but one are redundant)."""
        return self.size * (len(self.paths) - 1)


def find_duplicates(
    path: str | Path,
    min_size: int = 1024,
    callback: Optional[Callable[[str, int, int], None]] = None,
) -> list[DuplicateGroup]:
    """
    Find duplicate files under a directory using a two-phase approach.

    Phase 1: Group files by size (files with unique sizes can't be duplicates).
    Phase 2: For size-matched groups, compare quick 64KB hashes, then full
             hashes for groups that match on the quick hash.

    Args:
        path: Root directory to scan for duplicates.
        min_size: Minimum file size in bytes to consider (skip tiny files).
        callback: Progress callback(phase, current, total) where phase is
                  'scanning', 'hashing_quick', or 'hashing_full'.

    Returns:
        List of DuplicateGroup objects, sorted by wasted_bytes descending.
    """
    path = Path(path).resolve()

    # ── Phase 1: Group by size ──────────────────────────────────────
    size_groups: dict[int, list[str]] = defaultdict(list)
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(str(path)):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                # Skip symlinks
                if os.path.islink(fpath):
                    continue
                # Skip unsafe paths
                if not is_safe_path(fpath):
                    continue

                st = os.stat(fpath)
                if st.st_size >= min_size:
                    size_groups[st.st_size].append(fpath)
                    file_count += 1

                    if callback and file_count % 100 == 0:
                        callback("scanning", file_count, 0)

            except (PermissionError, OSError):
                continue

    # Keep only sizes with multiple files
    candidates = {
        sz: paths for sz, paths in size_groups.items() if len(paths) > 1
    }

    if not candidates:
        return []

    # ── Phase 2a: Quick hash (first 64KB) ───────────────────────────
    total_to_hash = sum(len(paths) for paths in candidates.values())
    hashed = 0
    quick_hash_groups: dict[str, list[str]] = defaultdict(list)

    for file_size, paths in candidates.items():
        for fpath in paths:
            try:
                qhash = hash_file(fpath, quick=True)
                key = f"{file_size}:{qhash}"
                quick_hash_groups[key].append(fpath)
            except (PermissionError, OSError):
                continue

            hashed += 1
            if callback and hashed % 50 == 0:
                callback("hashing_quick", hashed, total_to_hash)

    # Keep only quick-hash groups with multiple files
    quick_candidates = {
        k: paths for k, paths in quick_hash_groups.items() if len(paths) > 1
    }

    if not quick_candidates:
        return []

    # ── Phase 2b: Full hash ─────────────────────────────────────────
    total_full = sum(len(paths) for paths in quick_candidates.values())
    full_hashed = 0
    full_hash_groups: dict[str, list[str]] = defaultdict(list)

    for key, paths in quick_candidates.items():
        file_size = int(key.split(":")[0])
        for fpath in paths:
            try:
                full = hash_file(fpath, quick=False)
                full_hash_groups[full].append(fpath)
            except (PermissionError, OSError):
                continue

            full_hashed += 1
            if callback and full_hashed % 20 == 0:
                callback("hashing_full", full_hashed, total_full)

    # ── Build results ───────────────────────────────────────────────
    results: list[DuplicateGroup] = []

    for full_hash, paths in full_hash_groups.items():
        if len(paths) > 1:
            # Get file size from the first file
            try:
                fsize = os.path.getsize(paths[0])
            except OSError:
                fsize = 0

            group = DuplicateGroup(
                hash=full_hash,
                size=fsize,
                paths=sorted(paths),
            )
            results.append(group)

    # Sort by wasted space, most wasteful first
    results.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return results


def resolve_group(
    group: DuplicateGroup,
    strategy: str = "keep_newest",
) -> list[str]:
    """
    Determine which files to remove from a duplicate group.

    Args:
        group: The DuplicateGroup to resolve.
        strategy: Resolution strategy:
            - 'keep_newest': Keep the most recently modified file.
            - 'keep_oldest': Keep the oldest file.
            - 'keep_first': Keep the first file alphabetically.

    Returns:
        List of file paths that should be removed (all except the keeper).
    """
    if len(group.paths) <= 1:
        return []

    paths = list(group.paths)

    if strategy == "keep_newest":
        # Sort by mtime descending — keep the first (newest)
        paths.sort(key=lambda p: _get_mtime(p), reverse=True)
    elif strategy == "keep_oldest":
        # Sort by mtime ascending — keep the first (oldest)
        paths.sort(key=lambda p: _get_mtime(p))
    elif strategy == "keep_first":
        # Sort alphabetically — keep the first
        paths.sort()
    else:
        # Default to keep_newest
        paths.sort(key=lambda p: _get_mtime(p), reverse=True)

    # Keep the first, remove the rest
    return paths[1:]


def _get_mtime(path: str) -> float:
    """Get file modification time, returning 0.0 on error."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0

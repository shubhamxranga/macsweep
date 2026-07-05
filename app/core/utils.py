"""
MacSweep — Core Utilities
Path safety, size formatting, safe file operations.
All destructive operations go through staging before permanent deletion.
"""

import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# Blocked paths — never touch these
BLOCKED_ROOTS = frozenset({
    "/System",
    "/Library",
    "/usr",
    "/bin",
    "/sbin",
    "/private/var",
    "/Volumes/Macintosh HD",
})

BLOCKED_PREFIXES = (
    "/System/",
    "/usr/",
    "/bin/",
    "/sbin/",
    "/private/var/",
)

MACSWEEP_DIR = Path.home() / ".macsweep"
TRASH_DIR = MACSWEEP_DIR / "trash"
HISTORY_FILE = MACSWEEP_DIR / "history.json"
CONFIG_FILE = MACSWEEP_DIR / "config.json"
CMD_HISTORY_FILE = MACSWEEP_DIR / "cmd_history.json"


def ensure_dirs():
    """Create MacSweep working directories if they don't exist."""
    MACSWEEP_DIR.mkdir(exist_ok=True)
    TRASH_DIR.mkdir(exist_ok=True)


def format_size(size_bytes: int) -> str:
    """Human-readable file size. 0 → '0 B', 1536 → '1.5 KB', etc."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    if i == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[i]}"


def is_safe_path(path: str | Path) -> bool:
    """
    Returns True only if path is safe to operate on.
    Blocks /System, /Library (root), /usr, boot volumes.
    """
    p = str(Path(path).resolve())

    # Block exact root-level system dirs
    if p in BLOCKED_ROOTS:
        return False

    # Block anything under system prefixes
    for prefix in BLOCKED_PREFIXES:
        if p.startswith(prefix):
            # Allow user temporary directories inside /private/var/folders/
            if prefix == "/private/var/" and p.startswith("/private/var/folders/"):
                continue
            return False

    # Special case: /Library (root) is blocked, but ~/Library is fine
    if p == "/Library" or p.startswith("/Library/"):
        return False

    return True


def get_file_age(path: str | Path) -> timedelta:
    """Time since file was last modified."""
    mtime = os.path.getmtime(str(path))
    return datetime.now() - datetime.fromtimestamp(mtime)


def _collision_free_name(dest: Path) -> Path:
    """If dest exists, append (1), (2), etc. until unique."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def safe_move(src: str | Path, dst: str | Path) -> Path:
    """
    Move a file/dir, creating parent dirs and handling name collisions.
    Returns the actual destination path.
    """
    src = Path(src)
    dst = Path(dst)

    if not src.exists():
        raise FileNotFoundError(f"Source does not exist: {src}")

    if not is_safe_path(src):
        raise PermissionError(f"Blocked: cannot move from system path: {src}")

    # Create parent directory
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Handle collision
    dst = _collision_free_name(dst)

    shutil.move(str(src), str(dst))
    return dst


def safe_delete(path: str | Path) -> Path:
    """
    'Delete' a file by moving it to ~/.macsweep/trash/ staging area.
    The original path is encoded in the trash filename for later recovery.
    Returns the path in the trash directory.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    if not is_safe_path(path):
        raise PermissionError(f"Blocked: cannot delete system path: {path}")

    ensure_dirs()

    # Encode original path into the trash filename
    # /Users/bob/Downloads/file.txt → _Users_bob_Downloads_file.txt
    encoded_name = str(path).replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trash_name = f"{timestamp}__{encoded_name}"
    trash_path = TRASH_DIR / trash_name

    shutil.move(str(path), str(trash_path))
    return trash_path


def restore_from_trash(trash_path: str | Path, original_path: str | Path) -> Path:
    """Restore a file from the MacSweep trash to its original location."""
    trash_path = Path(trash_path)
    original_path = Path(original_path)

    if not trash_path.exists():
        raise FileNotFoundError(f"Trash file not found: {trash_path}")

    original_path.parent.mkdir(parents=True, exist_ok=True)
    dest = _collision_free_name(original_path)
    shutil.move(str(trash_path), str(dest))
    return dest


def hash_file(path: str | Path, algorithm: str = "sha256",
              chunk_size: int = 65536, quick: bool = False) -> str:
    """
    Hash a file. If quick=True, only hash the first 64KB (for pre-filtering).
    """
    h = hashlib.new(algorithm)
    with open(str(path), "rb") as f:
        if quick:
            data = f.read(chunk_size)
            if data:
                h.update(data)
        else:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                h.update(data)
    return h.hexdigest()


def get_dir_size(path: str | Path) -> int:
    """Total size of all files under a directory, in bytes."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(str(path)):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except (OSError, PermissionError):
                pass
    return total


def get_extension(path: str | Path) -> str:
    """Return lowercase file extension, e.g. '.pdf'. Returns '' for no ext."""
    return Path(path).suffix.lower()


def size_color(size_bytes: int) -> str:
    """Return a Rich/Textual color name based on file size thresholds."""
    if size_bytes >= 1_073_741_824:   # >= 1 GB
        return "red"
    elif size_bytes >= 104_857_600:    # >= 100 MB
        return "yellow"
    elif size_bytes >= 10_485_760:     # >= 10 MB
        return "bright_yellow"
    else:
        return "green"

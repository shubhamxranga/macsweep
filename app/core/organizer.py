"""
MacSweep — File Organizer Engine
Loads organization rules from YAML, plans moves via fnmatch pattern matching,
and executes them with full history logging and undo support.
"""

import os
import uuid
import fnmatch
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

import yaml

from .utils import safe_move, is_safe_path, get_extension
from .history import HistoryManager


@dataclass
class OrgRule:
    """A file organization rule mapping file patterns to a destination folder."""
    name: str
    patterns: list[str] = field(default_factory=list)
    dest: str = ""


@dataclass
class PlannedMove:
    """A planned file move operation before execution."""
    src: Path
    dst: Path
    rule_name: str


def _default_rules_path() -> Path:
    """Locate the bundled default_rules.yaml file."""
    return Path(__file__).parent.parent / "config" / "default_rules.yaml"


def load_rules(rules_path: Optional[str | Path] = None) -> list[OrgRule]:
    """
    Load organization rules from a YAML file.

    Args:
        rules_path: Path to a custom rules YAML file.
                    Defaults to the bundled default_rules.yaml.

    Returns:
        List of OrgRule objects parsed from the YAML.

    Raises:
        FileNotFoundError: If the rules file does not exist.
        ValueError: If the YAML structure is invalid.
    """
    path = Path(rules_path) if rules_path else _default_rules_path()

    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not data or "rules" not in data:
        raise ValueError(f"Invalid rules file: missing 'rules' key in {path}")

    rules: list[OrgRule] = []
    for entry in data["rules"]:
        rule = OrgRule(
            name=entry.get("name", "Unknown"),
            patterns=entry.get("match", []),
            dest=entry.get("dest", "Other/"),
        )
        rules.append(rule)

    return rules


def _match_file(filename: str, rules: list[OrgRule]) -> Optional[OrgRule]:
    """Find the first rule whose patterns match the given filename."""
    name_lower = filename.lower()
    for rule in rules:
        for pattern in rule.patterns:
            if fnmatch.fnmatch(name_lower, pattern.lower()):
                return rule
    return None


def plan_moves(
    source_dir: str | Path,
    rules: list[OrgRule],
    date_mode: bool = False,
) -> list[PlannedMove]:
    """
    Plan file moves from source_dir according to organization rules.

    Scans the top level of source_dir (non-recursive) and matches each
    file against the rules. Directories are skipped.

    Args:
        source_dir: Directory containing files to organize.
        rules: List of OrgRule to match against.
        date_mode: If True, destination becomes 'Category/YYYY-MM/filename'
                   based on the file's modification time.

    Returns:
        List of PlannedMove objects describing intended moves.
    """
    source = Path(source_dir).resolve()
    moves: list[PlannedMove] = []

    if not source.is_dir():
        return moves

    try:
        entries = list(os.scandir(str(source)))
    except PermissionError:
        return moves

    for entry in entries:
        try:
            # Skip directories, symlinks, hidden files
            if entry.is_dir(follow_symlinks=False):
                continue
            if entry.is_symlink():
                continue

            if not is_safe_path(entry.path):
                continue

            matched_rule = _match_file(entry.name, rules)
            if matched_rule is None:
                continue

            # Build destination path
            dest_folder = matched_rule.dest.rstrip("/")

            if date_mode:
                try:
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                    date_subfolder = mtime.strftime("%Y-%m")
                    dst = source / dest_folder / date_subfolder / entry.name
                except OSError:
                    dst = source / dest_folder / entry.name
            else:
                dst = source / dest_folder / entry.name

            moves.append(PlannedMove(
                src=Path(entry.path),
                dst=dst,
                rule_name=matched_rule.name,
            ))

        except (PermissionError, OSError):
            continue

    return moves


def execute_moves(
    moves: list[PlannedMove],
    history_manager: HistoryManager,
    dry_run: bool = False,
) -> list[str]:
    """
    Execute planned file moves, logging each to history.

    Args:
        moves: List of PlannedMove objects to execute.
        history_manager: HistoryManager instance for logging operations.
        dry_run: If True, only report what would happen without moving files.

    Returns:
        List of result strings summarizing what was (or would be) done.
    """
    if not moves:
        return ["No files to organize."]

    results: list[str] = []
    batch_id = str(uuid.uuid4())[:8]
    moved_count = 0
    error_count = 0

    for move in moves:
        if dry_run:
            results.append(
                f"[DRY RUN] {move.src.name} → {move.dst.parent.name}/ "
                f"({move.rule_name})"
            )
            continue

        try:
            # Get file size before moving
            try:
                size = move.src.stat().st_size
            except OSError:
                size = 0

            actual_dst = safe_move(move.src, move.dst)

            history_manager.log_move(
                source=str(move.src),
                destination=str(actual_dst),
                size_bytes=size,
                description=f"Organized {move.src.name} → {move.rule_name}",
                batch_id=batch_id,
            )

            results.append(
                f"✓ {move.src.name} → {actual_dst.parent.name}/ "
                f"({move.rule_name})"
            )
            moved_count += 1

        except Exception as exc:
            results.append(f"✗ {move.src.name}: {exc}")
            error_count += 1

    # Summary line
    if not dry_run:
        results.append(
            f"\n{'─' * 40}\n"
            f"Organized {moved_count} file(s) "
            f"({error_count} error(s)), batch: {batch_id}"
        )
    else:
        results.append(
            f"\n{'─' * 40}\n"
            f"[DRY RUN] Would organize {len(moves)} file(s)"
        )

    return results

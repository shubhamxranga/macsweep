"""
MacSweep Test Suite
Validates the core engine modules including scanner, duplicate finder, organizer, and cleaner.
"""

import os
import shutil
import pytest
from pathlib import Path

from app.core.utils import is_safe_path, format_size, hash_file
from app.core.scanner import scan_directory, get_top_files, get_type_breakdown
from app.core.duplicates import find_duplicates, resolve_group
from app.core.organizer import load_rules, plan_moves, OrgRule
from app.core.cleaner import scan_junk

@pytest.fixture
def temp_workspace(tmp_path):
    """Creates a temporary workspace with some test files."""
    # Create files of varying sizes and content
    file_a = tmp_path / "file_a.txt"
    file_a.write_text("Hello World! " * 10) # ~130 bytes
    
    file_b = tmp_path / "file_b.txt"
    file_b.write_text("Hello World! " * 10) # Duplicate of a
    
    file_c = tmp_path / "img_c.png"
    file_c.write_bytes(b"\x89PNG\r\n\x1a\n" + b"some random image data" * 10)
    
    # script_d directly in root for non-recursive organizer check
    file_d = tmp_path / "script_d.py"
    file_d.write_text("print('hello')\n")
    
    # Nested directory (still exists for recursive scanner check)
    nested = tmp_path / "subfolder"
    nested.mkdir()
    file_e = nested / "nested_file.txt"
    file_e.write_text("nested contents\n")
    
    yield tmp_path

def test_utils():
    # 1. Size formatter
    assert format_size(0) == "0 B"
    assert format_size(1023) == "1023 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024 * 1024 * 1024 * 5.5) == "5.5 GB"

    # 2. Path safety guards
    assert is_safe_path("/System") is False
    assert is_safe_path("/System/Library") is False
    assert is_safe_path("/Library") is False
    assert is_safe_path("/usr/bin/local") is False
    
    # Safe paths
    assert is_safe_path(Path.home() / "Downloads") is True
    assert is_safe_path(str(Path.home() / "Downloads")) is True

def test_scanner(temp_workspace):
    files = list(scan_directory(temp_workspace))
    non_dirs = [f for f in files if not f.is_dir]
    assert len(non_dirs) == 5
    
    # Top files
    top_files = get_top_files(temp_workspace, n=2)
    assert len(top_files) == 2
    assert top_files[0].size >= top_files[1].size

    # Type breakdown
    breakdown = get_type_breakdown(temp_workspace)
    assert ".txt" in breakdown
    assert ".png" in breakdown
    assert ".py" in breakdown
    assert breakdown[".txt"][0] == 3 # 2 in root, 1 nested

def test_duplicates(temp_workspace):
    groups = find_duplicates(temp_workspace, min_size=10)
    assert len(groups) == 1
    group = groups[0]
    
    # Resolve strategy
    to_delete = resolve_group(group, strategy="keep_first")
    assert len(to_delete) == 1
    assert "file_b.txt" in to_delete[0] or "file_a.txt" in to_delete[0]

def test_organizer(temp_workspace):
    rules = [
        OrgRule(name="Images", patterns=["*.png"], dest="Images/"),
        OrgRule(name="Code", patterns=["*.py"], dest="Code/"),
    ]
    
    moves = plan_moves(temp_workspace, rules, date_mode=False)
    assert len(moves) == 2
    
    move_names = [m.src.name for m in moves]
    assert "img_c.png" in move_names
    assert "script_d.py" in move_names

"""
MacSweep — End-to-End Programmatic Demo
Showcases all 4 core features of the MacSweep engine in action using a mock workspace.
"""

import os
import shutil
import tempfile
from pathlib import Path
from rich.console import Console
from rich.table import Table

from app.core.utils import format_size
from app.core.scanner import scan_directory, get_top_files, get_disk_usage
from app.core.duplicates import find_duplicates, resolve_group
from app.core.organizer import load_rules, plan_moves, OrgRule
from app.core.cleaner import scan_junk

console = Console()

def setup_demo_workspace() -> Path:
    """Create a temporary sandbox directory with mock files for scanning and sorting."""
    temp_dir = Path(tempfile.mkdtemp(prefix="macsweep_demo_")).resolve()
    
    # 1. Duplicate text files
    (temp_dir / "duplicate_1.txt").write_text("Unique text signature for hashing test.")
    (temp_dir / "duplicate_2.txt").write_text("Unique text signature for hashing test.")
    
    # 2. Large image
    large_img = temp_dir / "large_photo.png"
    large_img.write_bytes(b"\x00" * (1024 * 1024 * 5)) # 5 MB
    
    # 3. Code files
    (temp_dir / "script.py").write_text("print('Hello from MacSweep!')\n")
    (temp_dir / "server.js").write_text("console.log('App running');\n")
    
    # 4. Nested subdirectory
    sub = temp_dir / "archive_sub"
    sub.mkdir()
    (sub / "backup.zip").write_bytes(b"PK\x03\x04" + b"\x00" * 1000)

    return temp_dir

def run_demo():
    console.print("[bold cyan]====================================================[/bold cyan]")
    console.print("[bold white]          🧹 MACSWEEP DEMO RUNNING 🧹               [/bold white]")
    console.print("[bold cyan]====================================================[/bold cyan]\n")

    # Setup demo workspace
    workspace = setup_demo_workspace()
    console.print(f"Created sandbox workspace at: [yellow]{workspace}[/yellow]\n")

    try:
        # --- FEATURE 1: Storage Scanner ---
        console.print("[bold green]1. Storage Scanner Demo[/bold green]")
        total, used, free = get_disk_usage()
        console.print(f"Disk Info -> Total: [bold]{format_size(total)}[/bold], Used: [bold]{format_size(used)}[/bold], Free: [bold]{format_size(free)}[/bold]")
        
        files = list(scan_directory(workspace))
        console.print(f"Scanned [bold]{len(files)}[/bold] paths in workspace.")
        
        top_files = get_top_files(workspace, n=3)
        table = Table(title="Top 3 Files by Size")
        table.add_column("File Name", style="bold")
        table.add_column("Size", style="green")
        table.add_column("Path", style="dim")
        for f in top_files:
            table.add_row(f.name, format_size(f.size), str(f.path))
        console.print(table)
        console.print("")

        # --- FEATURE 2: Duplicate Finder ---
        console.print("[bold green]2. Duplicate Finder Demo[/bold green]")
        duplicates = find_duplicates(workspace, min_size=5)
        console.print(f"Found [bold]{len(duplicates)}[/bold] duplicate groups.")
        for g in duplicates:
            console.print(f"  • Hash: [cyan]{g.hash[:8]}[/cyan] ({format_size(g.size)} per file) - [red]Wasted: {format_size(g.wasted_bytes)}[/red]")
            for p in g.paths:
                console.print(f"    - {Path(p).name}")
            
            # Resolve group demo
            to_delete = resolve_group(g, strategy="keep_newest")
            console.print(f"    [dim]Recommended for deletion: {[Path(p).name for p in to_delete]}[/dim]")
        console.print("")

        # --- FEATURE 3: Smart File Organizer ---
        console.print("[bold green]3. Smart File Organizer Demo[/bold green]")
        rules = [
            OrgRule(name="Images", patterns=["*.png"], dest="Images/"),
            OrgRule(name="Code", patterns=["*.py", "*.js"], dest="Code/"),
            OrgRule(name="Documents", patterns=["*.txt"], dest="Docs/")
        ]
        planned_moves = plan_moves(workspace, rules, date_mode=False)
        org_table = Table(title="Planned Organization Moves")
        org_table.add_column("Source File", style="yellow")
        org_table.add_column("Target Destination", style="green")
        org_table.add_column("Matching Rule", style="cyan")
        for m in planned_moves:
            org_table.add_row(m.src.name, str(m.dst.relative_to(workspace)), m.rule_name)
        console.print(org_table)
        console.print("")

        # --- FEATURE 4: Cache & Junk Cleaner ---
        console.print("[bold green]4. Cache & Junk Cleaner Demo[/bold green]")
        junk_targets = scan_junk()
        # Find which targets exist on user machine
        existing_targets = [t for t in junk_targets if t.size_bytes > 0]
        console.print(f"Scanned user system. Found [bold]{len(existing_targets)}[/bold] active caches/junk folders.")
        for t in existing_targets[:5]:
            console.print(f"  • [yellow]{t.name}[/yellow]: {format_size(t.size_bytes)} ({t.safe_level.upper()}) at {t.path}")
        console.print("")

        console.print("[bold green]✓ Demo execution finished successfully![/bold green]")
    
    finally:
        # Cleanup workspace
        shutil.rmtree(workspace)
        console.print(f"\n[dim]Cleaned up sandbox workspace: {workspace}[/dim]")

if __name__ == "__main__":
    run_demo()

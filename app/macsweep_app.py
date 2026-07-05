"""
MacSweep — Textual Application Shell
Handles application initialization, global settings/history lifecycle, global routing, and design themes.
"""

from textual.app import App
from .screens import (
    Dashboard,
    ScannerScreen,
    DuplicatesScreen,
    OrganizerScreen,
    CleanerScreen,
)
from .core.history import HistoryManager
from .config.settings import Settings
from .core.organizer import load_rules

class MacSweepApp(App):
    """MacSweep local terminal utility app."""

    TITLE = "MacSweep 🧹"
    SUB_TITLE = "100% Local macOS File Organizer & Storage Manager"

    SCREENS = {
        "dashboard": Dashboard,
        "scanner": ScannerScreen,
        "duplicates": DuplicatesScreen,
        "organizer": OrganizerScreen,
        "cleaner": CleanerScreen,
    }

    # Beautiful premium terminal design system
    CSS = """
    /* Color Palette */
    Screen {
        background: #0d1117;
        color: #c9d1d9;
    }
    
    Header {
        background: #161b22;
        color: #58a6ff;
        text-style: bold;
    }
    
    Footer {
        background: #161b22;
        color: #8b949e;
    }
    
    /* Layout Container spacing */
    #dashboard-container, #scanner-container, #duplicates-container, #organizer-container, #cleaner-container {
        padding: 1 2;
        height: 1fr;
    }
    
    /* Title Styles */
    .screen-title {
        color: #58a6ff;
        text-style: bold;
        margin-bottom: 1;
    }
    
    .section-title {
        color: #c9d1d9;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }
    
    .warning {
        color: #d29922;
        text-style: bold;
    }
    
    /* Stat grid boxes */
    #stats-grid {
        grid-size: 2;
        grid-gutter: 2;
        height: 5;
        margin: 1 0;
    }
    
    .stat-box {
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
        align: center middle;
        text-align: center;
        color: #8b949e;
    }
    
    /* Input & Control structures */
    #path-selector-row, #dup-controls-row, #org-controls-row, #cleaner-controls-row {
        height: 3;
        margin-bottom: 1;
    }
    
    #path-selector-row Input, #dup-controls-row Input, #org-controls-row Input {
        width: 1fr;
        border: tall #30363d;
        background: #0d1117;
    }
    
    #path-selector-row Button, #dup-controls-row Button, #org-controls-row Button, #cleaner-controls-row Button {
        width: 20;
        margin-left: 2;
    }
    
    /* Switch elements styling */
    #dup-options-row, #org-options-row {
        height: 3;
        align: left middle;
        margin-bottom: 1;
    }
    
    .switch-lbl {
        margin: 0 1;
        text-align: center;
    }
    
    #dup-wasted-lbl {
        margin-left: 5;
        color: #f85149;
        text-style: bold;
    }
    
    /* Progress overlays */
    #scan-progress-box, #dup-progress-box {
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
        margin: 1 0;
        height: 5;
        align: center middle;
    }
    
    #scan-status-lbl, #dup-status-lbl {
        margin-bottom: 1;
        text-align: center;
        color: #58a6ff;
    }
    
    /* Tables design */
    DataTable {
        background: #161b22;
        border: solid #30363d;
        height: 1fr;
        margin-top: 1;
    }
    

    
    /* Help box on Dashboard */
    .help-box {
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
        margin-top: 1;
        text-align: center;
        color: #8b949e;
    }
    """

    def on_mount(self) -> None:
        # Load core configuration & history database
        self.settings = Settings()
        self.history_manager = HistoryManager()
        self.rules = load_rules()
        
        # Start at Home screen
        self.push_screen("dashboard")

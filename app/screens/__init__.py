"""
MacSweep TUI Screen Registration
"""

from .dashboard import Dashboard
from .scanner import ScannerScreen
from .duplicates import DuplicatesScreen
from .organizer import OrganizerScreen
from .cleaner import CleanerScreen

__all__ = [
    "Dashboard",
    "ScannerScreen",
    "DuplicatesScreen",
    "OrganizerScreen",
    "CleanerScreen",
]

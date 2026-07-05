"""
MacSweep — Settings Manager
Loads/saves user preferences to ~/.macsweep/config.json.
"""

import json
from pathlib import Path
from typing import Any

from ..core.utils import CONFIG_FILE, ensure_dirs


DEFAULT_SETTINGS = {
    "default_scan_path": str(Path.home()),
    "organizer_dry_run_default": True,
    "cleaner_auto_confirm": False,
    "max_history_entries": 5000,
    "theme": "dark",
}


class Settings:
    """Manages user settings with defaults and persistence."""

    def __init__(self):
        ensure_dirs()
        self._data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self):
        """Load settings from disk, merging with defaults."""
        if CONFIG_FILE.exists():
            try:
                saved = json.loads(CONFIG_FILE.read_text())
                self._data.update(saved)
            except (json.JSONDecodeError, TypeError):
                pass

    def save(self):
        """Persist current settings to disk."""
        ensure_dirs()
        CONFIG_FILE.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value and persist."""
        self._data[key] = value
        self.save()

    def reset(self):
        """Reset all settings to defaults."""
        self._data = dict(DEFAULT_SETTINGS)
        self.save()

    @property
    def scan_path(self) -> str:
        return self._data["default_scan_path"]



    @property
    def theme(self) -> str:
        return self._data["theme"]


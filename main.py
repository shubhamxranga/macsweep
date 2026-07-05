"""
MacSweep — 100% Local macOS Storage Manager
Application entry point.
"""

from app.macsweep_app import MacSweepApp

if __name__ == "__main__":
    app = MacSweepApp()
    app.run()

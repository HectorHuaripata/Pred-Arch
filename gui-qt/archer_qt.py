#!/usr/bin/env python3
"""Archer control panel (Qt 6 / QML). Talks to the daemon over
io.github.archer.Control1. `--hidden` starts in the tray."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from archerqt.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

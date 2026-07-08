"""Launcher for the full provider x mediator experimental comparison."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiments.full_comparison import main

if __name__ == "__main__":
    main()

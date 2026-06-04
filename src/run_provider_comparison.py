"""Run the reproducible mock-versus-Ollama provider comparison."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiments.compare_providers import main


if __name__ == "__main__":
    main()

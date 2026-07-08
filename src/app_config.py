"""Lightweight configuration helpers shared by demos, experiments and the UI.

Loads a project-level ``.env`` file (if present) into ``os.environ`` so that
secrets such as the OpenRouter API key never need to be hard-coded or passed on
the command line. The format is intentionally minimal: ``KEY=value`` lines,
``#`` comments and blank lines.
"""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Return the repository root (parent of the ``src`` directory)."""

    return Path(__file__).resolve().parent.parent


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """Load KEY=value pairs from a .env file into os.environ.

    Existing environment variables are not overwritten. Returns the values that
    were loaded for traceability.
    """

    env_path = path or (project_root() / ".env")
    loaded: dict[str, str] = {}
    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)

    return loaded

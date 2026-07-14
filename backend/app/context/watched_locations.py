"""User-managed watched locations for system-wide activity capture.

Persisted in backend/.contextos/watched.json. Defaults to Desktop / Documents / Downloads /
the active project. Users can add/remove folders, exclude patterns, and pause monitoring.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.context.sources.git_source import watch_dir
from app.core.config import STATE_DIR

_FILE = STATE_DIR / "watched.json"

# always-excluded dir names (noisy / sensitive / dependency dirs)
DEFAULT_EXCLUDES = [
    "node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv",
    ".contextos", ".idea", ".vscode", "dist-ssr", "AppData", ".cache",
    "$Recycle.Bin", "site-packages", ".next", "target", ".gradle", "Temp", "tmp",
]


def _defaults() -> dict[str, Any]:
    home = Path.home()
    env = os.environ.get("CONTEXTOS_ACTIVITY_ROOTS")
    if env:
        roots = [p.strip() for p in env.split(os.pathsep) if p.strip()]
    else:
        # include OneDrive-redirected known folders (common on Windows) — existing_roots()
        # keeps only the ones that actually exist.
        candidates = [watch_dir()]
        for base in (home, home / "OneDrive"):
            for folder in ("Desktop", "Documents", "Downloads"):
                candidates.append(base / folder)
        roots = [str(p) for p in candidates]
    return {"roots": roots, "excludes": [], "paused": False}


def load() -> dict[str, Any]:
    if _FILE.exists():
        try:
            data = json.loads(_FILE.read_text(encoding="utf-8"))
            data.setdefault("roots", _defaults()["roots"])
            data.setdefault("excludes", [])
            data.setdefault("paused", False)
            return data
        except Exception:  # noqa: BLE001
            pass
    d = _defaults()
    save(d)
    return d


def save(data: dict[str, Any]) -> None:
    _FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def existing_roots() -> list[Path]:
    """Resolved, existing, de-duplicated watched roots (empty if paused)."""
    data = load()
    if data.get("paused"):
        return []
    out: list[Path] = []
    for r in data.get("roots", []):
        try:
            p = Path(r).expanduser().resolve()
        except Exception:  # noqa: BLE001
            continue
        if p.exists() and p not in out:
            out.append(p)
    return out


def all_excludes() -> list[str]:
    return DEFAULT_EXCLUDES + load().get("excludes", [])


def add_root(path: str) -> dict[str, Any]:
    data = load()
    p = str(Path(path).expanduser())
    if p not in data["roots"]:
        data["roots"].append(p)
    save(data)
    return data


def remove_root(path: str) -> dict[str, Any]:
    data = load()
    data["roots"] = [r for r in data["roots"] if r != path]
    save(data)
    return data


def add_exclude(pattern: str) -> dict[str, Any]:
    data = load()
    if pattern not in data["excludes"]:
        data["excludes"].append(pattern)
    save(data)
    return data


def set_paused(paused: bool) -> dict[str, Any]:
    data = load()
    data["paused"] = paused
    save(data)
    return data


def status() -> dict[str, Any]:
    data = load()
    return {
        "roots": data["roots"],
        "existing_roots": [str(p) for p in existing_roots()],
        "excludes": data.get("excludes", []),
        "default_excludes": DEFAULT_EXCLUDES,
        "paused": data.get("paused", False),
    }

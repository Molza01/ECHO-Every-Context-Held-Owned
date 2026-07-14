"""Most-recently-touched source file in the watched project (a real activity signal)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from app.context.sources.git_source import watch_dir

_IGNORE_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv",
                "venv", ".contextos", ".idea", ".vscode", "dist-ssr"}
_CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
             ".c", ".cpp", ".cs", ".md", ".json", ".yaml", ".yml", ".sql", ".sh"}


class FileContextSource:
    name = "file"

    def __init__(self, root: Optional[Path] = None, window_seconds: int = 120) -> None:
        self.root = root or watch_dir()
        self.window_seconds = window_seconds

    def available(self) -> bool:
        return self.root.exists()

    def recent_file(self) -> Optional[str]:
        """Return the path of the most recently modified code file, if edited recently."""
        newest: tuple[float, Optional[str]] = (0.0, None)
        cutoff = time.time() - self.window_seconds
        try:
            for path in self.root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in _CODE_EXT:
                    continue
                if any(part in _IGNORE_DIRS for part in path.parts):
                    continue
                mtime = path.stat().st_mtime
                if mtime >= cutoff and mtime > newest[0]:
                    newest = (mtime, str(path.relative_to(self.root)))
        except Exception:  # noqa: BLE001
            return None
        return newest[1]

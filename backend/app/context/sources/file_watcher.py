"""Real filesystem watcher (watchdog) for the monitored project root.

On an actual save of a meaningful source file it emits a precise ContextEvent such as
"Modified backend/app/memory/ranking.py in the ContextOS repository on master" — which both
stores a memory and drives contextual retrieval. Ignores noise dirs and non-code files.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from app.context.sources.file_source import _CODE_EXT, _IGNORE_DIRS
from app.context.sources.git_source import GitContextSource, watch_dir
from app.models.context_event import ContextEvent

log = logging.getLogger("contextos.source.filewatcher")

EventCb = Callable[[ContextEvent], Awaitable[None]]


class FileWatcher:
    def __init__(self, root: Optional[Path] = None, debounce_s: float = 1.5) -> None:
        self.root = root or watch_dir()
        self.debounce_s = debounce_s
        self._observer = None
        self._git = GitContextSource(self.root)
        self._last_emit: dict[str, float] = {}

    def available(self) -> bool:
        try:
            import watchdog  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return self.root.exists()

    def start(self, callback: EventCb, loop: asyncio.AbstractEventLoop) -> bool:
        if not self.available():
            return False
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:  # noqa: BLE001
            return False

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_modified(self, event):  # noqa: ANN001
                if event.is_directory:
                    return
                watcher._handle(Path(event.src_path), callback, loop)

            on_created = on_modified

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(self.root), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        log.info("file watcher started on %s", self.root)
        return True

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            try:
                self._observer.join(timeout=2)
            except Exception:  # noqa: BLE001
                pass

    def _handle(self, path: Path, callback: EventCb, loop: asyncio.AbstractEventLoop) -> None:
        try:
            if path.suffix.lower() not in _CODE_EXT:
                return
            parts = path.parts
            if any(p in _IGNORE_DIRS for p in parts):
                return
            rel = str(path.relative_to(self.root))
        except Exception:  # noqa: BLE001
            return

        now = time.time()
        if now - self._last_emit.get(rel, 0) < self.debounce_s:
            return
        self._last_emit[rel] = now

        snap = self._git.snapshot() if self._git.available() else {}
        ev = ContextEvent(
            source_type="file",
            application="File watcher",
            file_path=rel,
            project_name=snap.get("project_name") or self.root.name,
            repository=snap.get("repository"),
            branch=snap.get("branch"),
            folder=snap.get("folder") or str(self.root),
            title=f"Modified {rel}",
        )
        # hop back onto the event loop from watchdog's thread
        asyncio.run_coroutine_threadsafe(callback(ev), loop)

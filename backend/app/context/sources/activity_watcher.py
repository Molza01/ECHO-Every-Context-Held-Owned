"""Universal, privacy-first OS activity watcher.

Watches user-managed roots (Desktop / Documents / Downloads / active project by default) and
turns real filesystem events — for BOTH files and folders — into semantic ContextEvents:

    created | modified | renamed | moved | deleted

Records ONLY path, action, and file type — never file contents, never hidden/temp files,
never excluded/dependency/system dirs. Locations and excludes are user-managed.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from app.context import watched_locations as WL
from app.context.sources.git_source import GitContextSource, watch_dir
from app.models.context_event import ContextEvent

log = logging.getLogger("contextos.source.activity")

EventCb = Callable[[ContextEvent], Awaitable[None]]

_KINDS: dict[str, tuple[str, ...]] = {
    "code": (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
             ".c", ".cpp", ".cs", ".sql", ".sh", ".html", ".css", ".vue"),
    "config": (".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".xml"),
    "document": (".md", ".txt", ".rtf", ".doc", ".docx", ".odt"),
    "pdf": (".pdf",),
    "presentation": (".ppt", ".pptx", ".key", ".odp"),
    "spreadsheet": (".xls", ".xlsx", ".csv", ".ods"),
    "image": (".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".bmp", ".heic"),
    "archive": (".zip", ".tar", ".gz", ".rar", ".7z"),
}
_EXT_KIND = {ext: kind for kind, exts in _KINDS.items() for ext in exts}

_IGNORE_PREFIX = ("~$", ".~", "tmp")
_IGNORE_SUFFIX = (".tmp", ".crdownload", ".part", ".swp", ".lock", ".log")


def _kind_for(path: Path, is_dir: bool) -> Optional[str]:
    """Return the classification if worth an event, else None."""
    name = path.name
    if name.startswith(".") or name.lower().startswith(_IGNORE_PREFIX):
        return None
    excludes = set(WL.all_excludes())
    if any(part in excludes for part in path.parts):
        return None
    if is_dir:
        return "folder"
    if name.lower().endswith(_IGNORE_SUFFIX):
        return None
    return _EXT_KIND.get(path.suffix.lower())  # None => uninteresting file type


class ActivityWatcher:
    def __init__(self, debounce_s: float = 1.5) -> None:
        self.debounce_s = debounce_s
        self._observer = None
        self._git = GitContextSource(watch_dir())
        self._last: dict[str, float] = {}
        self.roots: list[Path] = []

    def available(self) -> bool:
        try:
            import watchdog  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return bool(WL.existing_roots())

    # --- lifecycle (restartable so watched-location changes take effect) --------------
    def start(self, callback: EventCb, loop: asyncio.AbstractEventLoop) -> bool:
        self._callback = callback
        self._loop = loop
        return self._spawn()

    def restart(self) -> bool:
        self.stop()
        return self._spawn() if getattr(self, "_callback", None) else False

    def _spawn(self) -> bool:
        self.roots = WL.existing_roots()
        if not self.roots:
            log.info("activity watcher paused / no existing roots")
            return False
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception:  # noqa: BLE001
            return False

        w = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, e):  # noqa: ANN001
                w._emit(Path(e.src_path), "created", None, e.is_directory)

            def on_modified(self, e):  # noqa: ANN001
                if not e.is_directory:  # folder "modified" is noise
                    w._emit(Path(e.src_path), "modified", None, False)

            def on_deleted(self, e):  # noqa: ANN001
                w._emit(Path(e.src_path), "deleted", None, e.is_directory)

            def on_moved(self, e):  # noqa: ANN001
                src, dst = Path(e.src_path), Path(e.dest_path)
                action = "renamed" if src.parent == dst.parent else "moved"
                w._emit(dst, action, src, e.is_directory)

        self._observer = Observer()
        for root in self.roots:
            try:
                self._observer.schedule(_Handler(), str(root), recursive=True)
            except Exception as exc:  # noqa: BLE001
                log.debug("cannot watch %s: %s", root, exc)
        self._observer.daemon = True
        self._observer.start()
        log.info("activity watcher started on %d roots: %s",
                 len(self.roots), ", ".join(p.name or str(p) for p in self.roots))
        return True

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            try:
                self._observer.join(timeout=2)
            except Exception:  # noqa: BLE001
                pass
            self._observer = None

    # --- event construction -----------------------------------------------------------
    def _root_for(self, path: Path) -> Optional[Path]:
        for r in self.roots:
            try:
                path.relative_to(r)
                return r
            except ValueError:
                continue
        return None

    def _emit(self, path: Path, action: str, old: Optional[Path], is_dir: bool) -> None:
        kind = _kind_for(path, is_dir)
        if kind is None:
            return
        key = f"{path}|{action}"
        now = time.time()
        if now - self._last.get(key, 0) < self.debounce_s:
            return
        self._last[key] = now

        root = self._root_for(path)
        in_project = root is not None and root == watch_dir()
        snap = self._git.snapshot() if in_project and self._git.available() else {}

        folder = path.parent.name
        try:
            display = str(path.relative_to(root)) if in_project and root else path.name
        except Exception:  # noqa: BLE001
            display = path.name

        meta: dict = {"file_kind": kind, "to_folder": folder,
                      "root": (root.name if root else None), "is_dir": is_dir,
                      "full_path": str(path)}
        if old is not None:
            meta["from_folder"] = old.parent.name
            meta["old_name"] = old.name
            meta["new_name"] = path.name

        ev = ContextEvent(
            source_type="file",
            application="File Explorer",
            action=action,
            file_path=display,
            old_path=(old.name if old else None),
            folder=folder,
            project_name=snap.get("project_name") or (root.name if root else None),
            repository=snap.get("repository"),
            branch=snap.get("branch"),
            title=f"{action.title()} {path.name}",
            metadata=meta,
        )
        asyncio.run_coroutine_threadsafe(self._callback(ev), self._loop)

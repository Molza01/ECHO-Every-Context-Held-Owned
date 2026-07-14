"""Active-window context source (Windows-first, degrades gracefully elsewhere).

Reads only the foreground window's *title* and owning process name — never keystrokes,
never window contents. Titles are parsed for well-known apps to extract file/project.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from app.models.context_event import ContextEvent

log = logging.getLogger("contextos.source.window")

# app-detection by executable name
_EDITORS = {"code.exe": "VS Code", "cursor.exe": "Cursor", "code - insiders.exe": "VS Code"}
_BROWSERS = {"chrome.exe": "Chrome", "msedge.exe": "Edge", "brave.exe": "Brave", "firefox.exe": "Firefox"}
_TERMINALS = {"windowsterminal.exe": "Terminal", "powershell.exe": "PowerShell",
              "cmd.exe": "Command Prompt", "wt.exe": "Terminal", "pwsh.exe": "PowerShell"}


def _foreground() -> Optional[tuple[str, str]]:
    """Return (window_title, exe_name_lower) for the foreground window, or None."""
    try:
        import win32gui  # type: ignore
        import win32process  # type: ignore
        import psutil
    except Exception:  # noqa: BLE001
        return None
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        exe = ""
        try:
            exe = os.path.basename(psutil.Process(pid).name()).lower()
        except Exception:  # noqa: BLE001
            pass
        return title, exe
    except Exception as exc:  # noqa: BLE001
        log.debug("foreground read failed: %s", exc)
        return None


def _parse_editor_title(title: str) -> tuple[Optional[str], Optional[str]]:
    """VS Code / Cursor titles look like 'auth.ts - ContextOS - Visual Studio Code'.

    Returns (file_path, project_name).
    """
    # strip trailing app name
    cleaned = re.sub(r"\s*[-—]\s*(Visual Studio Code|Cursor)(\s*-\s*Insiders)?\s*$", "", title).strip()
    parts = [p.strip() for p in re.split(r"\s+[-—]\s+", cleaned) if p.strip()]
    if not parts:
        return None, None
    file_part = parts[0].lstrip("●•*").strip()  # leading dot = unsaved indicator
    project = parts[1] if len(parts) > 1 else None
    file_path = file_part if ("." in file_part or "/" in file_part or "\\" in file_part) else None
    return file_path, project


class ActiveWindowSource:
    name = "active_window"

    def available(self) -> bool:
        return _foreground() is not None

    def sample(self) -> Optional[ContextEvent]:
        fg = _foreground()
        if not fg:
            return None
        title, exe = fg
        if not title:
            return None

        if exe in _EDITORS:
            app = _EDITORS[exe]
            file_path, project = _parse_editor_title(title)
            return ContextEvent(
                source_type="active_window",
                application=app,
                title=title,
                file_path=file_path,
                project_name=project,
                metadata={"exe": exe},
            )

        if exe in _BROWSERS:
            # Browser detail (url/domain) comes from the extension; here we only note focus.
            return ContextEvent(
                source_type="active_window",
                application=_BROWSERS[exe],
                title=title,
                metadata={"exe": exe, "is_browser": True},
            )

        if exe in _TERMINALS:
            return ContextEvent(
                source_type="active_window",
                application=_TERMINALS[exe],
                title=title,
                metadata={"exe": exe, "is_terminal": True},
            )

        if exe == "explorer.exe":
            return ContextEvent(source_type="active_window", application="File Explorer",
                                title=title, metadata={"exe": exe})

        # generic app — still useful for "what am I doing" but low value
        app = exe.replace(".exe", "").title() if exe else "Application"
        return ContextEvent(
            source_type="active_window", application=app, title=title, metadata={"exe": exe}
        )

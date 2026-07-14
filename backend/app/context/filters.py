"""Meaningful-activity filter — the gate that keeps ContextOS from surveillance logging."""
from __future__ import annotations

from app.models.context_event import ContextEvent

# Generic window titles / apps that carry no useful project context on their own.
_NOISE_APPS = {"searchhost", "shellexperiencehost", "textinputhost",
               "applicationframehost", "startmenuexperiencehost", "lockapp", "dwm"}
_NOISE_TITLES = {"", "program manager", "task switching", "new tab", "settings"}


def is_meaningful(ev: ContextEvent) -> bool:
    """Return True if this context is worth remembering / acting on."""
    if ev.source_type in ("browser", "terminal", "manual", "git", "file"):
        # these sources are already curated upstream
        if ev.source_type == "browser" and not (ev.url or ev.title):
            return False
        return True

    # active_window: require some substance
    app = (ev.application or "").lower()
    title = (ev.title or "").strip().lower()
    if app in _NOISE_APPS or title in _NOISE_TITLES:
        return False
    # a bare app with a trivially short title isn't meaningful
    if not ev.file_path and not ev.project_name and len(title) < 4:
        return False
    return True


def is_worth_storing(ev: ContextEvent) -> tuple[bool, str]:
    """Decide whether a context event should become a *stored* memory.

    Every event still drives ambient retrieval; only genuinely meaningful ones are
    persisted, so we never clutter memory with bare "focused a window" events.
    Returns (store?, reason).
    """
    st = ev.source_type
    if st == "browser":
        return (bool(ev.url or ev.title), "browser page")
    if st == "terminal":
        return (bool(ev.content), "terminal command")
    if st == "manual":
        return (bool(ev.content or ev.title), "explicitly remembered")
    if st == "file":
        return (bool(ev.file_path), "file modified")
    if st == "git":
        return (bool(ev.repository), "git context")
    if st == "active_window":
        # store editor focus that resolves to a real file, or a cooldown-gated app-usage
        # marker so application history ("spent time in Chrome") is remembered
        if ev.file_path:
            return (True, "editing a file")
        if ev.metadata.get("app_usage"):
            return (True, "application usage")
        return (False, "bare window focus (not stored, drives retrieval only)")
    return (False, "unknown source")

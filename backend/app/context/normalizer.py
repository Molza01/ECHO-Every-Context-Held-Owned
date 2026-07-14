"""Merge raw source signals into one enriched 'current context' ContextEvent."""
from __future__ import annotations

from app.context.sources.file_source import FileContextSource
from app.context.sources.git_source import GitContextSource
from app.models.context_event import ContextEvent


def enrich_with_project(
    ev: ContextEvent,
    git_source: GitContextSource,
    file_source: FileContextSource,
) -> ContextEvent:
    """Attach live git repo/branch/project + recent file to an active-window event.

    This is what makes an editor focus event become 'working in the ContextOS repo on
    feature/auth, editing auth.ts' — the rich context proactive retrieval needs.
    """
    meta = ev.metadata or {}
    is_dev_app = bool(meta.get("is_terminal")) or ev.file_path is not None or (
        ev.application in ("VS Code", "Cursor", "Terminal", "PowerShell", "Command Prompt")
    )
    if not is_dev_app:
        return ev

    snap = git_source.snapshot() if git_source.available() else {}
    if snap:
        ev.repository = ev.repository or snap.get("repository")
        ev.branch = ev.branch or snap.get("branch")
        ev.folder = ev.folder or snap.get("folder")
        # only trust the git project name if the window didn't already give one
        ev.project_name = ev.project_name or snap.get("project_name")

    if not ev.file_path and file_source.available():
        recent = file_source.recent_file()
        if recent:
            ev.file_path = recent
            ev.metadata["file_from_scan"] = True  # inferred, not detected from the editor

    return ev

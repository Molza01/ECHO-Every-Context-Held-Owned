"""Turn a normalized ContextEvent into a meaningful semantic memory in Supermemory.

Deterministic formatting only — no per-event LLM call (fast, private, reproducible).
The goal is memories that read like a sentence a human would write, so semantic search
can relate them later even when the words differ.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.privacy import redact, redact_dict
from app.models.context_event import ContextEvent
from app.services.supermemory_service import get_supermemory

log = logging.getLogger("contextos.ingestion")


_KIND_VERB = {
    "pdf": "Worked with",
    "presentation": "Worked on the presentation",
    "spreadsheet": "Edited the spreadsheet",
    "document": "Worked on",
    "image": "Worked with",
    "code": "Worked on",
}


def _file_activity_sentence(ev: ContextEvent) -> Optional[str]:
    """Human, action-aware, type-aware phrasing for universal file/folder activity."""
    name = ev.file_path or ev.title or "a file"
    base = name.split("\\")[-1].split("/")[-1]
    where = ev.folder or ev.project_name or "a folder"
    kind = str(ev.metadata.get("file_kind") or "code")
    action = ev.action or "modified"
    m = ev.metadata
    is_dir = bool(m.get("is_dir")) or kind == "folder"

    # ---- folders ----
    if is_dir:
        if action == "created":
            return f"Created folder {base} in {where}."
        if action == "deleted":
            return f"Deleted folder {base} from {where}."
        if action == "renamed":
            return f"Renamed folder {m.get('old_name') or ev.old_path} to {base} in {where}."
        if action == "moved":
            return f"Moved folder {base} from {m.get('from_folder')} to {m.get('to_folder') or where}."
        return None

    # ---- files ----
    if action == "renamed":
        return f"Renamed {m.get('old_name') or ev.old_path} to {m.get('new_name') or base} in {where}."
    if action == "moved":
        return f"Moved {m.get('new_name') or base} from {m.get('from_folder') or 'another folder'} to {m.get('to_folder') or where}."
    if action == "deleted":
        return f"Deleted {base} from {where}."

    if action == "created":
        if kind == "image":
            return f"Image {base} was added to {where}."
        if kind == "pdf":
            if (m.get("root") or "").lower() == "downloads" or where.lower() == "downloads":
                return f"Downloaded the PDF {base} to {where}."
            return f"Added the PDF {base} to {where}."
        if kind in ("presentation", "spreadsheet", "document", "archive"):
            return f"Added {base} to {where}."
        if kind == "code" and (ev.project_name or ev.branch):
            branch = f" on the {ev.branch} branch" if ev.branch else ""
            return f"Created {base} in the {ev.project_name or where} project{branch}."
        return f"Created {base} in {where}."

    # modified / opened
    if kind == "image":
        return f"Edited the image {base} in {where}."
    if kind in ("pdf", "presentation", "spreadsheet", "document"):
        return f"{_KIND_VERB.get(kind, 'Worked on')} {base}."
    branch = f" on the {ev.branch} branch" if ev.branch else ""
    proj = ev.project_name or where
    return f"Worked on {name} in the {proj} project{branch}."


def build_memory_content(ev: ContextEvent) -> Optional[str]:
    """Render a ContextEvent into a natural-language memory string.

    Returns None if the event carries nothing worth remembering.
    """
    st = ev.source_type

    # A dev-context active-window event has been enriched with file/project/branch — store
    # it as meaningful work, NOT as "Using VS Code" (which would be noise).
    if st == "active_window" and (ev.file_path or ev.repository or ev.project_name):
        where = ev.project_name or ev.repository or "a project"
        branch = f" on the {ev.branch} branch" if ev.branch else ""
        if ev.file_path:
            return f"Working on {ev.file_path} in the {where} project{branch}."
        return f"Working in the {where} project{branch}."

    if st == "git":
        where = ev.project_name or ev.repository or ev.folder or "a project"
        branch = f" on the {ev.branch} branch" if ev.branch else ""
        file_bit = f", currently in {ev.file_path}" if ev.file_path else ""
        return f"Working in the {where} repository{branch}{file_bit}."

    if st == "file":
        return _file_activity_sentence(ev)

    if st == "browser":
        title = ev.title or ev.url or "a web page"
        domain = f" on {ev.domain}" if ev.domain else ""
        return f"Researching \"{title}\"{domain}."

    if st == "terminal":
        cmd = ev.content or ev.title
        if not cmd:
            return None
        where = f" while working in {ev.project_name or ev.folder}" if (ev.project_name or ev.folder) else ""
        return f"Used the command `{cmd}`{where}."

    if st == "active_window":
        if ev.metadata.get("app_usage") and ev.application:
            return f"Spent time in {ev.application}."
        # generic app focus with no dev/project context is not worth remembering
        return None

    if st == "manual":
        return ev.content or ev.title

    return ev.content or ev.title


# Supermemory metadata must be flat scalars (str/int/float/bool) — nested objects are
# rejected with 400. These internal keys are UI/engine-only and must never be sent.
_INTERNAL_META_KEYS = {"detection", "file_from_scan", "exe", "is_browser", "is_terminal"}


def build_metadata(ev: ContextEvent) -> dict[str, Any]:
    """Flat, scalar-only metadata that round-trips through Supermemory."""
    meta: dict[str, Any] = {
        "source_type": ev.source_type,
        "timestamp": ev.timestamp,
    }
    if ev.action:
        meta["action"] = ev.action
    for key in (
        "application", "project_name", "repository", "branch",
        "file_path", "folder", "url", "domain",
    ):
        val = getattr(ev, key)
        if val:
            meta[key] = val
    if ev.title:
        meta["event_title"] = ev.title
    # merge any extra source-provided metadata, but only flat scalar values
    for k, v in (ev.metadata or {}).items():
        if k in _INTERNAL_META_KEYS or k in meta:
            continue
        if isinstance(v, (str, int, float, bool)):
            meta[k] = v
    return meta


async def ingest_event(ev: ContextEvent) -> Optional[dict[str, Any]]:
    """Store one ContextEvent as a semantic memory. Returns the add result or None."""
    content = build_memory_content(ev)
    if not content or len(content.strip()) < 8:
        return None
    # privacy redaction BEFORE anything reaches Supermemory
    content = redact(content)
    try:
        result = await get_supermemory().add_memory(content, metadata=redact_dict(build_metadata(ev)))
        log.info("ingested memory %s (%s)", result.get("id"), ev.source_type)
        return result
    except Exception as exc:  # noqa: BLE001 - ingestion must never crash the engine
        log.warning("ingest failed for %s: %s", ev.source_type, exc)
        return None

"""Context Passport — the portable, user-owned representation of the current work state.

Derived from REAL ContextOS signals: the live current context, the active Context Session,
recent Supermemory memories, derived decisions/blockers, and related semantic retrieval.
User corrections (goal/task/added decisions/blockers/pins/removals) persist in a local
sidecar and override the derived values. Privacy redaction is applied on the way out.

This is NOT chat sync — it's a concise, AI-ready snapshot the user owns and can hand to any
tool (Claude Code / ChatGPT / Cursor) so their context follows them.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from app.core.config import STATE_DIR
from app.core.privacy import redact
from app.memory import sessions as S
from app.memory.derive import derive_blockers, derive_decisions, suggest_next_action
from app.models.context_event import ContextEvent
from app.services.supermemory_service import get_supermemory

_CORRECTIONS = STATE_DIR / "passport.json"


def _load_corrections() -> dict[str, Any]:
    if _CORRECTIONS.exists():
        try:
            return json.loads(_CORRECTIONS.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {"goal": None, "task": None, "added_decisions": [], "added_blockers": [],
            "removed": [], "pinned": []}


def _save_corrections(data: dict[str, Any]) -> None:
    _CORRECTIONS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def apply_correction(**kw: Any) -> dict[str, Any]:
    c = _load_corrections()
    if kw.get("goal") is not None:
        c["goal"] = redact(kw["goal"]) or None
    if kw.get("task") is not None:
        c["task"] = redact(kw["task"]) or None
    if kw.get("add_decision"):
        c.setdefault("added_decisions", []).append(redact(kw["add_decision"]))
    if kw.get("add_blocker"):
        c.setdefault("added_blockers", []).append(redact(kw["add_blocker"]))
    if kw.get("remove"):
        c.setdefault("removed", []).append(kw["remove"])  # memory_id to hide
    if kw.get("pin"):
        c.setdefault("pinned", []).append(kw["pin"])  # memory_id to keep
    _save_corrections(c)
    return c


async def build_passport(current: Optional[ContextEvent]) -> dict[str, Any]:
    sm = get_supermemory()
    corr = _load_corrections()
    removed = set(corr.get("removed", []))

    memories = await sm.list_memories(limit=300)
    memories = [m for m in memories if m.id not in removed]

    all_sessions = S.build_sessions(memories)

    # active session = the one matching the current project, else most recent
    project = (current.project_name or current.repository) if current else None
    active = None
    if project:
        active = next((s for s in all_sessions if s["project"] == project), None)
    if not active and all_sessions:
        active = all_sessions[0]

    # recent meaningful work (newest first, skip trivial window focus)
    def ts(m):  # noqa: ANN001
        v = m.metadata.get("timestamp")
        return v if isinstance(v, (int, float)) else 0
    recent = sorted([m for m in memories if m.source_type != "active_window" or m.file_path],
                    key=ts, reverse=True)[:8]

    decisions = derive_decisions(memories)
    blockers = derive_blockers(memories)
    for d in corr.get("added_decisions", []):
        decisions.insert(0, {"kind": "decision", "text": d, "memory_id": None, "source": "user"})
    for b in corr.get("added_blockers", []):
        blockers.insert(0, {"kind": "blocker", "text": b, "memory_id": None, "source": "user"})

    # related semantic context for the current activity (real Supermemory search)
    related: list[dict[str, Any]] = []
    if current:
        from app.memory.retrieval import build_context_query

        q = build_context_query(current)
        hits = await sm.search(q, limit=5)
        related = [{"text": redact(h.content or h.title or ""), "id": h.id,
                    "score": h.score, "source": h.source_type} for h in hits if h.id not in removed]

    recent_files: list[str] = []
    for m in recent:
        if m.file_path and m.file_path not in recent_files:
            recent_files.append(m.file_path)

    goal = corr.get("goal") or (active["title"] if active else (f"Working on {project}" if project else None))
    task = corr.get("task")
    if not task and current:
        if current.file_path:
            task = f"Editing {current.file_path}"
        elif current.domain:
            task = f"Researching on {current.domain}"
    next_action = suggest_next_action(recent, blockers)

    last_state = None
    if recent:
        last_state = redact(recent[0].content or recent[0].title or "")

    return {
        "generated_at": int(time.time() * 1000),
        "goal": goal,
        "project": project,
        "repository": current.repository if current else (active["project"] if active else None),
        "branch": current.branch if current else None,
        "task": task,
        "active_session": {
            "id": active["id"], "title": active["title"], "count": active["count"],
            "last_activity": active["last_activity"],
        } if active else None,
        "recent_work": [{"text": redact(m.content or m.title or ""), "id": m.id,
                         "source": m.source_type, "created_at": m.created_at} for m in recent],
        "recent_files": recent_files[:8],
        "decisions": decisions[:8],
        "blockers": blockers[:8],
        "related_context": related,
        "last_known_state": last_state,
        "suggested_next_action": next_action,
        "corrections_applied": {
            "goal": corr.get("goal") is not None,
            "task": corr.get("task") is not None,
            "added_decisions": len(corr.get("added_decisions", [])),
            "added_blockers": len(corr.get("added_blockers", [])),
            "removed": len(removed),
        },
    }


def to_markdown(p: dict[str, Any]) -> str:
    lines = ["# ContextOS Context Passport", ""]
    lines.append(f"**Goal:** {p.get('goal') or '—'}")
    if p.get("project"):
        repo = p.get("repository") or p["project"]
        branch = f" ({p['branch']})" if p.get("branch") else ""
        lines.append(f"**Project:** {repo}{branch}")
    if p.get("task"):
        lines.append(f"**Current task:** {p['task']}")
    if p.get("active_session"):
        lines.append(f"**Active session:** {p['active_session']['title']} ({p['active_session']['count']} activities)")
    lines.append("")
    if p.get("recent_work"):
        lines.append("## Recent work")
        for w in p["recent_work"][:6]:
            lines.append(f"- {w['text']}")
        lines.append("")
    if p.get("decisions"):
        lines.append("## Decisions")
        for d in p["decisions"]:
            lines.append(f"- {d['text']}")
        lines.append("")
    if p.get("blockers"):
        lines.append("## Blockers / errors")
        for b in p["blockers"]:
            lines.append(f"- {b['text']}")
        lines.append("")
    if p.get("recent_files"):
        lines.append("## Recent files")
        for f in p["recent_files"]:
            lines.append(f"- `{f}`")
        lines.append("")
    if p.get("last_known_state"):
        lines.append(f"**Last known state:** {p['last_known_state']}")
    if p.get("suggested_next_action"):
        lines.append(f"**Suggested next action:** {p['suggested_next_action']}")
    lines.append("")
    lines.append("_Generated by ContextOS — your context follows you._")
    return "\n".join(lines)

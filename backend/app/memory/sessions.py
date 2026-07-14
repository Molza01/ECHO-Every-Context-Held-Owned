"""Context Sessions — group real memories into resumable work sessions.

Deterministic clustering: memories are grouped by their project / repository / domain, then
split into sessions wherever there is a temporal gap. Titles come from the dominant project
or topic. User overrides (rename / pin) persist in a small local JSON sidecar — NOT a
database, just ContextOS-local state. All underlying data is real Supermemory memory.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import STATE_DIR
from app.models.context_event import Memory
from app.services.supermemory_service import get_supermemory

_GAP_MS = 90 * 60 * 1000  # a >90-min gap starts a new session
_OVERRIDES = STATE_DIR / "sessions.json"


def _load_overrides() -> dict[str, Any]:
    if _OVERRIDES.exists():
        try:
            return json.loads(_OVERRIDES.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_overrides(data: dict[str, Any]) -> None:
    _OVERRIDES.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _ts(m: Memory) -> int:
    v = m.metadata.get("timestamp")
    if isinstance(v, (int, float)):
        return int(v)
    if m.created_at:
        try:
            return int(datetime.fromisoformat(m.created_at.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:  # noqa: BLE001
            return 0
    return 0


def _group_key(m: Memory) -> str:
    return (m.project_name or m.repository or m.domain or "General").strip()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "session"


def build_sessions(memories: list[Memory]) -> list[dict[str, Any]]:
    overrides = _load_overrides()
    by_group: dict[str, list[Memory]] = {}
    for m in memories:
        by_group.setdefault(_group_key(m), []).append(m)

    sessions: list[dict[str, Any]] = []
    for group, mems in by_group.items():
        mems.sort(key=_ts)
        cluster: list[Memory] = []
        last_ts = None
        for m in mems:
            ts = _ts(m)
            if last_ts is not None and ts - last_ts > _GAP_MS and cluster:
                sessions.append(_make_session(group, cluster, overrides))
                cluster = []
            cluster.append(m)
            last_ts = ts
        if cluster:
            sessions.append(_make_session(group, cluster, overrides))

    sessions.sort(key=lambda s: s["last_activity"], reverse=True)
    return sessions


def _make_session(group: str, mems: list[Memory], overrides: dict[str, Any]) -> dict[str, Any]:
    start = _ts(mems[0])
    end = _ts(mems[-1])
    sid = f"{_slug(group)}-{start}"
    sources = sorted({(m.source_type or "unknown") for m in mems})
    files = [m.file_path for m in mems if m.file_path][:6]
    ov = overrides.get(sid, {})
    return {
        "id": sid,
        "title": ov.get("title") or _title_for(group, mems),
        "auto_title": _title_for(group, mems),
        "project": group,
        "pinned": bool(ov.get("pinned")),
        "start": start,
        "last_activity": end,
        "count": len(mems),
        "sources": sources,
        "files": files,
        "memory_ids": [m.id for m in mems],
        "preview": [(m.content or m.title or "")[:90] for m in mems[-4:]][::-1],
    }


def _title_for(group: str, mems: list[Memory]) -> str:
    if group and group != "General":
        return f"Working on {group}"
    # fall back to the most common domain or a generic label
    domains = [m.domain for m in mems if m.domain]
    if domains:
        return f"Researching on {max(set(domains), key=domains.count)}"
    return "General activity"


async def list_sessions(limit: int = 400) -> list[dict[str, Any]]:
    memories = await get_supermemory().list_memories(limit=limit)
    return build_sessions(memories)


async def get_session(session_id: str) -> Optional[dict[str, Any]]:
    for s in await list_sessions():
        if s["id"] == session_id:
            return s
    return None


def rename_session(session_id: str, title: str) -> None:
    ov = _load_overrides()
    ov.setdefault(session_id, {})["title"] = title.strip()
    _save_overrides(ov)


def set_pinned(session_id: str, pinned: bool) -> None:
    ov = _load_overrides()
    ov.setdefault(session_id, {})["pinned"] = pinned
    _save_overrides(ov)


def continue_candidates(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sessions worth resuming: recent (last 24h) but not touched in the last 10 min."""
    now = time.time() * 1000
    out = []
    for s in sessions:
        age = now - s["last_activity"]
        if s["pinned"] or (10 * 60 * 1000 < age < 24 * 60 * 60 * 1000):
            out.append(s)
    out.sort(key=lambda s: (not s["pinned"], -s["last_activity"]))
    return out[:5]

"""ContextOS REST API — all backed by real Supermemory Local + the ambient engine."""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.context.engine import get_engine
from app.core.config import get_settings
from app.core.container import user_container_tag
from app.memory.graph import build_graph
from app.memory.ranking import rank
from app.models.context_event import ContextEvent
from app.services.supermemory_service import get_supermemory

router = APIRouter()


# ----- system / status ----------------------------------------------------------------
@router.get("/api/status")
async def status() -> dict[str, Any]:
    settings = get_settings()
    engine = get_engine()
    health = await get_supermemory().health()
    return {
        "supermemory": health,
        "user_container": user_container_tag(),
        "sources": engine.source_status,
        "surface_threshold": settings.contextos_surface_threshold,
    }


@router.get("/api/context/current")
async def current_context() -> dict[str, Any]:
    engine = get_engine()
    return {
        "context": engine.current_context.model_dump() if engine.current_context else None,
        "last_update": engine.last_update.model_dump() if engine.last_update else None,
        "phase": engine.phase,
    }


# ----- Context Passport (portable user-owned context) ---------------------------------
@router.get("/api/context/passport")
async def context_passport() -> dict[str, Any]:
    from app.memory.passport import build_passport

    return await build_passport(get_engine().current_context)


@router.get("/api/context/passport/export")
async def passport_export(format: str = "markdown") -> Any:
    from fastapi.responses import PlainTextResponse

    from app.memory.passport import build_passport, to_markdown

    p = await build_passport(get_engine().current_context)
    if format in ("md", "markdown"):
        return PlainTextResponse(to_markdown(p), media_type="text/markdown")
    return p


class PassportCorrection(BaseModel):
    goal: Optional[str] = None
    task: Optional[str] = None
    add_decision: Optional[str] = None
    add_blocker: Optional[str] = None
    remove: Optional[str] = None  # memory id to hide
    pin: Optional[str] = None     # memory id to keep


@router.post("/api/context/passport/correct")
async def passport_correct(c: PassportCorrection) -> dict[str, Any]:
    from app.memory.passport import apply_correction, build_passport

    apply_correction(**c.model_dump(exclude_none=True))
    return await build_passport(get_engine().current_context)


@router.get("/api/context/decisions")
async def context_decisions() -> dict[str, Any]:
    from app.memory.derive import derive_decisions

    mems = await get_supermemory().list_memories(limit=300)
    return {"decisions": derive_decisions(mems)}


@router.get("/api/context/blockers")
async def context_blockers() -> dict[str, Any]:
    from app.memory.derive import derive_blockers

    mems = await get_supermemory().list_memories(limit=300)
    return {"blockers": derive_blockers(mems)}


@router.get("/api/context/project/{project}")
async def context_project(project: str) -> dict[str, Any]:
    from app.memory.derive import derive_blockers, derive_decisions

    mems = await get_supermemory().list_memories(limit=400)
    scoped = [m for m in mems if (m.project_name == project or m.repository == project)]
    return {
        "project": project,
        "memory_count": len(scoped),
        "files": list({m.file_path for m in scoped if m.file_path})[:20],
        "decisions": derive_decisions(scoped),
        "blockers": derive_blockers(scoped),
        "recent": [m.model_dump() for m in scoped[:10]],
    }


@router.get("/api/sessions/{session_id}/resume")
async def session_resume(session_id: str) -> dict[str, Any]:
    from app.memory import sessions as S
    from app.memory.derive import derive_blockers, derive_decisions, suggest_next_action

    s = await S.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    mems = await get_supermemory().list_memories(limit=500)
    ids = set(s["memory_ids"])
    sm = [m for m in mems if m.id in ids]
    decisions = derive_decisions(sm)
    blockers = derive_blockers(sm)
    return {
        "session_id": session_id,
        "title": s["title"],
        "project": s["project"],
        "what_you_were_doing": (sm[-1].content or sm[-1].title) if sm else None,
        "relevant_files": s["files"],
        "decisions": decisions,
        "blockers": blockers,
        "last_problem": blockers[0]["text"] if blockers else None,
        "suggested_next_action": suggest_next_action(list(reversed(sm)), blockers),
        "memory_count": len(sm),
    }


@router.get("/api/diagnostics")
async def diagnostics() -> dict[str, Any]:
    """Observability into the whole ambient pipeline — no secrets, dev-friendly."""
    engine = get_engine()
    health = await get_supermemory().health()
    return {
        "supermemory": health,
        "phase": engine.phase,
        "ws_clients": engine.ws_clients,
        "sources": engine.source_status,
        "activity_roots": [str(r) for r in getattr(engine._watcher, "roots", [])],
        "last_suggestion": engine.last_suggestion,
        "pipeline": engine.diag,
    }


# ----- memories: search / list / delete -----------------------------------------------
class SearchRequest(BaseModel):
    q: str
    limit: int = 10


@router.post("/api/search")
async def search(req: SearchRequest) -> dict[str, Any]:
    memories = await get_supermemory().search(req.q, limit=req.limit)
    return {"query": req.q, "results": [m.model_dump() for m in memories]}


@router.get("/api/memories")
async def list_memories(limit: int = 100, page: int = 1) -> dict[str, Any]:
    memories = await get_supermemory().list_memories(limit=limit, page=page)
    return {"memories": [m.model_dump() for m in memories]}


@router.delete("/api/memories/{doc_id}")
async def delete_memory(doc_id: str) -> dict[str, Any]:
    ok = await get_supermemory().delete_memory(doc_id)
    if not ok:
        raise HTTPException(status_code=502, detail="delete failed")
    return {"deleted": doc_id}


# ----- interactive memory actions (real, via Supermemory PATCH) -----------------------
class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    pinned: Optional[bool] = None
    important: Optional[bool] = None
    irrelevant: Optional[bool] = None
    note: Optional[str] = None


@router.patch("/api/memories/{doc_id}")
async def update_memory(doc_id: str, upd: MemoryUpdate) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if upd.pinned is not None:
        meta["contextos_pinned"] = upd.pinned
    if upd.important is not None:
        meta["contextos_important"] = upd.important
    if upd.irrelevant is not None:
        meta["contextos_irrelevant"] = upd.irrelevant
    if upd.note is not None:
        meta["contextos_note"] = upd.note
    ok = await get_supermemory().update_memory(
        doc_id, content=upd.content, metadata=meta or None
    )
    if not ok:
        raise HTTPException(status_code=502, detail="update failed")
    return {"updated": doc_id, "content_changed": upd.content is not None, "metadata": meta}


# ----- Ask ContextOS (grounded natural-language Q&A) -----------------------------------
class AskRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = []


@router.post("/api/ask")
async def ask_contextos(req: AskRequest) -> dict[str, Any]:
    from app.memory.ask import ask

    return await ask(req.question, req.history)


# ----- Context Sessions ---------------------------------------------------------------
@router.get("/api/sessions")
async def sessions() -> dict[str, Any]:
    from app.memory import sessions as S

    items = await S.list_sessions()
    return {"sessions": items, "continue": S.continue_candidates(items)}


@router.get("/api/sessions/{session_id}")
async def session_detail(session_id: str) -> dict[str, Any]:
    from app.memory import sessions as S

    s = await S.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    mems = await get_supermemory().list_memories(limit=500)
    ids = set(s["memory_ids"])
    s["memories"] = [m.model_dump() for m in mems if m.id in ids]
    return s


class SessionRename(BaseModel):
    title: str


@router.post("/api/sessions/{session_id}/rename")
async def session_rename(session_id: str, body: SessionRename) -> dict[str, Any]:
    from app.memory import sessions as S

    S.rename_session(session_id, body.title)
    return {"renamed": session_id, "title": body.title}


class SessionPin(BaseModel):
    pinned: bool


@router.post("/api/sessions/{session_id}/pin")
async def session_pin(session_id: str, body: SessionPin) -> dict[str, Any]:
    from app.memory import sessions as S

    S.set_pinned(session_id, body.pinned)
    return {"session": session_id, "pinned": body.pinned}


# ----- user profile + recent activity + continue --------------------------------------
@router.get("/api/profile")
async def profile() -> dict[str, Any]:
    from app.memory.profile import build_profile

    return await build_profile()


@router.get("/api/activity/recent")
async def recent_activity(limit: int = 30) -> dict[str, Any]:
    memories = await get_supermemory().list_memories(limit=limit, order="desc")
    return {"items": [m.model_dump() for m in memories]}


# ----- watched locations (system-wide activity capture management) --------------------
@router.get("/api/analytics")
async def analytics(period: str = "week") -> dict[str, Any]:
    from app.memory.analytics import build_analytics

    return await build_analytics(period)


class RevealRequest(BaseModel):
    path: str


@router.post("/api/activity/reveal")
async def reveal_in_explorer(req: RevealRequest) -> dict[str, Any]:
    """Open the OS file manager at a file — only for paths inside watched locations."""
    import subprocess
    import sys
    from pathlib import Path

    from app.context import watched_locations as WL

    try:
        target = Path(req.path).expanduser().resolve()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid path")
    roots = WL.existing_roots()
    if not any(str(target).startswith(str(r)) for r in roots):
        raise HTTPException(status_code=403, detail="path is outside watched locations")
    if not target.exists():
        raise HTTPException(status_code=404, detail="path no longer exists")
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{target}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target.parent)])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"could not open: {exc}")
    return {"revealed": str(target)}


@router.get("/api/activity/locations")
async def get_locations() -> dict[str, Any]:
    from app.context import watched_locations as WL

    return WL.status()


class LocationOp(BaseModel):
    action: str  # add | remove | exclude | pause | resume
    path: Optional[str] = None
    pattern: Optional[str] = None


@router.post("/api/activity/locations")
async def manage_locations(op: LocationOp) -> dict[str, Any]:
    from app.context import watched_locations as WL

    if op.action == "add" and op.path:
        WL.add_root(op.path)
    elif op.action == "remove" and op.path:
        WL.remove_root(op.path)
    elif op.action == "exclude" and op.pattern:
        WL.add_exclude(op.pattern)
    elif op.action == "pause":
        WL.set_paused(True)
    elif op.action == "resume":
        WL.set_paused(False)
    else:
        raise HTTPException(status_code=400, detail="invalid location op")
    # apply immediately by restarting the watcher
    get_engine().restart_watcher()
    return WL.status()


# ----- timeline (chronological real memories) -----------------------------------------
@router.get("/api/timeline")
async def timeline(limit: int = 150) -> dict[str, Any]:
    memories = await get_supermemory().list_memories(limit=limit, order="desc")
    items = [m.model_dump() for m in memories if m.created_at]
    return {"items": items}


# ----- graph --------------------------------------------------------------------------
@router.get("/api/graph")
async def graph(limit: int = 120) -> dict[str, Any]:
    memories = await get_supermemory().list_memories(limit=limit)
    return build_graph(memories)


# ----- related suggestions for an ad-hoc context (e.g. a filename) --------------------
class RelatedRequest(BaseModel):
    file_path: Optional[str] = None
    project_name: Optional[str] = None
    repository: Optional[str] = None
    query: Optional[str] = None


@router.post("/api/related")
async def related(req: RelatedRequest) -> dict[str, Any]:
    ev = ContextEvent(
        source_type="manual",
        file_path=req.file_path,
        project_name=req.project_name,
        repository=req.repository,
        title=req.query,
    )
    from app.memory.retrieval import build_context_query

    q = req.query or build_context_query(ev)
    memories = await get_supermemory().search(q, limit=10)
    surfaced = rank(ev, memories)
    return {"query": q, "surfaced": [s.model_dump() for s in surfaced]}


# ----- ingestion from external sources (browser extension, terminal, manual) ----------
class IngestEvent(BaseModel):
    source_type: str
    application: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    project_name: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    file_path: Optional[str] = None
    folder: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    metadata: dict[str, Any] = {}
    set_current: bool = True


@router.post("/api/ingest")
async def ingest(ev: IngestEvent) -> dict[str, Any]:
    engine = get_engine()
    context_event = ContextEvent(
        source_type=ev.source_type,  # type: ignore[arg-type]
        application=ev.application,
        title=ev.title,
        content=ev.content,
        project_name=ev.project_name,
        repository=ev.repository,
        branch=ev.branch,
        file_path=ev.file_path,
        folder=ev.folder,
        url=ev.url,
        domain=ev.domain,
        metadata=ev.metadata or {},
        timestamp=int(time.time() * 1000),
    )
    await engine.submit_external(context_event, set_current=ev.set_current)
    return {"accepted": True, "source_type": ev.source_type}


class CommandImport(BaseModel):
    command: str
    project_name: Optional[str] = None
    repository: Optional[str] = None
    folder: Optional[str] = None


@router.post("/api/commands/import")
async def import_command(cmd: CommandImport) -> dict[str, Any]:
    """Explicit, user-initiated terminal command import (no keylogging)."""
    engine = get_engine()
    ev = ContextEvent(
        source_type="terminal",
        content=cmd.command.strip(),
        title=cmd.command.strip()[:80],
        project_name=cmd.project_name,
        repository=cmd.repository,
        folder=cmd.folder,
    )
    await engine.submit_external(ev, set_current=False)
    return {"remembered": cmd.command}


# ----- privacy: source toggles + export -----------------------------------------------
class SourceToggle(BaseModel):
    source: str
    enabled: bool


@router.post("/api/sources/toggle")
async def toggle_source(t: SourceToggle) -> dict[str, Any]:
    engine = get_engine()
    engine.set_source_enabled(t.source, t.enabled)
    return {"sources": engine.source_status}


@router.get("/api/export")
async def export_memories() -> dict[str, Any]:
    """ContextOS export of the user's local memories (built from Supermemory data)."""
    memories = await get_supermemory().list_memories(limit=1000)
    return {
        "export_kind": "contextos-memory-export",
        "container": user_container_tag(),
        "exported_at": int(time.time() * 1000),
        "count": len(memories),
        "memories": [m.model_dump() for m in memories],
    }

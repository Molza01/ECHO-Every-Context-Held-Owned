"""The ContextOS ambient engine.

Core loop on every SIGNIFICANT context change:
  detect -> emit context.updated -> emit retrieval.started ->
  RETRIEVE related past memories (before ingesting, so we never surface ourselves) ->
  rank + confidence + why -> emit retrieval.completed / ambient.memory_found ->
  THEN ingest the current context as a memory (only if it is worth storing).

The user never searches manually.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional

from app.context.deduplicator import ContextDeduplicator
from app.context.filters import is_meaningful, is_worth_storing
from app.context.normalizer import enrich_with_project
from app.context.sources.active_window import ActiveWindowSource
from app.context.sources.activity_watcher import ActivityWatcher
from app.context.sources.file_source import FileContextSource
from app.context.sources.git_source import GitContextSource
from app.memory.ingestion import build_memory_content, ingest_event
from app.memory.ranking import rank
from app.memory.retrieval import build_context_query
from app.models.context_event import AmbientUpdate, ContextEvent
from app.services.supermemory_service import get_supermemory

log = logging.getLogger("contextos.engine")

# Broadcaster now emits typed lifecycle messages: {"type": <event>, "data": {...}}.
Broadcaster = Callable[[dict], Awaitable[None]]


def _now_ms() -> int:
    return int(time.time() * 1000)


class AmbientEngine:
    def __init__(self, poll_interval_s: float = 2.0) -> None:
        self.poll_interval_s = poll_interval_s
        self._window = ActiveWindowSource()
        self._git = GitContextSource()
        self._file = FileContextSource()
        self._watcher = ActivityWatcher()
        self._dedup = ContextDeduplicator(min_interval_s=1.5)
        self._broadcaster: Optional[Broadcaster] = None
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

        self.current_context: Optional[ContextEvent] = None
        self.last_update: Optional[AmbientUpdate] = None
        self.phase: str = "idle"  # idle | detected | checking | surfaced | none
        self.enabled: dict[str, bool] = {
            "active_window": True, "git": True, "file": True, "browser": True, "terminal": True,
        }
        self.source_status: dict[str, dict] = {}
        self._just_ingested_ids: set[str] = set()
        self._ingested_signatures: dict[str, float] = {}
        self._ingest_ttl_s = 300.0
        self._sm_reachable: Optional[bool] = None
        self.ws_clients = 0
        # proactive-suggestion cooldown, keyed by project (avoid nagging)
        self._proactive_cooldown: dict[str, float] = {}
        self._proactive_cooldown_s = 600.0
        self.last_suggestion: Optional[dict] = None
        # application-usage history: record "spent time in <app>" at most once per app
        # per cooldown window, so app usage is remembered without per-switch spam
        self._app_cooldown: dict[str, float] = {}
        self._app_cooldown_s = 240.0

        # Rolling diagnostics — the whole pipeline, observable at /api/diagnostics.
        self.diag: dict[str, Any] = {
            "last_event": None,
            "detected_at": None,
            "last_filter": None,
            "last_dedup": None,
            "last_query": None,
            "last_result_count": None,
            "last_ranked_count": None,
            "last_surfaced_ids": [],
            "last_ingest": None,
            "phase": "idle",
            "updated_at": None,
        }

    # -- lifecycle ----------------------------------------------------------------------
    def set_broadcaster(self, broadcaster: Broadcaster) -> None:
        self._broadcaster = broadcaster

    async def start(self) -> None:
        self._refresh_source_status()
        self._task = asyncio.create_task(self._run())
        # start the real filesystem watcher, bridging its thread back to this loop
        try:
            loop = asyncio.get_running_loop()
            started = self._watcher.start(self._on_file_event, loop)
            log.info("file watcher %s", "started" if started else "unavailable")
        except Exception as exc:  # noqa: BLE001
            log.warning("file watcher failed to start: %s", exc)
        log.info("ambient engine started (poll=%.1fs)", self.poll_interval_s)

    async def _on_file_event(self, ev: ContextEvent) -> None:
        """Callback from the activity watcher — real file/folder activity."""
        if not self.enabled.get("file", True):
            return
        _mark_detection(ev)
        # emit an INSTANT raw activity signal for the live feed (every meaningful event),
        # independent of retrieval/dedup so the user can verify capture in real time
        from app.memory.ingestion import build_memory_content

        await self._emit("activity.signal", {
            "action": ev.action,
            "kind": ev.metadata.get("file_kind"),
            "name": (ev.file_path or ev.title or "").split("\\")[-1].split("/")[-1],
            "folder": ev.folder,
            "application": ev.application,
            "text": build_memory_content(ev),
            "at": _now_ms(),
        })
        if self._dedup.is_significant_change(ev):
            await self._on_context_change(ev)

    def restart_watcher(self) -> bool:
        """Re-spawn the activity watcher after watched locations change."""
        return self._watcher.restart()

    async def stop(self) -> None:
        self._stop.set()
        self._watcher.stop()
        if self._task:
            await asyncio.gather(self._task, return_exceptions=True)

    async def _emit(self, event: str, data: dict) -> None:
        self.diag["updated_at"] = _now_ms()
        if self._broadcaster:
            try:
                await self._broadcaster({"type": event, "data": data})
            except Exception as exc:  # noqa: BLE001
                log.debug("emit %s failed: %s", event, exc)

    def _refresh_source_status(self) -> None:
        self.source_status = {
            "active_window": {"available": self._window.available(), "enabled": self.enabled["active_window"]},
            "git": {"available": self._git.available(), "enabled": self.enabled["git"]},
            "file": {"available": self._file.available(), "enabled": self.enabled["file"]},
            "browser": {"available": True, "enabled": self.enabled["browser"]},
            "terminal": {"available": True, "enabled": self.enabled["terminal"]},
        }

    def set_source_enabled(self, source: str, enabled: bool) -> None:
        if source in self.enabled:
            self.enabled[source] = enabled
            self._refresh_source_status()
            asyncio.create_task(
                self._emit("source.status_changed", {"sources": self.source_status})
            )

    # -- polling loop -------------------------------------------------------------------
    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
                await self._poll_supermemory_status()
            except Exception as exc:  # noqa: BLE001 - never let the loop die
                log.warning("engine tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_s)
            except asyncio.TimeoutError:
                pass

    async def _poll_supermemory_status(self) -> None:
        # only hit health occasionally (every ~10 ticks) and emit on change
        if int(time.time()) % 10 != 0:
            return
        health = await get_supermemory().health()
        reachable = bool(health.get("reachable"))
        if reachable != self._sm_reachable:
            self._sm_reachable = reachable
            await self._emit("supermemory.status_changed", health)

    async def _tick(self) -> None:
        if not self.enabled.get("active_window", True):
            return
        ev = self._window.sample()
        if not ev:
            return
        if self.enabled.get("git", True) or self.enabled.get("file", True):
            ev = enrich_with_project(
                ev,
                self._git if self.enabled.get("git", True) else _NullGit(),
                self._file if self.enabled.get("file", True) else _NullFile(),
            )
        _mark_detection(ev)

        meaningful = is_meaningful(ev)
        self.diag["last_filter"] = {"meaningful": meaningful, "signature": ev.signature()}
        if not meaningful:
            return
        significant = self._dedup.is_significant_change(ev)
        self.diag["last_dedup"] = {"significant": significant, "signature": ev.signature()}
        if not significant:
            return
        await self._on_context_change(ev)

    # -- external sources (browser extension, terminal import, manual) ------------------
    async def submit_external(self, ev: ContextEvent, *, set_current: bool = True) -> None:
        if not self.enabled.get(ev.source_type, True):
            return
        _mark_detection(ev)
        if not is_meaningful(ev):
            return
        if set_current and self._dedup.is_significant_change(ev):
            await self._on_context_change(ev)
        else:
            await self._ingest(ev)

    # -- the core transition (retrieve BEFORE ingest) -----------------------------------
    def _mark_app_usage(self, ev: ContextEvent) -> None:
        """Flag an app-focus event as worth remembering as usage history (cooldown-gated)."""
        if ev.source_type != "active_window" or ev.file_path or not ev.application:
            return
        app = ev.application
        now = time.time()
        if now - self._app_cooldown.get(app, 0) >= self._app_cooldown_s:
            self._app_cooldown[app] = now
            ev.metadata["app_usage"] = True

    async def _on_context_change(self, ev: ContextEvent) -> None:
        self.current_context = ev
        self._mark_app_usage(ev)
        self.diag["last_event"] = ev.model_dump()
        self.diag["detected_at"] = _now_ms()
        log.info("[context.updated] %s", ev.signature())

        self.phase = "detected"
        self.diag["phase"] = "detected"
        await self._emit("context.updated", {"context": ev.model_dump(), "detected_at": _now_ms()})

        # retrieval phase
        self.phase = "checking"
        self.diag["phase"] = "checking"
        query = build_context_query(ev)
        self.diag["last_query"] = query
        log.info("[retrieval.started] query=%r", query)
        await self._emit("retrieval.started", {"query": query})

        update = await self.retrieve_for(ev, query=query)
        self.last_update = update
        self.diag["last_ranked_count"] = len(update.surfaced)
        self.diag["last_surfaced_ids"] = [s.memory.id for s in update.surfaced]

        if update.surfaced:
            self.phase = "surfaced"
            self.diag["phase"] = "surfaced"
            log.info("[ambient.memory_found] %d surfaced (top=%s)",
                     len(update.surfaced), update.surfaced[0].memory.id)
            await self._emit("ambient.memory_found", update.model_dump())
        else:
            self.phase = "none"
            self.diag["phase"] = "none"
            log.info("[retrieval.completed] no relevant past context")
        await self._emit("retrieval.completed", update.model_dump())

        # proactive, cooldown-gated "you're returning to X" suggestion
        await self._maybe_proactive(ev, update)

        # ingest AFTER retrieval so the current context can never surface itself
        await self._ingest(ev)

    async def _maybe_proactive(self, ev: ContextEvent, update: AmbientUpdate) -> None:
        project = ev.project_name or ev.repository
        if not project or not update.surfaced:
            return
        now = time.time()
        if now - self._proactive_cooldown.get(project, 0) < self._proactive_cooldown_s:
            return
        # find the strongest surfaced memory from the same project that is genuinely older
        for s in update.surfaced:
            m = s.memory
            ts = m.metadata.get("timestamp")
            same_project = (m.project_name or m.repository) == project
            old_enough = isinstance(ts, (int, float)) and (now * 1000 - ts) > 20 * 60 * 1000
            if same_project and old_enough and s.context_confidence >= 55:
                self._proactive_cooldown[project] = now
                suggestion = {
                    "text": f"You're back on {project}. Last time you were: "
                            f"{(m.content or m.title or '').rstrip('.')}.",
                    "project": project,
                    "memory_id": m.id,
                    "confidence": s.context_confidence,
                    "created_at": _now_ms(),
                }
                self.last_suggestion = suggestion
                log.info("[proactive.suggestion] %s", suggestion["text"][:80])
                await self._emit("proactive.suggestion", suggestion)
                return

    async def _ingest(self, ev: ContextEvent) -> None:
        store, reason = is_worth_storing(ev)
        if not store:
            self.diag["last_ingest"] = {"stored": False, "reason": reason,
                                        "signature": ev.signature()}
            return

        sig = ev.signature()
        now = time.time()
        self._ingested_signatures = {
            k: t for k, t in self._ingested_signatures.items() if now - t < self._ingest_ttl_s
        }
        if sig in self._ingested_signatures:
            self.diag["last_ingest"] = {"stored": False, "reason": "duplicate within TTL",
                                        "signature": sig}
            return
        self._ingested_signatures[sig] = now

        res = await ingest_event(ev)
        if res and res.get("id"):
            self._just_ingested_ids.add(res["id"])
            if len(self._just_ingested_ids) > 50:
                self._just_ingested_ids = set(list(self._just_ingested_ids)[-25:])
            self.diag["last_ingest"] = {"stored": True, "reason": reason,
                                        "id": res["id"], "status": res.get("status")}
            log.info("[memory.ingested] %s (%s)", res["id"], ev.source_type)
            await self._emit("memory.ingested", {
                "id": res["id"], "source_type": ev.source_type,
                "preview": (build_memory_content(ev) or "")[:120],
            })
        else:
            self.diag["last_ingest"] = {"stored": False, "reason": "ingest returned no id"}

    async def retrieve_for(self, ev: ContextEvent, *, query: Optional[str] = None) -> AmbientUpdate:
        q = query or build_context_query(ev)
        try:
            memories = await get_supermemory().search(q, limit=10)
        except Exception as exc:  # noqa: BLE001
            log.warning("retrieval search failed: %s", exc)
            memories = []
        self.diag["last_result_count"] = len(memories)
        current_content = build_memory_content(ev)
        surfaced = rank(
            ev, memories,
            exclude_ids=set(self._just_ingested_ids),
            exclude_content=current_content,
        )
        return AmbientUpdate(context=ev, surfaced=surfaced, query=q, generated_at=_now_ms())


def _mark_detection(ev: ContextEvent) -> None:
    """Record which fields are genuinely DETECTED vs INFERRED, for honest UI labelling."""
    det: dict[str, str] = {}
    if ev.application:
        det["application"] = "detected"
    if ev.title:
        det["title"] = "detected"
    if ev.url:
        det["url"] = "detected"
    if ev.domain:
        det["domain"] = "detected"
    # file from window title = detected; file from recent-file scan = inferred
    if ev.file_path:
        det["file_path"] = "inferred" if ev.metadata.get("file_from_scan") else "detected"
    # git repo/branch come from the watched project dir, not necessarily the focused app
    if ev.repository:
        det["repository"] = "inferred"
    if ev.branch:
        det["branch"] = "inferred"
    if ev.project_name:
        det["project_name"] = det.get("file_path", "inferred")
    ev.metadata["detection"] = det


class _NullGit(GitContextSource):
    def available(self) -> bool:  # pragma: no cover - trivial
        return False


class _NullFile(FileContextSource):
    def available(self) -> bool:  # pragma: no cover - trivial
        return False


_engine: Optional[AmbientEngine] = None


def get_engine() -> AmbientEngine:
    global _engine
    if _engine is None:
        _engine = AmbientEngine()
    return _engine

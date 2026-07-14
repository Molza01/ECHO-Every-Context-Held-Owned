"""Rank real Supermemory search results for proactive surfacing."""
from __future__ import annotations

import time

from app.core.config import get_settings
from app.memory.confidence import score_memory
from app.models.context_event import ContextEvent, Memory, SurfacedMemory

# doc_id -> last surfaced epoch seconds (to apply the recently-surfaced penalty)
_recently_surfaced: dict[str, float] = {}
_RESURFACE_WINDOW_S = 90


def rank(
    ctx: ContextEvent,
    memories: list[Memory],
    *,
    exclude_ids: set[str] | None = None,
    exclude_content: str | None = None,
) -> list[SurfacedMemory]:
    """Filter duplicates, score, threshold, and order memories for surfacing."""
    settings = get_settings()
    now = time.time()
    seen_ids: set[str] = set(exclude_ids or set())
    seen_content: set[str] = set()
    if exclude_content:
        # never surface the memory describing the very context we are in right now
        seen_content.add(exclude_content.strip().lower()[:160])
    ranked: list[SurfacedMemory] = []

    for mem in memories:
        if not mem.id or mem.id in seen_ids:
            continue
        seen_ids.add(mem.id)

        # content-level dedup (same memory phrased identically)
        key = (mem.content or mem.title or "").strip().lower()[:160]
        if key and key in seen_content:
            continue
        seen_content.add(key)

        # a memory the user marked irrelevant is never surfaced proactively
        if mem.irrelevant:
            continue

        was_recent = (now - _recently_surfaced.get(mem.id, 0)) < _RESURFACE_WINDOW_S
        confidence, reasons = score_memory(ctx, mem, recently_surfaced=was_recent)

        # user signals: pinned/important memories get a real, explained boost
        if mem.pinned:
            confidence = min(100, confidence + 12)
            reasons.insert(0, "You pinned this memory")
        if mem.important:
            confidence = min(100, confidence + 8)
            reasons.insert(0, "You marked this important")

        # relevance threshold uses the REAL semantic score; ContextOS-only matches
        # (same repo/file with no semantic signal) still pass if confidence is high.
        semantic_ok = (mem.score or 0.0) >= settings.contextos_surface_threshold
        strong_context = confidence >= 60
        if not (semantic_ok or strong_context or mem.pinned or mem.important):
            continue

        ranked.append(
            SurfacedMemory(
                memory=mem,
                context_confidence=confidence,
                semantic_score=mem.score,
                reasons=reasons,
            )
        )

    ranked.sort(key=lambda s: s.context_confidence, reverse=True)
    top = ranked[:6]
    for s in top:
        _recently_surfaced[s.memory.id] = now
    return top

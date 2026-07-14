"""Deterministic ContextOS Context Confidence + transparent 'why this appeared' reasons.

IMPORTANT: We never fabricate Supermemory scores. `semantic_score` is the REAL value
returned by Supermemory search. The Context Confidence is ContextOS's own explainable
composite of transparent signals — clearly labelled as such in the UI.
"""
from __future__ import annotations

from app.models.context_event import ContextEvent, Memory

# Weights for the positive signals; the composite is clamped to 0..100. Semantic relevance
# leads, but an *exact* same-file / same-repo match is strong, near-certain evidence, so
# those structural signals carry real weight too.
_W_SEMANTIC = 0.50   # real Supermemory relevance score
_W_SAME_REPO = 0.16
_W_SAME_FILE = 0.18
_W_SAME_PROJECT = 0.08
_W_SAME_DOMAIN = 0.10
_W_RECENCY = 0.05


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def score_memory(
    ctx: ContextEvent,
    mem: Memory,
    *,
    recently_surfaced: bool = False,
) -> tuple[int, list[str]]:
    """Return (context_confidence 0..100, reasons)."""
    reasons: list[str] = []
    semantic = mem.score if mem.score is not None else 0.0
    total = _W_SEMANTIC * max(0.0, min(1.0, semantic))
    if semantic > 0:
        reasons.append("Semantically retrieved by Supermemory")

    if _norm(mem.repository) and _norm(mem.repository) == _norm(ctx.repository):
        total += _W_SAME_REPO
        reasons.append(f"Same repository ({mem.repository})")

    if _norm(mem.file_path) and _norm(mem.file_path) == _norm(ctx.file_path):
        total += _W_SAME_FILE
        reasons.append(f"Same file ({mem.file_path})")

    if _norm(mem.project_name) and _norm(mem.project_name) == _norm(ctx.project_name):
        # avoid double-crediting when repo already matched to the same thing
        if _norm(mem.repository) != _norm(ctx.repository):
            total += _W_SAME_PROJECT
        reasons.append(f"Same project ({mem.project_name})")

    if _norm(mem.domain) and _norm(mem.domain) == _norm(ctx.domain):
        total += _W_SAME_DOMAIN
        reasons.append(f"Related to {mem.domain}")

    # temporal recency: only genuinely recent memories (<= 3 days) get the nudge
    ts = mem.metadata.get("timestamp")
    if isinstance(ts, (int, float)):
        import time

        age_days = (time.time() * 1000 - ts) / 86_400_000
        if age_days <= 3:
            total += _W_RECENCY
            reasons.append("From your recent activity" if age_days <= 1 else "From the last few days")
    else:
        total += _W_RECENCY * 0.5  # unknown age: modest baseline

    if recently_surfaced:
        total *= 0.7  # recently-surfaced penalty so we don't nag with the same card

    confidence = int(round(max(0.0, min(1.0, total)) * 100))
    if not reasons:
        reasons.append("Related to your current context")
    return confidence, reasons

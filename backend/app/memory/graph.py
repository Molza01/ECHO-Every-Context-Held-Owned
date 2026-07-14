"""Build a memory relationship graph from REAL memories using transparent signals.

Supermemory Local has no graph endpoint (verified). ContextOS constructs the graph itself
from actual retrieved memories. Every edge has a defensible signal — no invented links.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any

from app.models.context_event import Memory

# Temporal-proximity window: memories created within this window are linked as "around
# the same time".
_TEMPORAL_WINDOW_MS = 30 * 60 * 1000  # 30 minutes


def _ts(mem: Memory) -> int | None:
    ts = mem.metadata.get("timestamp")
    if isinstance(ts, (int, float)):
        return int(ts)
    return None


def build_graph(memories: list[Memory]) -> dict[str, Any]:
    nodes = [
        {
            "id": m.id,
            "label": (m.title or m.content or "memory")[:60],
            "source_type": m.source_type or "unknown",
            "project": m.project_name,
            "repository": m.repository,
            "file_path": m.file_path,
            "domain": m.domain,
            "created_at": m.created_at,
        }
        for m in memories
    ]

    candidates: list[dict[str, Any]] = []
    for a, b in combinations(memories, 2):
        signals: list[str] = []
        if a.file_path and a.file_path == b.file_path:
            signals.append("same file")
        if a.domain and a.domain == b.domain:
            signals.append("same domain")
        if a.repository and a.repository == b.repository:
            signals.append("same repository")
        elif a.project_name and a.project_name == b.project_name:
            signals.append("same project")
        ta, tb = _ts(a), _ts(b)
        if ta is not None and tb is not None and abs(ta - tb) <= _TEMPORAL_WINDOW_MS:
            signals.append("around the same time")

        # A shared repository alone is too generic to be a useful edge (everything in one
        # project would connect to everything). Require a stronger/second signal.
        strong = any(s in signals for s in ("same file", "same domain", "same project"))
        if not signals or (len(signals) == 1 and not strong):
            continue
        candidates.append(
            {"source": a.id, "target": b.id, "signals": signals, "weight": len(signals)}
        )

    # Greedy degree-capped pruning keeps the graph readable instead of a hairball.
    candidates.sort(key=lambda e: e["weight"], reverse=True)
    degree: dict[str, int] = {}
    edges: list[dict[str, Any]] = []
    max_degree = 4
    for e in candidates:
        if degree.get(e["source"], 0) >= max_degree or degree.get(e["target"], 0) >= max_degree:
            continue
        edges.append(e)
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1

    return {"nodes": nodes, "edges": edges}

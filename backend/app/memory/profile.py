"""User context profile — derived entirely from real Supermemory memories."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.supermemory_service import get_supermemory


async def build_profile(limit: int = 500) -> dict[str, Any]:
    memories = await get_supermemory().list_memories(limit=limit)
    projects: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    files: list[str] = []
    pinned = 0

    for m in memories:
        if m.project_name:
            projects[m.project_name] += 1
        if m.source_type:
            sources[m.source_type] += 1
        if m.domain:
            domains[m.domain] += 1
        if m.file_path and m.file_path not in files:
            files.append(m.file_path)
        if m.pinned:
            pinned += 1

    return {
        "total_memories": len(memories),
        "pinned": pinned,
        "top_projects": [{"name": n, "count": c} for n, c in projects.most_common(6)],
        "top_sources": [{"name": n, "count": c} for n, c in sources.most_common(6)],
        "top_domains": [{"name": n, "count": c} for n, c in domains.most_common(5)],
        "recent_files": files[:8],
    }

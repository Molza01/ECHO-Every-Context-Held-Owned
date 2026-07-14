"""Contextual query generation: turn the CURRENT context into a semantic search query."""
from __future__ import annotations

from app.models.context_event import ContextEvent


def build_context_query(ev: ContextEvent) -> str:
    """Generate a natural-language query describing what the user is doing now.

    The query is intentionally descriptive (not keyword-y) so Supermemory's semantic
    search can relate it to past memories phrased with different words.
    """
    bits: list[str] = []

    if ev.file_path:
        bits.append(f"working on {ev.file_path}")
    if ev.project_name or ev.repository:
        bits.append(f"in the {ev.project_name or ev.repository} project")
    if ev.branch:
        bits.append(f"on the {ev.branch} branch")
    if ev.domain:
        bits.append(f"researching on {ev.domain}")
    if ev.title and ev.source_type == "browser":
        bits.append(f'about "{ev.title}"')
    if ev.application and not bits:
        bits.append(f"using {ev.application}")
    if ev.title and not bits:
        bits.append(ev.title)

    query = " ".join(bits).strip()
    return query or (ev.title or ev.application or "current work context")

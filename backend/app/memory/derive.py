"""Derive decisions, blockers, goal, and next action from REAL memories.

Deterministic + grounded: every derived item references the memory id it came from, and
carries a short evidence excerpt. No invention.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.context_event import Memory

_DECISION = re.compile(
    r"\b(decid|chose|choosing|switch(ed)? to|going with|will use|opted|settled on|adopt(ed)?)\b",
    re.IGNORECASE,
)
_BLOCKER = re.compile(
    r"\b(block(ed|er)?|error|fail(ed|ing)?|bug|stuck|can'?t|cannot|broken|crash|regression|"
    r"400|401|403|404|500|timeout|exception|traceback)\b",
    re.IGNORECASE,
)
_NEXT = re.compile(r"\b(todo|next|need to|should|follow[- ]?up|continue|finish|implement)\b", re.IGNORECASE)


def _item(m: Memory, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "text": (m.content or m.title or "").strip(),
        "memory_id": m.id,
        "source": m.source_type,
        "project": m.project_name,
        "created_at": m.created_at,
    }


def derive_decisions(memories: list[Memory]) -> list[dict[str, Any]]:
    out = [_item(m, "decision") for m in memories
           if not m.irrelevant and _DECISION.search(m.content or m.title or "")]
    return out[:12]


def derive_blockers(memories: list[Memory]) -> list[dict[str, Any]]:
    out = [_item(m, "blocker") for m in memories
           if not m.irrelevant and _BLOCKER.search(m.content or m.title or "")]
    return out[:12]


def suggest_next_action(memories: list[Memory], blockers: list[dict[str, Any]]) -> str | None:
    """Grounded next-action heuristic from the most recent signal."""
    if blockers:
        return f"Resolve: {blockers[0]['text'].rstrip('.')}."
    for m in memories:
        text = m.content or m.title or ""
        if _NEXT.search(text):
            return text.rstrip(".") + "."
    # else, continue the most recent file work
    for m in memories:
        if m.file_path:
            return f"Continue working on {m.file_path}."
    return None

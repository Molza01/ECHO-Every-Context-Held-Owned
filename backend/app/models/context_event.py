"""Normalized cross-source context model + memory/retrieval DTOs."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SourceType = Literal[
    "active_window",
    "git",
    "file",
    "browser",
    "terminal",
    "manual",
]


def _now_ms() -> int:
    return int(time.time() * 1000)


class ContextEvent(BaseModel):
    """A single normalized observation of what the user is doing right now.

    Not every source populates every field — that is expected.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source_type: SourceType
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
    # Activity semantics for the universal OS activity layer.
    action: Optional[str] = None  # created | modified | renamed | moved | deleted | opened
    old_path: Optional[str] = None  # previous path for renamed/moved events
    timestamp: int = Field(default_factory=_now_ms)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def signature(self) -> str:
        """Stable key describing *what* this context is about, for dedup/change detection."""
        parts = [
            self.source_type,
            self.action or "",
            self.application or "",
            self.project_name or "",
            self.repository or "",
            self.branch or "",
            self.file_path or "",
            self.old_path or "",
            self.domain or "",
            (self.url or "")[:120],
            (self.title or "")[:120],
        ]
        return "|".join(parts)


class Memory(BaseModel):
    """A memory as ContextOS understands it (normalized from Supermemory responses)."""

    id: str
    title: Optional[str] = None
    content: Optional[str] = None
    source_type: Optional[str] = None
    project_name: Optional[str] = None
    repository: Optional[str] = None
    file_path: Optional[str] = None
    domain: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Real Supermemory relevance score (0..1) when this came from a search; else None.
    score: Optional[float] = None
    # User-controlled state, persisted as Supermemory metadata (contextos_*).
    pinned: bool = False
    important: bool = False
    irrelevant: bool = False
    note: Optional[str] = None
    action: Optional[str] = None


class SurfacedMemory(BaseModel):
    """A ranked memory ready to be proactively shown, with ContextOS's explanation."""

    memory: Memory
    context_confidence: int  # 0..100, ContextOS Context Confidence (deterministic)
    semantic_score: Optional[float] = None  # raw Supermemory score, surfaced transparently
    reasons: list[str] = Field(default_factory=list)


class AmbientUpdate(BaseModel):
    """Payload pushed to the frontend when the active context changes."""

    context: Optional[ContextEvent] = None
    surfaced: list[SurfacedMemory] = Field(default_factory=list)
    query: Optional[str] = None
    generated_at: int = Field(default_factory=_now_ms)

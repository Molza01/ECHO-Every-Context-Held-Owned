"""Ask ContextOS — natural-language questions grounded in real Supermemory retrieval.

No hallucination: every answer is composed strictly from retrieved memory text and their
timestamps. If nothing relevant is found, it says so. Supports simple time scoping
("yesterday", "today", "this week", "around 3 pm") and follow-up questions via history.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from app.models.context_event import Memory
from app.services.supermemory_service import get_supermemory

_DAY_MS = 86_400_000


def _memory_ts(m: Memory) -> Optional[int]:
    ts = m.metadata.get("timestamp")
    if isinstance(ts, (int, float)):
        return int(ts)
    if m.created_at:
        try:
            return int(datetime.fromisoformat(m.created_at.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:  # noqa: BLE001
            return None
    return None


def parse_time_filter(q: str) -> Optional[tuple[int, int, str]]:
    """Return (start_ms, end_ms, label) if the question scopes a time, else None."""
    ql = q.lower()
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def ms(dt: datetime) -> int:
        return int(dt.timestamp() * 1000)

    if "yesterday" in ql:
        start = midnight - timedelta(days=1)
        return ms(start), ms(midnight), "yesterday"
    if "today" in ql or "so far today" in ql:
        return ms(midnight), ms(now + timedelta(minutes=1)), "today"
    if "this week" in ql:
        start = midnight - timedelta(days=now.weekday())
        return ms(start), ms(now + timedelta(minutes=1)), "this week"
    if "last week" in ql:
        end = midnight - timedelta(days=now.weekday())
        return ms(end - timedelta(days=7)), ms(end), "last week"
    if "this morning" in ql:
        return ms(midnight), ms(midnight + timedelta(hours=12)), "this morning"
    if "this afternoon" in ql:
        return ms(midnight + timedelta(hours=12)), ms(midnight + timedelta(hours=17)), "this afternoon"

    # "around 3 pm" / "at 15:00" — a +/-90min window today
    m = re.search(r"\b(?:around|at|by)?\s*(\d{1,2})\s*(am|pm)\b", ql)
    if not m:
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", ql)
    if m:
        try:
            hour = int(m.group(1))
            if m.re.groups >= 2 and m.group(2) in ("am", "pm"):
                if m.group(2) == "pm" and hour < 12:
                    hour += 12
                if m.group(2) == "am" and hour == 12:
                    hour = 0
            center = midnight + timedelta(hours=hour)
            return ms(center - timedelta(minutes=90)), ms(center + timedelta(minutes=90)), f"around {m.group(0).strip()}"
        except Exception:  # noqa: BLE001
            pass
    return None


def _age(ts: Optional[int]) -> str:
    if not ts:
        return ""
    secs = (time.time() * 1000 - ts) / 1000
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < _DAY_MS / 1000:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _compose(question: str, memories: list[Memory], tf: Optional[tuple[int, int, str]]) -> str:
    """Compose a grounded answer strictly from retrieved memories."""
    scope = f" {tf[2]}" if tf else ""
    if not memories:
        return (f"I don't have any memories{scope} about that yet. "
                "As you work, ContextOS will remember relevant activity here.")

    top = memories[0]
    lead_content = (top.content or top.title or "").rstrip(".")
    n = len(memories)
    when = _age(_memory_ts(top))
    when_txt = f" ({when})" if when else ""

    if n == 1:
        return f"Here's what I found{scope}: {lead_content}{when_txt}."
    return (f"Here's what I found{scope}: {lead_content}{when_txt} — "
            f"plus {n - 1} related {'memory' if n == 2 else 'memories'} below.")


async def ask(question: str, history: Optional[list[dict[str, str]]] = None) -> dict[str, Any]:
    tf = parse_time_filter(question)

    # follow-up: prepend the previous user turn so pronouns resolve ("what about it?")
    query = question
    if history:
        prev = [h.get("content", "") for h in history if h.get("role") == "user"]
        if prev:
            query = f"{prev[-1]} {question}"

    sm = get_supermemory()
    try:
        memories = await sm.search(query, limit=12)
    except Exception:  # noqa: BLE001 - Supermemory unreachable / erroring
        return {
            "question": question, "query": query,
            "answer": "I can't reach your local memory (Supermemory at localhost:6767) "
                      "right now. Make sure it's running, then ask again.",
            "grounded": False, "time_filter": tf[2] if tf else None, "evidence": [],
        }

    if tf:
        start, end, _ = tf
        # Time-scoped questions ("what did I do today?") are often too vague for semantic
        # search, so pull the chronological window directly and merge in any semantic hits.
        try:
            listed = await sm.list_memories(limit=300)
        except Exception:  # noqa: BLE001
            listed = []
        by_id = {m.id: m for m in memories if (ts := _memory_ts(m)) is not None and start <= ts < end}
        for m in listed:
            ts = _memory_ts(m)
            if ts is not None and start <= ts < end and m.id not in by_id:
                by_id[m.id] = m
        memories = sorted(by_id.values(), key=lambda m: _memory_ts(m) or 0, reverse=True)

    # drop memories the user marked irrelevant
    memories = [m for m in memories if not m.irrelevant]

    answer = _compose(question, memories, tf)
    return {
        "question": question,
        "query": query,
        "answer": answer,
        "grounded": bool(memories),
        "time_filter": tf[2] if tf else None,
        "evidence": [m.model_dump() for m in memories[:8]],
    }

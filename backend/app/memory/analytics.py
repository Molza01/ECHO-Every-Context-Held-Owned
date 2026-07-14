"""Work analytics — day / week / month summaries derived from REAL memories.

Counts are real activity events (not fabricated durations); "focus" = share of activity per
source/project, presented honestly as attention distribution.
"""
from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from app.services.supermemory_service import get_supermemory

_PERIODS = {"day": 1, "week": 7, "month": 30}


def _ts(m) -> int:  # noqa: ANN001
    v = m.metadata.get("timestamp")
    if isinstance(v, (int, float)):
        return int(v)
    if m.created_at:
        try:
            return int(datetime.fromisoformat(m.created_at.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:  # noqa: BLE001
            return 0
    return 0


async def build_analytics(period: str = "week") -> dict[str, Any]:
    days = _PERIODS.get(period, 7)
    now = datetime.now()
    start_ms = int((now - timedelta(days=days)).timestamp() * 1000)

    memories = await get_supermemory().list_memories(limit=1000)
    scoped = [m for m in memories if _ts(m) >= start_ms and not m.irrelevant]

    by_source: Counter[str] = Counter()
    by_project: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_hour: Counter[int] = Counter()
    by_day: Counter[str] = Counter()

    for m in scoped:
        by_source[m.source_type or "unknown"] += 1
        if m.project_name:
            by_project[m.project_name] += 1
        k = m.metadata.get("file_kind")
        if isinstance(k, str):
            by_kind[k] += 1
        dt = datetime.fromtimestamp(_ts(m) / 1000)
        by_hour[dt.hour] += 1
        by_day[dt.strftime("%Y-%m-%d")] += 1

    total = len(scoped)

    # day buckets across the window (chronological, filled)
    day_series = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        label = (now - timedelta(days=i)).strftime("%a" if days <= 7 else "%d")
        day_series.append({"date": d, "label": label, "count": by_day.get(d, 0)})

    hour_series = [{"hour": h, "count": by_hour.get(h, 0)} for h in range(24)]

    def top(counter: Counter, n=6):
        return [{"name": k, "count": v,
                 "pct": round(100 * v / total) if total else 0}
                for k, v in counter.most_common(n)]

    busiest_hour = max(by_hour, key=by_hour.get) if by_hour else None
    busiest_day = max(by_day, key=by_day.get) if by_day else None

    return {
        "period": period,
        "days": days,
        "total_events": total,
        "generated_at": int(time.time() * 1000),
        "by_source": top(by_source, 8),
        "by_project": top(by_project, 6),
        "by_kind": top(by_kind, 8),
        "day_series": day_series,
        "hour_series": hour_series,
        "most_active_source": by_source.most_common(1)[0][0] if by_source else None,
        "most_active_project": by_project.most_common(1)[0][0] if by_project else None,
        "busiest_hour": busiest_hour,
        "busiest_day": busiest_day,
    }

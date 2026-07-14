"""Context-change detection + debounce, so we act only on *significant* changes."""
from __future__ import annotations

import time

from app.models.context_event import ContextEvent


class ContextDeduplicator:
    def __init__(self, min_interval_s: float = 1.5) -> None:
        self._last_signature: str | None = None
        self._last_change_ts: float = 0.0
        self._min_interval_s = min_interval_s

    def is_significant_change(self, ev: ContextEvent) -> bool:
        """True if `ev` is a new context distinct from the last, past the debounce window."""
        sig = ev.signature()
        now = time.time()
        if sig == self._last_signature:
            return False
        if (now - self._last_change_ts) < self._min_interval_s:
            return False
        self._last_signature = sig
        self._last_change_ts = now
        return True

    @property
    def current_signature(self) -> str | None:
        return self._last_signature

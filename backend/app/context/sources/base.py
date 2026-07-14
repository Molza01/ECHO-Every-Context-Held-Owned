"""Context source adapter interface."""
from __future__ import annotations

from typing import Optional, Protocol

from app.models.context_event import ContextEvent


class ContextSource(Protocol):
    name: str

    def available(self) -> bool:
        """Whether this source can run on the current machine."""
        ...

    def sample(self) -> Optional[ContextEvent]:
        """Return the current context observation, or None if nothing meaningful."""
        ...

"""Single reusable container-tag utility.

Supermemory Local isolates memory strictly by container tag (verified: a search with
no container tag returns an empty scope). ContextOS scopes every add/search/list to one
persistent per-user container so the user's memory is a private, isolated brain.
"""
from __future__ import annotations

from app.core.config import get_settings

_PREFIX = "contextos:user:"


def user_container_tag() -> str:
    """The one container tag for this local user, e.g. ``contextos:user:local-ab12cd34``."""
    return f"{_PREFIX}{get_settings().resolved_user_id()}"


def container_tags() -> list[str]:
    """List form expected by Supermemory ``containerTags`` params."""
    return [user_container_tag()]

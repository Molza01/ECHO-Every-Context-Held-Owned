"""Demo data seeding — DEMO DATA ONLY.

Adds a set of realistic historical memories through the REAL Supermemory service so the
proactive ambient experience has history to retrieve. These are NOT injected into React
state; they enter Supermemory Local, get indexed, and flow through the normal
search -> ranking -> surfacing pipeline exactly like organic memories.

Every seeded memory is tagged metadata.seed=true so `--clean` can remove them safely.

Usage (from the backend/ directory, with the venv active):
    python -m scripts.seed_demo          # seed
    python -m scripts.seed_demo --clean  # delete only seeded demo memories
"""
from __future__ import annotations

import asyncio
import sys

from app.services.supermemory_service import get_supermemory

# (content, extra_metadata). source_type drives phrasing/colour in the UI.
SEED = [
    (
        "Fixed JWT expiration by changing refresh token handling in auth.ts on the "
        "feature/auth branch of ContextOS.",
        {"source_type": "manual", "project_name": "ContextOS", "repository": "ContextOS",
         "file_path": "auth.ts", "branch": "feature/auth"},
    ),
    (
        "Researched JWT refresh token rotation best practices while implementing "
        "authentication for ContextOS.",
        {"source_type": "browser", "domain": "auth0.com",
         "url": "https://auth0.com/docs/secure/tokens/refresh-tokens", "project_name": "ContextOS"},
    ),
    (
        "Read the OAuth 2.0 authorization code flow documentation to understand token exchange.",
        {"source_type": "browser", "domain": "oauth.net", "url": "https://oauth.net/2/"},
    ),
    (
        "Used `docker compose up --build` to rebuild the ContextOS backend containers.",
        {"source_type": "terminal", "project_name": "ContextOS", "repository": "ContextOS"},
    ),
    (
        "Debugged CORS errors between the React frontend and FastAPI backend by widening "
        "the allowed origins in main.py.",
        {"source_type": "manual", "project_name": "ContextOS", "repository": "ContextOS",
         "file_path": "backend/app/main.py"},
    ),
    (
        "Updated the authentication middleware to validate bearer tokens before hitting the "
        "protected routes.",
        {"source_type": "file", "project_name": "ContextOS", "repository": "ContextOS",
         "file_path": "backend/app/api/routes.py"},
    ),
    (
        "Switched from the main branch to feature/auth to isolate the login refactor work.",
        {"source_type": "git", "project_name": "ContextOS", "repository": "ContextOS",
         "branch": "feature/auth"},
    ),
    (
        "Note to self: refresh tokens should rotate on every use to limit replay risk.",
        {"source_type": "manual", "project_name": "ContextOS"},
    ),
]


async def seed() -> None:
    sm = get_supermemory()
    print("Seeding demo memories through the real Supermemory service...")
    for content, meta in SEED:
        meta = {**meta, "seed": True}
        res = await sm.add_memory(content, metadata=meta)
        print(f"  + {res.get('id')}  {content[:60]}...")
    await sm.aclose()
    print(f"Done. Seeded {len(SEED)} memories (metadata.seed=true).")


async def clean() -> None:
    sm = get_supermemory()
    memories = await sm.list_memories(limit=1000)
    seeded = [m for m in memories if (m.metadata or {}).get("seed") is True]
    print(f"Found {len(seeded)} seeded demo memories to remove...")
    for m in seeded:
        ok = await sm.delete_memory(m.id)
        print(f"  - {m.id}  {'deleted' if ok else 'FAILED'}")
    await sm.aclose()
    print("Cleanup complete.")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        asyncio.run(clean())
    else:
        asyncio.run(seed())

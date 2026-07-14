"""Smart Command Recall — explicit, user-run shell-history import (NOT a keylogger).

You run this yourself. It reads your shell history file, filters to useful commands,
skips anything that looks secret-bearing, de-duplicates, and stores the most recent ones
as real semantic memories in Supermemory Local so you can later recall
"that docker command I used".

Usage (from backend/, venv active):
    python -m scripts.import_commands              # import recent useful commands
    python -m scripts.import_commands --limit 40   # cap how many
    python -m scripts.import_commands --dry-run    # show what would be imported
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from app.models.context_event import ContextEvent
from app.memory.ingestion import ingest_event

# Commands worth remembering usually start with a real tool.
_USEFUL = re.compile(
    r"^\s*(docker|docker-compose|kubectl|git|npm|pnpm|yarn|pip|python|uvicorn|node|"
    r"make|curl|ssh|scp|terraform|aws|gcloud|az|psql|redis-cli|go|cargo|mvn|gradle)\b",
    re.IGNORECASE,
)
# Never store anything that looks like it carries a secret.
_SECRET = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|apikey|bearer|-----BEGIN|"
    r"AKIA[0-9A-Z]{16}|xox[baprs]-|ghp_[0-9A-Za-z]{20,})",
    re.IGNORECASE,
)


def history_files() -> list[Path]:
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(
            Path(appdata) / "Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt"
        )
    home = Path.home()
    candidates += [home / ".bash_history", home / ".zsh_history"]
    return [p for p in candidates if p.exists()]


def collect(limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for f in history_files():
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:  # noqa: BLE001
            continue
        for line in reversed(lines):  # most recent first
            cmd = line.strip()
            # zsh history lines look like ": 1690000000:0;actual command"
            if cmd.startswith(":") and ";" in cmd:
                cmd = cmd.split(";", 1)[1].strip()
            if not cmd or len(cmd) < 4 or len(cmd) > 200:
                continue
            if not _USEFUL.match(cmd) or _SECRET.search(cmd):
                continue
            if cmd in seen:
                continue
            seen.add(cmd)
            out.append(cmd)
            if len(out) >= limit:
                return out
    return out


async def run(limit: int, dry: bool) -> None:
    cmds = collect(limit)
    if not cmds:
        print("No useful commands found in shell history (or history file not present).")
        return
    print(f"Found {len(cmds)} useful commands{' (dry run)' if dry else ''}:")
    for cmd in cmds:
        print(f"  $ {cmd}")
        if not dry:
            await ingest_event(
                ContextEvent(source_type="terminal", content=cmd, title=cmd[:80])
            )
    if not dry:
        from app.services.supermemory_service import get_supermemory

        await get_supermemory().aclose()
        print(f"Imported {len(cmds)} commands into Supermemory Local.")


if __name__ == "__main__":
    args = sys.argv[1:]
    limit = 30
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    asyncio.run(run(limit, "--dry-run" in args))

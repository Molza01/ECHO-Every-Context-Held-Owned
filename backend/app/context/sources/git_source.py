"""Git context for a watched project directory.

ContextOS watches one project root (CONTEXTOS_WATCH_DIR, default = the ContextOS repo).
When the user is in an editor/terminal focused on that project, its live repo + branch are
attached to the current context — that is what powers 'Same repository / same branch'.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("contextos.source.git")


def watch_dir() -> Path:
    return Path(os.environ.get("CONTEXTOS_WATCH_DIR", os.getcwd())).resolve()


class GitContextSource:
    name = "git"

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or watch_dir()

    def available(self) -> bool:
        try:
            import git  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return (self.root / ".git").exists()

    def snapshot(self) -> dict[str, Optional[str]]:
        """Return {repository, branch, folder, project_name} for the watched repo."""
        result: dict[str, Optional[str]] = {
            "repository": None, "branch": None,
            "folder": str(self.root), "project_name": self.root.name,
        }
        try:
            import git

            repo = git.Repo(self.root, search_parent_directories=True)
            root = Path(repo.working_tree_dir or self.root)
            result["folder"] = str(root)
            result["project_name"] = root.name
            result["repository"] = root.name
            try:
                result["branch"] = repo.active_branch.name
            except (TypeError, Exception):  # detached HEAD, etc.
                try:
                    result["branch"] = repo.head.commit.hexsha[:8]
                except Exception:  # noqa: BLE001
                    result["branch"] = None
        except Exception as exc:  # noqa: BLE001
            log.debug("git snapshot failed for %s: %s", self.root, exc)
        return result

# ECHO Activity Capture — Gap Analysis

Inventory of every current ContextEvent producer and what it does / doesn't capture.

## Current ContextEvent producers

| Source | File | Captures | Scope |
|---|---|---|---|
| ActiveWindowSource | `sources/active_window.py` | foreground app + window title; parses editor file/project | system-wide (window title only) |
| GitContextSource | `sources/git_source.py` | repo name + branch of the watched project | **Git-specific** |
| FileContextSource | `sources/file_source.py` | most-recently-modified code file (fallback enrichment) | project dir |
| **ActivityWatcher** | `sources/activity_watcher.py` | file created/modified/renamed/moved/deleted | multi-root (files only) |
| Browser (extension) | `browser-extension/` + `/api/ingest` | page title/URL/domain, "remember this" | **browser-specific** |
| Terminal/manual | `/api/ingest`, `/api/commands/import` | explicit commands / notes | explicit |

## Gaps found (why manual activity wasn't captured)

1. **Folder events are dropped.** Every watchdog handler in `activity_watcher.py` skips
   `is_directory`, so *folder created / renamed / moved / deleted* never became events.
   → This is the #1 reason "create a folder on Desktop" did nothing.
2. **Watched roots were project-scoped at runtime.** The backend was being launched with
   `CONTEXTOS_ACTIVITY_ROOTS=d:/ContextOS`, so Desktop/Downloads/Documents activity was
   never watched. Defaults *do* include those dirs, but there was no way to see or manage
   which locations are active, and no persistence for user-added folders.
3. **No live "activity signal" stream.** Events only reached the UI *after* ingestion
   (`memory.ingested`), so raw folder/file/image events weren't visible "just now".
4. **File Explorer filtered as noise** (`_NOISE_APPS` contains `explorer`) → no
   application-context signal for File-Explorer-driven work.
5. **No watched-location management** (add/remove/pause/exclude) surfaced to the user.

## Fixes implemented

- Folder events captured (created/renamed/moved/deleted) with folder-aware phrasing.
- Persistent, user-managed **watched locations** (`backend/.contextos/watched.json`) +
  API (`/api/activity/locations` list/add/remove/pause/exclude) + Privacy-page UI. Defaults
  = Desktop, Documents, Downloads, active project.
- New **`activity.signal`** WebSocket event emitted for every meaningful raw event → live
  Activity Signals panel updates instantly, independent of ingestion.
- File Explorer allowed as an application-context signal.
- File-type-aware phrasing (Image added / PDF downloaded / folder created …).
- Everything flows through the **existing** ContextEvent → filter → dedup → session →
  Supermemory pipeline. No second activity system.

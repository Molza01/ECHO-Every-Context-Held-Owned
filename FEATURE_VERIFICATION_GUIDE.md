# ContextOS — Feature Verification Guide

How to prove each of the 10 features is **real** (backed by live Supermemory Local at
`localhost:6767`), not static UI. Every feature below was traced end-to-end with runtime
evidence.

**Services required for all features:** Supermemory Local (`:6767`), ContextOS backend
(`:8765`), ContextOS frontend (`:5173`). Start order in the README.

**Universal "is it real?" proof:** open the **Pipeline diagnostics** panel at the bottom of
the Context page (or `GET http://localhost:8765/api/diagnostics`). It shows the live
`last_query`, `last_result_count`, `last_ranked_count`, `last_ingest`, and phase — updating as
you work. Watch the backend log; every memory is a real `POST /v3/documents` and every
retrieval a real `POST /v3/search`.

---

## 1. Ambient Context Detection
- **What:** Detects your real active application, project, git repo/branch, and the file you're editing.
- **How:** `active_window` source (pywin32 foreground window + process) enriched by `git_source` (GitPython) and a `watchdog` file watcher, normalized into a `ContextEvent`, filtered, deduplicated. Polls every 2s; file saves fire immediately.
- **Test:** Switch between VS Code, a terminal, and a browser. Save a source file in the watched project.
- **Expected UI:** The **Current Context** card updates automatically (no refresh) with app/project/branch/file, each tagged `DETECTED` or `INFERRED`. A "detected Xs ago" timestamp appears.
- **Prove it's real:** Backend log prints `[context.updated] active_window|VS Code|<repo>|<branch>|<file>`; the values match your actual window. Diagnostics `last_event` mirrors it.
- **Diagnostics/logs:** `last_filter`, `last_dedup` show the meaningful/significant decisions.
- **Common failure & fix:** File shows blank → editor title has no filename; the file watcher still supplies it on the next save, or it shows as `INFERRED` from the recent-file scan.

## 2. Context-Aware Ambient Panel
- **What:** Surfaces relevant past memories automatically on every context change — no Search button.
- **How:** On a significant change the engine emits `context.updated` → `retrieval.started` → runs a real Supermemory search → `ambient.memory_found`/`retrieval.completed` over WebSocket.
- **Test:** With demo data seeded (below), edit `auth.ts` or open an auth-related page.
- **Expected UI:** The lifecycle bar animates **Detected → Checking local memory → Surfaced**, then memory cards appear with confidence + reasons. If nothing matches: *"No relevant past context found."*
- **Prove it's real:** Network tab shows `/ws` frames with types `retrieval.started`/`ambient.memory_found`. Kill the backend and the panel stops updating (no fake timers).
- **Common failure & fix:** Panel stuck on "Checking" → Supermemory unreachable; sidebar dot turns amber. Restart Supermemory.

## 3. Universal Memory Layer
- **What:** Browser, editor, git, files, terminal, and manual notes all become one searchable memory.
- **How:** Every source funnels through `ingest_event` → `POST /v3/documents` with one container tag `contextos:user:<id>`.
- **Test:** Create memories from 3 sources: edit a file, use the browser extension "Remember this page", run `scripts/import_commands`.
- **Expected UI:** All appear together on the **Memories** page with distinct source badges.
- **Prove it's real:** `GET /api/memories` returns them with real `createdAt` + metadata `source_type`; `curl` the Supermemory list directly and see the same IDs.
- **Common failure & fix:** A source's memories missing → that source toggle is off in Privacy, or (browser) the extension isn't loaded.

## 4. Local Semantic Search
- **What:** Manual meaning-based search (a supporting feature).
- **How:** `POST /api/search` → `SupermemoryService.search` → `POST /v3/search` with `containerTags` + low `chunkThreshold`.
- **Test:** Search "how did I solve the token timeout" (no exact keywords from stored text).
- **Expected UI:** The JWT fix ranks top with its real `score`.
- **Prove it's real:** Result cards show the Supermemory `score`; a paraphrase with zero shared keywords still matches (semantic, not substring).
- **Common failure & fix:** 0 results → container empty (seed demo data) or Supermemory offline.

## 5. Timeline Mode
- **What:** Chronological view of real memories grouped by day.
- **How:** `GET /api/timeline` → `POST /v3/documents/list` sorted by real `createdAt`.
- **Test:** Open **Timeline** after generating activity.
- **Expected UI:** Day groups (Today/Yesterday/…) with real timestamps and source badges.
- **Prove it's real:** Timestamps match when you actually did the work; there are no placeholder events. Delete a memory and it disappears from the timeline.
- **Common failure & fix:** Empty → no memories yet; seed or work a bit.

## 6. Smart Command Recall
- **What:** Recall useful terminal commands semantically.
- **How:** Explicit import only — `scripts/import_commands.py` reads your shell history, filters to real tools, **skips anything secret-bearing**, stores as `terminal` memories. Also `POST /api/commands/import`.
- **Test:** `python -m scripts.import_commands --dry-run` then without `--dry-run`; search "docker".
- **Expected UI:** Your real docker/git/npm commands appear in Search/Memories.
- **Prove it's real:** Dry-run prints commands pulled from your actual `ConsoleHost_history.txt`/`.bash_history`; secret-looking lines are excluded.
- **Common failure & fix:** "No useful commands" → history file empty or only non-tool commands.

## 7. Related Memory Suggestions
- **What:** Given the current file/context, suggest related memories.
- **How:** `POST /api/related` builds a query from real context → Supermemory search → ranking. No hardcoded relationships.
- **Test:** `curl -X POST /api/related -d '{"file_path":"auth.ts","repository":"ContextOS"}'`.
- **Expected result:** JWT/auth memories ranked with `why` reasons.
- **Prove it's real:** Change the file to `graph.py` and the suggestions change accordingly.

## 8. Memory Graph
- **What:** Visual graph of how memories connect.
- **How:** `GET /api/graph` builds nodes from **real memories**; edges use defensible signals (same file/domain/project/repo + temporal proximity), degree-capped for readability. No native graph endpoint is faked.
- **Test:** Open **Memory Graph**; hover nodes.
- **Expected UI:** Real memory labels; hovering shows repo/file/domain; edges reflect shared signals.
- **Prove it's real:** Node count tracks your memory count; delete memories and the graph shrinks. Edge `signals` are inspectable in `GET /api/graph`.

## 9. Privacy Dashboard
- **What:** Shows local-only guarantees, real source/Supermemory status, working toggles, real export.
- **How:** Status from `/api/status`; toggles call `/api/sources/toggle` which actually flips `engine.enabled[...]` (a disabled source stops being sampled/ingested); export streams `/api/export` from real Supermemory data.
- **Test:** Toggle **Files** off, save a file — no new file memory appears. Toggle on — it resumes. Click **Export JSON**.
- **Prove it's real:** After disabling a source, diagnostics `last_ingest` shows it's skipped; the exported JSON contains your real memory IDs.

## 10. Memory Confidence & Explanation
- **What:** Every surfaced memory shows a deterministic ContextOS Context Confidence and why it appeared.
- **How:** `memory/confidence.py` — weighted composite of the **real** Supermemory `score` plus same-repo/file/project/domain and recency; recently-surfaced penalty. Documented weights; never a fabricated similarity score.
- **Test:** Edit `auth.ts` with demo data seeded.
- **Expected UI:** e.g. **75–85%** with reasons *Same repository · Same file · Semantically retrieved by Supermemory*.
- **Prove it's real:** The `semantic_score` shown is exactly Supermemory's returned value; changing context changes the score and reasons deterministically.

---

## Seeding demo history (so proactive retrieval has something to find)
```bash
cd backend
python -m scripts.seed_demo          # adds 8 realistic memories via the REAL Supermemory service
python -m scripts.seed_demo --clean  # removes only seeded demo memories (metadata.seed=true)
```
Seeded memories are **not** injected into React state — they enter Supermemory Local, get
indexed, and surface through the normal search → rank → ambient pipeline.

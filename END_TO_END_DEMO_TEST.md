# ContextOS — End-to-End Demo Test (5–10 minutes)

One exact scenario that proves the full real flow:

real context detection → real ingestion → real Supermemory storage → context switching →
automatic semantic search → historical retrieval → ranking → Context Confidence →
Why This Appeared → live frontend update — **with no manual search**.

Keep two things visible: the **browser** on the ContextOS Context page, and a **terminal
tailing the backend log** (or the Pipeline diagnostics panel open).

---

## Setup (once)

```bash
# 1. Supermemory Local already running at http://localhost:6767
# 2. Backend
cd backend && .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
# 3. Frontend (new terminal)
cd frontend && npm run dev            # http://localhost:5173
# 4. Seed realistic history through the REAL Supermemory service
cd backend && .venv/Scripts/python -m scripts.seed_demo
```
Open http://localhost:5173. Confirm the sidebar shows **Supermemory · Local :6767** (green)
and **live stream connected**.

---

## STEP 1 — Baseline: prove memory is real, not seeded into the UI
- **ACTION:** Open the **Memories** page, then the **Timeline** page.
- **EXPECTED UI:** 8 seeded memories (JWT fix, OAuth docs, docker command, CORS, auth middleware, branch switch, refresh-token note) with source badges and real timestamps grouped under Today.
- **EXPECTED BACKEND:** none (reads only).
- **DIAGNOSTIC PROOF:** `curl http://localhost:6767/v3/documents/list -X POST -H "Content-Type: application/json" -d '{"containerTags":["<your container>"],"limit":20}'` returns the same IDs. Get `<your container>` from `GET /api/status` → `user_container`. This proves the memories live in Supermemory, not React.

## STEP 2 — Real context detection
- **ACTION:** Switch to your editor and open the ContextOS project. Then switch back to the browser Context page.
- **EXPECTED UI:** **Current Context** auto-updates: Application = VS Code (DETECTED), Project/Repository = ContextOS (INFERRED), Branch (INFERRED). A "detected Ns ago" appears. No page refresh.
- **EXPECTED BACKEND:** `[context.updated] active_window|VS Code|ContextOS|<branch>|...` then `[retrieval.started] query=...`.
- **DIAGNOSTIC PROOF:** Diagnostics panel `last_event` = active_window with your real values; `Filter = meaningful ✓`, `Dedup = significant change ✓`.

## STEP 3 — A file save becomes a real memory (retrieve-before-ingest)
- **ACTION:** Edit and **save** a real source file, e.g. `backend/app/memory/ranking.py`.
- **EXPECTED UI:** Lifecycle bar runs **Detected → Checking local memory → Surfaced/None**. At the bottom: *Last remembered: "Editing backend/app/memory/ranking.py in the ContextOS project."*
- **EXPECTED BACKEND:** `[context.updated] file|File watcher|...|ranking.py` → `[retrieval.started]` → `[retrieval.completed]` → **then** `[memory.ingested] <id> (file)`. Note the order: retrieval happens **before** ingest, so the file never surfaces itself.
- **DIAGNOSTIC PROOF:** Diagnostics `last_ingest` = `stored (file modified)`; `last_query` mentions ranking.py. `POST http://localhost:6767/v3/search` for "ranking implementation" now returns this memory.

## STEP 4 — THE AHA MOMENT: switch to related context, memory finds you
- **ACTION:** Open (or focus) a file named `auth.ts` in the project — or run:
  `curl -X POST http://localhost:8765/api/related -H "Content-Type: application/json" -d '{"file_path":"auth.ts","project_name":"ContextOS","repository":"ContextOS","query":"working on auth.ts authentication token handling"}'`
- **EXPECTED UI:** Ambient panel shows **CONTEXT FOUND** with the top card:
  *"Fixed JWT expiration by changing refresh token handling in auth.ts…"*
  **Context Confidence ≈ 75–85%**, Source = Saved/Manual, Memory age, and
  **WHY THIS APPEARED:** Same repository · Same file (auth.ts) · Same project · Semantically retrieved by Supermemory.
- **EXPECTED BACKEND:** `[ambient.memory_found] N surfaced (top=<id>)`.
- **DIAGNOSTIC PROOF:** The card's `semantic 0.7x` equals Supermemory's returned `results[].score` for that query — run the same `POST /v3/search` and compare. You never clicked Search.

## STEP 5 — Prove semantic (not keyword) retrieval
- **ACTION:** Go to the **Search** page and search: *"where did I resolve the login session expiring problem"* (no words shared with the stored memory).
- **EXPECTED UI:** The JWT fix still returns near the top.
- **DIAGNOSTIC PROOF:** Zero shared keywords + a match ⇒ real embeddings/semantic search, not substring.

## STEP 6 — Live WebSocket update (no polling, no fake timers)
- **ACTION:** Keep the Context page open. In a terminal:
  `curl -X POST http://localhost:8765/api/ingest -H "Content-Type: application/json" -d '{"source_type":"browser","title":"JWT access token expiry and refresh explained","url":"https://jwt.io/introduction","domain":"jwt.io","set_current":true}'`
- **EXPECTED UI:** Within ~1s, Current Context switches to the browser page and the ambient panel re-runs the lifecycle and surfaces JWT memories — **live**, without refresh.
- **DIAGNOSTIC PROOF:** Browser devtools `/ws` frames: `context.updated` → `retrieval.started` → `ambient.memory_found`. Stop the backend and the UI stops updating — nothing is simulated client-side.

## STEP 7 — Confidence + explanation are deterministic
- **ACTION:** Repeat STEP 4 twice.
- **EXPECTED UI:** Same inputs → same Context Confidence and same reasons. A recently-surfaced card's confidence drops slightly on immediate re-surface (recently-surfaced penalty), then recovers — visible, explainable behavior.
- **DIAGNOSTIC PROOF:** `memory/confidence.py` weights are fixed; the score is reproducible.

## STEP 8 — Privacy controls actually control monitoring
- **ACTION:** Privacy page → toggle **Files** off → save a source file.
- **EXPECTED UI/BACKEND:** No new file memory; diagnostics `last_ingest` shows skipped. Toggle on → saving resumes creating memories.
- **DIAGNOSTIC PROOF:** `GET /api/diagnostics` `sources.file.enabled=false` while off.

---

## Teardown / reset
```bash
cd backend && .venv/Scripts/python -m scripts.seed_demo --clean   # remove seeded demo memories
```
Organic memories created during the test remain (they're real). Delete any individually from
the Memories page (real `DELETE /v3/documents/{id}`).

---

### The one-sentence result
> "I switched what I was actually doing, and a relevant past memory appeared with a real
> confidence score and a real explanation — I never searched for it."

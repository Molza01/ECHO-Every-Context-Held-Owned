# Supermemory Local — Verified Integration Note

> Source of truth: live inspection of `http://localhost:6767/v4/openapi` + a real
> create → process → semantic-search → delete smoke test executed on 2026-07-12.
> This is **verified behavior**, not assumptions. ContextOS is built against exactly this.

## Base URL & Auth
- **Base URL:** `http://localhost:6767`
- **Health:** `GET /v3/health` → `{"status":"ok"}`
- **Auth:** None required for the local server. The OpenAPI spec declares a `bearerAuth`
  scheme, but the local instance does not enforce it. ContextOS sends no Authorization
  header by default; if `SUPERMEMORY_API_KEY` is set it is attached as `Bearer` (forward-compat).

## Core operations used by ContextOS

### Add memory — `POST /v3/documents`
Request (JSON):
- `content` (string, **required**) — the semantic text to store.
- `containerTag` (string) or `containerTags` (string[]) — isolation scope.
- `metadata` (object) — arbitrary; **round-trips fully** and comes back on search results.
- `customId`, `taskType` ("memory" default), `dreaming` ("dynamic" default).

Response: `{"id": "<docId>", "status": "queued"}`

### Processing / indexing
- Asynchronous but **fast** (sub-second in local testing).
- Poll `GET /v3/documents/{id}` → `status` and `dreamingStatus` reach `done`.
- ContextOS ingestion is fire-and-forget; retrieval tolerates eventual consistency.

### Semantic search — `POST /v3/search`
**Two hard-won requirements (both verified):**
1. **Must pass `containerTags`.** A search with *no* container tag hits an empty default
   scope and returns `total: 0`, even when matching docs exist.
2. **Must pass a low `chunkThreshold`.** The default threshold filters out perfectly valid
   semantic matches (a 0.706-scoring paraphrase returned 0 results at default). ContextOS
   sends `chunkThreshold` low and applies its **own** score threshold in the ranking layer.

Request: `{ "q", "containerTags", "limit", "chunkThreshold", "rerank" }`

Response:
```json
{
  "total": 1,
  "timing": 77,
  "results": [{
    "documentId": "r2pY8...",
    "score": 0.706,                // REAL relevance score, 0..1
    "title": "...",
    "metadata": { "source_type": "...", "project": "...", "file": "..." },
    "createdAt": "2026-07-12T08:09:45.088Z",
    "updatedAt": "...",
    "type": "text",
    "chunks": [{ "content": "...", "score": 0.709, "isRelevant": true, "position": 0 }]
  }]
}
```
> **`results[].score` is a real, usable relevance score.** ContextOS does NOT fabricate
> similarity. Semantic quality confirmed: query *"where did I resolve the login session
> expiring problem"* retrieved a doc about *"Fixed JWT expiration... refresh token"* — zero
> shared keywords — at score **0.706**.

### List memories (Timeline) — `POST /v3/documents/list`
Request: `{ "containerTags", "includeContent", "limit", "page", "sort":"createdAt", "order":"desc" }`
Response: `{ "memories": [...], "pagination": {...} }`. Each memory carries `id`, `title`,
`status`, `containerTags`, `metadata`, `createdAt`.

### Delete memory — `DELETE /v3/documents/{id}`
Returns `204`. Verified: after delete the container list is empty. Real deletion — no faking.

## Container-tag strategy
- Isolation scope: `contextos:user:<local-user-id>` (single reusable util, see
  `backend/app/core/container.py`). One persistent local user id is generated on first run.
- Every add + every search + every list passes this tag → the user's memory is a private,
  isolated brain.

## Metadata schema ContextOS writes
`source_type, application, project_name, repository, branch, file_path, folder, url, domain, title, timestamp` — all optional, all round-trip.

## Limitations discovered
- No native graph endpoint → ContextOS builds the memory graph itself from real retrieved
  memories using transparent signals (same project/repo/file/domain, temporal proximity,
  semantic co-retrieval).
- No relevance score on `documents/list` (only `search` returns `score`) → Timeline uses
  chronological ordering, proactive surfacing uses search scores.
- `chunkThreshold` semantics: **lower = more results**. ContextOS filters by `score` afterward.

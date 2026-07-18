<div align="center">

# ECHO

### Every Context, Held & Owned

**Pick up exactly where you left off.**

*Your computer creates context all day. ECHO remembers what matters — and carries it to any AI you use.*

`local-first` · `privacy-first` · `powered by Supermemory`

</div>

---

## 🔗 Live demo

- **App:** https://echo-every-context-held-owned.vercel.app

The live link is a **hosted showcase** (Vercel UI → Render backend → Supermemory Cloud) with
sample data — so you can click and use Ask, Search, Memories, Timeline, Graph, and the Context
Passport. Automatic activity capture ("ECHO watches what you do") only runs when the backend is
on **your** machine — see the local setup below. Full options in **[DEPLOYMENT.md](DEPLOYMENT.md)**.

> Note: the hosted backend is on Render's free tier and sleeps when idle — the first click may
> take ~30s to wake (the UI shows a "Waking up ECHO" panel meanwhile).

---

## What is ECHO?

ECHO is a **user-owned context layer for your computer**.

It quietly understands the meaningful things you do — the file you created, the branch you switched to, the docs you researched, the app you're in — turns them into **semantic memory stored locally in [Supermemory](https://supermemory.ai)**, and then **proactively surfaces the right memory at the right moment**, without you ever searching.

Then it does the thing no chat app does: it **hands that context to your AI tools**. Hit a limit in Claude Code and switch to ChatGPT? Your context goes with you.

> **The core principle:** context belongs to the **user**, not to an application, an AI account, or a chat session.

### The problem

Your work is scattered across VS Code, a browser, a terminal, File Explorer, and three AI assistants. Every one of them has its own island of context:

- You re-explain your project to an AI **every single session**
- You hunt for a command you definitely ran last week
- Yesterday's decisions are buried in a chat log
- Research and implementation live in different universes
- Switching tasks means rebuilding context from scratch

Today's computers know **what is open**. They don't understand **what matters**.

### The aha moment

```
You open auth.ts
        ↓
ECHO (unprompted): "You previously fixed JWT expiration by changing refresh token handling."
                    Context Confidence: 78%
                    Why: Same repository · Same file · Semantically retrieved by Supermemory
```

**You never searched. ECHO already knew you needed it.**

---

## 🧠 How ECHO uses Supermemory Local

Supermemory isn't a storage bucket bolted onto the side — **it is the brain**. Remove it and ECHO has no memory, no understanding, and no product.

Every meaningful signal becomes a memory in Supermemory. Every question, every surfaced card, every session, every passport is a **real Supermemory query**.

| ECHO capability | The actual Supermemory call |
|---|---|
| Activity capture | `POST /v3/documents` — each meaningful event becomes semantic memory |
| Ambient retrieval | `POST /v3/search` — real semantic search + **real relevance scores** |
| Ask ECHO | `POST /v3/search` — answers grounded strictly in retrieved memories |
| Timeline / Sessions / Analytics / Profile | `POST /v3/documents/list` |
| Pin · Important · Note · Edit | `PATCH /v3/documents/{id}` (metadata merges, verified) |
| Forget | `DELETE /v3/documents/{id}` |
| Live status | `GET /v3/health` |

**Everything is local:** storage, embeddings (`Xenova/bge-base-en-v1.5`, 768d, on-device), and retrieval all run on **your machine** at `localhost:6767`. Nothing is sent to a cloud memory service.

Memory is isolated per user with a single container tag: `contextos:user:<local-id>`.

**Proven, not claimed** — stored *"Fixed JWT expiration by changing refresh token handling"*, then searched *"where did I resolve the login session expiring problem"* (**zero shared keywords**) → retrieved at **score 0.706**. That's real embeddings, not string matching. Full verified API notes: [`docs/SUPERMEMORY_INTEGRATION.md`](docs/SUPERMEMORY_INTEGRATION.md).

---

## ✨ Features

### 1. Ambient context detection
Knows your active app, project, git repo, branch and current file — no tagging, no setup. Values are honestly labelled **DETECTED** vs **INFERRED**, so you always know what's real.

### 2. System-wide activity capture
Not just VS Code. ECHO understands your **whole computer**:
`created` · `modified` · `renamed` · `moved` · `deleted` — for **files and folders**, across Desktop / Documents / Downloads / your projects, with file-type awareness (code, docs, PDFs, images, spreadsheets, presentations).

> *"Created folder ECHO Test in Desktop"* · *"Image architecture.png was added to ECHO Test"* · *"Downloaded the PDF to Downloads"*

### 3. Proactive memory surfacing — the core loop
On every significant context change: build a semantic query → search Supermemory → rank → surface. **No search button.**

### 4. Ask ECHO
Chat with your own computer memory: *"What did I work on today?"* · *"What was the JWT issue I fixed?"*
Time-aware (`today`, `yesterday`, `this week`, `around 3pm`), supports follow-ups, shows **evidence**, and says *"I don't have memories about that"* when it doesn't. **Grounded in retrieval — it cannot hallucinate activity.**

### 5. Context Passport 🛂
**The signature feature.** A portable snapshot of your work state — goal, project, branch, current task, recent work, decisions, blockers, related context, suggested next action.

**Copy Passport** → paste into ChatGPT/Claude/any AI → it instantly knows where you left off. Export **Markdown/JSON**. Correct the goal/task or add decisions/blockers — **your corrections persist and override the derived values**.

### 6. MCP server 🔌
Exposes that same context to **Claude Code, Cursor**, and any MCP client — 10 tools:
`get_context_passport` · `get_current_context` · `search_user_memory` · `get_active_session` · `get_project_context` · `get_recent_activity` · `get_recent_decisions` · `get_current_blockers` · `get_related_memories` · `get_recent_files`

*"Load my context passport and continue where I left off"* — no re-explaining.

### 7. Context Sessions
Related activity across apps grouped into resumable work sessions (deterministic: project + temporal gaps). Rename, pin, resume — resume generates what you were doing, relevant files, decisions, blockers, and a next action.

### 8. Interactive memories
**Pin** · **Mark important** · **Add a note** · **Edit** · **Mark irrelevant** · **Forget** — all real `PATCH`/`DELETE` operations against Supermemory. Ranking respects them: pinned/important get boosted, irrelevant are never surfaced.

### 9. Activity history & analytics
Full searchable history (filter by Folders/Files/Images/Browser/Apps/Git/Terminal/Notes, date ranges), plus **Day/Week/Month analytics**: where your attention went, activity per day, focus by hour, top projects, peak hour. Reveal any file in your file manager.

### 10. Memory Graph
Real memories connected by **defensible signals** — same file, domain, project, repo, temporal proximity. No invented relationships (Supermemory has no graph endpoint; ECHO builds it transparently).

### 11. Timeline & semantic search
Chronological story of your work from real timestamps, plus meaning-based search (not keywords).

### 12. Context Confidence & "Why this appeared"
Every surfaced memory shows a **deterministic, explainable** score:

```
Context Confidence = 0.50 × Supermemory's real semantic score
                   + 0.18 same file  + 0.16 same repo
                   + 0.10 same domain + 0.08 same project + 0.05 recent
                   (− penalty if surfaced very recently)
```
**Supermemory scores are never fabricated.** The composite is clearly labelled as ECHO's own.

### 13. Privacy dashboard
Manage **watched locations** (add/remove/pause/exclude), toggle sources, export all memories, and see live proof that storage + retrieval are local.

### 14. Browser extension
Chromium MV3: page title/URL/domain on navigation, explicit **"Remember this"**, and an ambient side panel.

---

## 🔒 Privacy

ECHO is **conservative by design**:

| ECHO does | ECHO never does |
|---|---|
| Reads window **titles** and file **paths** | ❌ Log keystrokes |
| Records **actions** (created/renamed/moved) | ❌ Read file contents |
| Captures pages **you** browse (with the extension) | ❌ Capture passwords or form fields |
| Stores only **meaningful** events | ❌ Silently grab selected text/clipboard |
| Keeps everything **on your machine** | ❌ Send your history to any cloud |

**Secrets are redacted *before* anything reaches Supermemory** — verified: a token-bearing memory is stored as `token=[redacted] and api_key=[redacted]`. Noise is filtered (bare window focus is never stored), and everything is deduplicated and debounced.

---

## 🏗 Architecture

```
   Files · Folders · Apps · Git · Browser · Terminal        ← your real activity
                        │
                        ▼
      ┌──────────────────────────────────────┐
      │  Context Sources (window/git/watcher)│
      │  Privacy redaction → noise filter    │
      │  → dedup → normalize                 │
      └──────────────────────────────────────┘
                        │  ContextEvent
                        ▼
      ┌──────────────────────────────────────┐
      │        Ambient Engine                │
      │  1. detect significant change        │
      │  2. RETRIEVE first (never self-echo) │
      │  3. rank + confidence + "why"        │
      │  4. THEN ingest as memory            │
      └──────────────────────────────────────┘
              │                    │
              ▼                    ▼
   ┌────────────────────┐   ┌──────────────────┐
   │ Supermemory Local  │   │ WebSocket        │
   │ :6767 · on-device  │   │ live lifecycle   │
   │ THE MEMORY ENGINE  │   └──────────────────┘
   └────────────────────┘            │
              │                      ▼
              ├──────────► React UI (Now · Activity · Analytics · Passport ·
              │            Sessions · Memories · Timeline · Graph · Privacy)
              │
              └──────────► Context Passport ──► Claude · Cursor (MCP)
                                             └► ChatGPT & others (Copy Passport)
```

**Retrieve-before-ingest** is deliberate: ECHO searches for *past* memories **before** storing the current context, so it can never surface the thing you just did as a "memory".

### Live lifecycle (WebSocket)
`context.updated` → `retrieval.started` → `ambient.memory_found` / `retrieval.completed` → `memory.ingested`
plus `activity.signal`, `proactive.suggestion`, `source.status_changed`, `supermemory.status_changed`.

The UI shows the real state: **Detected → Checking local memory → Surfaced** (or an honest *"No relevant past context found"*).

---

## 🛠 Tech stack

| Layer | Technology |
|---|---|
| **Memory engine** | **Supermemory Local** (`:6767`) — on-device embeddings `Xenova/bge-base-en-v1.5` (768d), encrypted local storage |
| **Backend** | Python 3.11+ · FastAPI · Uvicorn · Pydantic v2 · httpx · WebSockets |
| **Capture** | watchdog (filesystem) · pywin32 (active window) · GitPython (repo/branch) · psutil |
| **Frontend** | React 18 · Vite 6 · TypeScript 5.7 · Tailwind CSS 3 · framer-motion · zustand · react-router · lucide-react |
| **AI integration** | Model Context Protocol (`mcp` Python SDK, stdio) |
| **Extension** | Chromium MV3 (vanilla JS, no build step) |

No database. **No second vector store.** Supermemory *is* the persistence layer; only tiny local state (user id, session/passport overrides, watched locations) lives in `backend/.contextos/` as JSON.

---

## 🚀 Setup

### Prerequisites
- **Git** · **Python 3.11+** · **Node 18+**
- **Supermemory** — run it locally *or* use Supermemory Cloud (step 1).

### 0. Clone this repo
```bash
git clone https://github.com/TusharKale10/ECHO-Every-Context-Held-Owned.git
cd ECHO-Every-Context-Held-Owned
```

### 1. Get Supermemory running (the memory engine ECHO needs)
**Option A — Supermemory Local** *(recommended, fully private).* If you don't have it yet,
install & start it from the official quickstart →
[supermemory.ai/docs/self-hosting/quickstart](https://supermemory.ai/docs/self-hosting/quickstart).
It should serve `http://localhost:6767`.
Verify: `curl http://localhost:6767/v3/health` → `{"status":"ok"}`.

**Option B — Supermemory Cloud** *(no local install).* Create an API key at
[supermemory.ai](https://supermemory.ai), then in `backend/.env` (step 2) set
`SUPERMEMORY_BASE_URL=https://api.supermemory.ai` and `SUPERMEMORY_API_KEY=sm_...`.

> Not installed yet? ECHO also shows an in-app **"Connect to Supermemory"** guide on the home
> screen when it can't reach Supermemory, and the sidebar dot is **red** (offline) / **green**
> (connected).

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install --only-binary=:all: -r requirements.txt   # macOS/Linux: .venv/bin/pip
cp ../.env.example .env                                             # defaults work as-is
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

### 4. Seed demo history *(optional — gives proactive retrieval something to find)*
```bash
cd backend
.venv\Scripts\python -m scripts.seed_demo          # real memories via the real Supermemory service
.venv\Scripts\python -m scripts.seed_demo --clean  # remove them
```

### 5. Browser extension *(optional)*
`chrome://extensions` → **Developer mode** → **Load unpacked** → select `browser-extension/`

### 6. MCP — give your context to Claude Code / Cursor *(optional)*
```bash
claude mcp add echo -- <abs-path>/backend/.venv/Scripts/python.exe <abs-path>/mcp-server/contextos_mcp.py
```
Details: [`mcp-server/README.md`](mcp-server/README.md)

### Configuration (`backend/.env`)
| Variable | Default | Purpose |
|---|---|---|
| `SUPERMEMORY_BASE_URL` | `http://localhost:6767` | Supermemory Local, or `https://api.supermemory.ai` for cloud |
| `SUPERMEMORY_API_KEY` | *(blank)* | required only for Supermemory Cloud |
| `CONTEXTOS_USER_ID` | auto-generated | container tag identity |
| `CONTEXTOS_WATCH_DIR` | cwd | project tracked for git/branch |
| `CONTEXTOS_ACTIVITY_ROOTS` | Desktop/Documents/Downloads/project | folders to watch |
| `CONTEXTOS_SURFACE_THRESHOLD` | `0.42` | min semantic score to surface |

**Never commit `.env`.** Manage watched folders in the UI: **Privacy → Watched Locations**.

---

## 🧪 Try it in 60 seconds

1. Open **http://localhost:5173** → sidebar shows **Supermemory · Local :6767** (green).
2. Create a folder on your **Desktop**, drop a file in it → it appears in **Activity Signals within ~2s**.
3. Ask ECHO: *"what did I create today?"* → grounded answer **with evidence**.
4. Open **Context Passport** → **Copy Passport** → paste into any AI. It knows where you left off.

Verification guides: [`FEATURE_VERIFICATION_GUIDE.md`](FEATURE_VERIFICATION_GUIDE.md) · [`END_TO_END_DEMO_TEST.md`](END_TO_END_DEMO_TEST.md)

---

## 📁 Project structure

```
ECHO/
├── backend/                 FastAPI — the ambient engine
│   ├── app/
│   │   ├── context/         sources (window/git/activity watcher), filters, dedup, engine
│   │   ├── memory/          ingestion, retrieval, ranking, confidence, ask, passport,
│   │   │                    sessions, analytics, graph, derive, profile
│   │   ├── services/        supermemory_service.py  ← the ONLY Supermemory client
│   │   ├── core/            config, container tag, privacy redaction
│   │   └── api/             routes + WebSocket
│   └── scripts/             seed_demo.py, import_commands.py
├── frontend/                React + Vite + TS + Tailwind
├── mcp-server/              MCP server (context → Claude Code / Cursor)
├── browser-extension/       Chromium MV3
└── docs/                    verified Supermemory integration + gap analysis
```

All Supermemory access is funnelled through **one** service — no scattered HTTP calls.

---

<div align="center">

**Your activity creates a signal. ECHO carries the context forward.**

*Applications change. User context continues.*

</div>

# Deploying ECHO

ECHO has two parts: a **frontend** (static React app) and a **backend** (FastAPI) that talks
to **Supermemory** (Local on your machine, or Supermemory Cloud). Pick the setup that fits.

| # | Setup | Public link judges can click? | Auto activity capture? | Memory location |
|---|---|---|---|---|
| **1** | Fully local | no | ✅ | your machine |
| **2** | **Vercel + Render + Supermemory Cloud** ⭐ | ✅ always-on | ❌ (cloud can't watch a PC) | Supermemory Cloud |
| **3** | Vercel + your local backend (tunnel) | ✅ while your PC is on | ✅ | your machine |

> **Why no auto-capture on a hosted link:** ECHO's file/window watcher runs *where the backend
> runs*. A cloud server can't see a visitor's computer — that's an OS/browser boundary. Auto
> capture only works when the backend runs on that person's machine (Setups 1 & 3).

---

## Setup 2 — Live link for demos/hackathons ⭐ (Vercel + Render + Supermemory Cloud)

A clickable, always-on URL. Memory is managed in the cloud; fill it via seeding, the
"Remember" box, or the browser extension.

### A. Supermemory Cloud key
1. Sign up at **supermemory.ai** → dashboard → **create an API key** (`sm_...`). Keep it secret.

### B. Backend → Render
1. **render.com → New → Blueprint** → pick this repo (it reads `render.yaml`).
2. Set env vars on the service:
   | Key | Value |
   |---|---|
   | `SUPERMEMORY_BASE_URL` | `https://api.supermemory.ai` |
   | `SUPERMEMORY_API_KEY` | *your `sm_...` key* (secret) |
   | `CONTEXTOS_USER_ID` | `hackathon-demo` |
   | `PYTHON_VERSION` | `3.12.6` |
   | `FRONTEND_URL` | *(optional — only for a custom domain; `*.vercel.app` is auto-allowed)* |
3. Deploy → copy the URL, e.g. `https://echo-backend-xxxx.onrender.com`.
   Test: open `<url>/api/status` → `"reachable": true`, `"mode": "cloud"`.

### C. Frontend → Vercel
1. **vercel.com → Add New → Project** → import the repo.
2. **Root Directory:** `frontend`.
3. Env var: `VITE_API_URL = https://echo-backend-xxxx.onrender.com` (your Render URL). Scope
   **Production and Preview**. (Do **not** import `backend/.env` — that has your secret key.)
4. Deploy → your live link `https://<app>.vercel.app`.

### D. Seed demo data (so it isn't empty)
The cloud memory starts empty. Either:
- **Type memories** into the "Remember something" box on the Memories page (saves to cloud), or
- **Run the seeder** locally, pointed at the same cloud + id:
  ```bash
  cd backend            # .env: SUPERMEMORY_BASE_URL=https://api.supermemory.ai,
                        #       SUPERMEMORY_API_KEY=sm_..., CONTEXTOS_USER_ID=hackathon-demo
  .venv/Scripts/python -m scripts.seed_demo     # --clean removes them later
  ```
  `CONTEXTOS_USER_ID` **must match** Render, or the live site won't see the seeds.

### E. Notes
- **Render free tier sleeps after ~15 min idle** — the first click can take 30–60s to wake. Open
  it once before judging. (The UI shows a "Waking up ECHO" panel while it wakes.)
- **One shared memory:** everyone who opens the link reads the same `hackathon-demo` container,
  so it's a **shared showcase**, not per-user. For per-user data see "Per-user" below.
- 🔐 **Never expose your API key** — it lives only in Render env + `backend/.env` (gitignored).
  If it leaks, rotate it in the Supermemory dashboard and update both places.

---

## Setup 1 — Fully local (real product, max privacy)

1. Start **Supermemory Local** (serves `localhost:6767`) — or use Supermemory Cloud by setting
   `SUPERMEMORY_BASE_URL`/`SUPERMEMORY_API_KEY` in `backend/.env`.
2. Start the backend: double-click **`start.bat`**, or:
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
   ```
3. Start the frontend: `cd frontend && npm install && npm run dev` → open `http://localhost:5173`.
   Full features including automatic activity capture.

---

## Setup 3 — Vercel UI + your local backend (public link, full features, while your PC is on)

1. Run backend + Supermemory locally (Setup 1).
2. Expose the backend: `cloudflared tunnel --url http://localhost:8765` → public `https://xxx.trycloudflare.com`.
3. On Vercel set `VITE_API_URL` = that tunnel URL → redeploy.
   The link now drives *your* real ECHO (auto-capture included) — but only while your PC + tunnel are on.

---

## Per-user data ("each visitor sees their own")

The hosted link (Setup 2) is a **single shared memory** by design. To give each visitor their
own data you must either:
- **Run locally per user** (Setup 1/3): each person runs their own backend → their own memory +
  auto-capture. This is the real product model.
- **Add multi-user auth** to the backend (per-user container tags): a larger feature — turns the
  hosted link into a multi-tenant cloud app, but still **without** auto OS capture.

---

## Backend env reference (`backend/.env`, gitignored)
| Var | Default | Notes |
|---|---|---|
| `SUPERMEMORY_BASE_URL` | `http://localhost:6767` | set to `https://api.supermemory.ai` for cloud |
| `SUPERMEMORY_API_KEY` | *(blank)* | required for cloud |
| `CONTEXTOS_USER_ID` | *(auto)* | fixed value to share a container across machines |
| `FRONTEND_URL` | `http://localhost:5173` | extra CORS origin (custom domains); `*.vercel.app` auto-allowed |
| `CONTEXTOS_WATCH_DIR` | cwd | project root for git/branch + file watching |

## Frontend env (Vercel)
| Var | Notes |
|---|---|
| `VITE_API_URL` | backend origin. Unset → dev proxy (local) / visitor's `localhost:8765` (prod build). Set → that backend (Render/tunnel). |

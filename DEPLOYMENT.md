# Deploying ECHO

ECHO is **local-first**. The trick to deploying it:

> **Host the UI on Vercel. Each user runs the backend + Supermemory on their own machine.**
> The Vercel page runs in the visitor's browser, so it talks to *their own* `http://localhost:8765`.

Result:
- A visitor **without** the local backend/Supermemory → sees the **"Supermemory offline / Connect"** panel; the app still loads and navigates, memory features show empty states.
- A visitor **with** the backend + Supermemory running locally → **every feature works**, including automatic activity capture.

> Do **not** deploy the backend to Render/a cloud server — a cloud backend can't see any
> user's files, windows, or their local Supermemory, so activity capture and local memory
> would never work. The backend must run on each user's machine.

---

## 1. Frontend → Vercel (one public deploy)

- **Root Directory:** `frontend`
- **Framework preset:** Vite (Build `npm run build`, Output `dist`, Install `npm install`)
- `frontend/vercel.json` already adds the SPA rewrite so routes like `/passport` don't 404.
- **Env var (optional):**
  - Leave unset → the built app calls the visitor's own `http://localhost:8765` (the default).
  - Or set `VITE_API_URL` to a specific backend origin (e.g. an ngrok/cloudflared tunnel URL) if you want to point at one machine.

Local dev is unchanged: with no `VITE_API_URL`, `npm run dev` uses the Vite proxy to `127.0.0.1:8765`.

## 2. Backend + Supermemory → each user runs locally

Give users these steps (or the one-click `start.bat` in the repo root):

```bash
# 1. Start Supermemory Local  (from your ~/supermemory-local install; must serve :6767)
#    verify:  curl http://localhost:6767/v3/health   ->  {"status":"ok"}

# 2. Start the ECHO backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Then open the Vercel URL — the UI connects to this local backend automatically.

## 3. Browser requirement (Private Network Access)

An HTTPS page (Vercel) calling `http://localhost` triggers Chrome/Edge's **Private Network
Access** check. The backend already answers it (`Access-Control-Allow-Private-Network: true`)
and its CORS allows `*.vercel.app`, so it works in Chrome/Edge/Firefox out of the box. If you
use a **custom domain**, set `FRONTEND_URL=https://your-domain` in the backend environment so
CORS allows it.

## Optional env (backend)
`SUPERMEMORY_BASE_URL` (default `http://localhost:6767`), `CONTEXTOS_USER_ID`,
`FRONTEND_URL`, `CONTEXTOS_WATCH_DIR`. See `.env.example`.

---

### Want a public URL where *you* have every feature working?
Run the backend + Supermemory on your machine and expose the backend with a tunnel
(`cloudflared tunnel --url http://localhost:8765`), then set `VITE_API_URL` on Vercel to that
tunnel URL. The Vercel UI now drives your real local ECHO — full features, public link.

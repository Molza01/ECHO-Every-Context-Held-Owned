"""ContextOS FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.api.websocket import manager
from app.context.engine import get_engine
from app.core.config import get_settings
from app.services.supermemory_service import get_supermemory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("contextos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    engine.set_broadcaster(manager.broadcast)
    await engine.start()
    log.info("ContextOS backend ready")
    yield
    await engine.stop()
    await get_supermemory().aclose()


app = FastAPI(title="ContextOS", version="0.1.0", lifespan=lifespan)


class PrivateNetworkMiddleware(BaseHTTPMiddleware):
    """Allow an HTTPS site (e.g. the Vercel-hosted ECHO UI) to call this backend on the
    user's OWN machine at http://localhost:8765. Chrome/Edge require the server to answer
    the Private Network Access preflight with this header, or the request is blocked.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.headers.get("access-control-request-private-network") == "true":
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response


settings = get_settings()
# Allow: local dev, browser extensions, any *.vercel.app deployment, and an optional
# explicit FRONTEND_URL. The UI runs in the user's browser and calls their local backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if settings.frontend_url else [],
    allow_origin_regex=(
        r"^(https?://localhost(:\d+)?|https?://127\.0\.0\.1(:\d+)?"
        r"|chrome-extension://.*|moz-extension://.*"
        r"|https://[a-z0-9-]+\.vercel\.app)$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# outermost, so it can add the PNA header onto CORS preflight responses
app.add_middleware(PrivateNetworkMiddleware)

app.include_router(router)


@app.get("/")
async def root() -> dict:
    return {"name": "ContextOS", "status": "ok", "memory_engine": "Supermemory Local"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    engine = get_engine()
    engine.ws_clients = manager.count
    # replay current state so a freshly-connected client renders immediately
    try:
        await ws.send_json({
            "type": "hello",
            "data": {
                "phase": engine.phase,
                "context": engine.current_context.model_dump() if engine.current_context else None,
                "last_update": engine.last_update.model_dump() if engine.last_update else None,
            },
        })
    except Exception:  # noqa: BLE001
        pass
    try:
        while True:
            await ws.receive_text()  # keepalive / ignore inbound
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:  # noqa: BLE001
        await manager.disconnect(ws)
    finally:
        engine.ws_clients = manager.count

"""ContextOS FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

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

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    # allow the Vite dev server + browser extensions (chrome-extension://...) to reach the API
    allow_origin_regex=r"^(http://localhost:\d+|http://127\.0\.0\.1:\d+|chrome-extension://.*|moz-extension://.*)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

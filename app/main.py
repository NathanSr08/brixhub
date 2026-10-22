from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static" if (BASE_DIR / "static").exists() else BASE_DIR.parent / "static"
from fastapi import WebSocket, WebSocketDisconnect
from starlette.responses import FileResponse, Response
import hmac
import hashlib
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings
from app.db.clickhouse import init_clients, close_clients
from app.api.v1.router import api_v1
from app.api.legacy import router as legacy
from app.repositories import usage_repo
from app.core import audit
from app.db import bootstrap
from app.api.admin_logs import router as admin_logs_router
from app.api.admin_pricing import router as pricing_router, public_router as config_router
from app.api.admin_web_access import router as admin_web_access_router
from starlette.concurrency import run_in_threadpool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_clients()
    # BRIXHUB-AUDIT : verification du schema + tables d'audit au demarrage
    await run_in_threadpool(bootstrap.ensure_schema)
    await run_in_threadpool(bootstrap.ensure_pricing_defaults)
    await run_in_threadpool(audit.ensure_audit_table)
    usage_task = asyncio.create_task(usage_repo.flush_loop())
    audit_task = asyncio.create_task(audit.flush_loop())
    yield
    usage_task.cancel()
    audit_task.cancel()
    try:
        await audit.flush_now()
    except Exception:
        pass
    await close_clients()


def create_app() -> FastAPI:
    app = FastAPI(
        title="BrixHub API",
        version="1.0.0",
        description="Moteur d'investigation multi-sources & API publique",
        lifespan=lifespan
    )

    app.middleware("http")(audit.audit_middleware)
    app.include_router(admin_logs_router)
    app.include_router(pricing_router)
    app.include_router(admin_web_access_router)
    app.include_router(config_router)


    # Routes v1 avec prefixe
    app.include_router(api_v1, prefix="/v1")
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(auth_router, prefix="/api")
    # Routes legacy (/api/*) et WebSocket
    app.include_router(legacy)
    # Fichiers statiques UI
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app

app = create_app()


import hmac
import hashlib


@app.get("/reset-password", response_class=FileResponse)
async def serve_reset_password():
    return FileResponse(str(STATIC_DIR / "reset-password.html"))

@app.get("/", response_class=FileResponse)
async def serve_index(response: Response):
    s = get_settings()
    sig = hmac.new(s.admin_token.encode(), b"brixhub_internal_web_session", hashlib.sha256).hexdigest()
    res = FileResponse(str(STATIC_DIR / "index.html"))
    res.set_cookie(
        key="bx_web_session",
        value=sig,
        httponly=True,
        samesite="lax",
        secure=False
    )
    return res

# --- TRACKER UTILISATEURS EN LIGNE (WEBSOCKET) ---
connected_websockets = set()

@app.websocket("/ws/online")
async def ws_online_tracker(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        # Diffuser le nombre à tous les clients
        count = len(connected_websockets)
        for ws in list(connected_websockets):
            try:
                await ws.send_json({"online_users": count})
            except Exception:
                connected_websockets.discard(ws)
        
        while True:
            # Maintenir la connexion ouverte (ping/pong automatique)
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        connected_websockets.discard(websocket)
        count = len(connected_websockets)
        for ws in list(connected_websockets):
            try:
                await ws.send_json({"online_users": count})
            except Exception:
                connected_websockets.discard(ws)

@app.get("/api-docs", response_class=FileResponse)
async def serve_api_docs():
    return FileResponse(str(STATIC_DIR / "api-docs.html"))

@app.get("/cgu", response_class=FileResponse)
async def serve_cgu():
    return FileResponse(str(STATIC_DIR / "cgu.html"))

@app.get("/rgpd", response_class=FileResponse)
async def serve_rgpd():
    return FileResponse(str(STATIC_DIR / "rgpd.html"))
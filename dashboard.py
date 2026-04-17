"""
FastAPI + python-socketio (ASGI) dashboard for Music Bot.

Runs in a separate container from the Discord bot. All DB and stats access
uses the same asyncio event loop as the HTTP/WebSocket handlers (no per-request
new_event_loop).
"""

import os
import secrets
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager

import psutil
import socketio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from utils.logger import logger
from utils.stats_manager import stats_manager

# ---------------------------------------------------------------------------
# Secret (Flask name kept for backward compatibility with existing .env)
# ---------------------------------------------------------------------------

if not (os.getenv("DASHBOARD_SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")):
    logger.warning(
        "DASHBOARD_SECRET_KEY / FLASK_SECRET_KEY not set — fine for read-only stats; "
        "set one if you add signed cookies / sessions later."
    )

# ---------------------------------------------------------------------------
# Auth (remote control)
# ---------------------------------------------------------------------------

ADMIN_PIN = os.getenv("ADMIN_PIN")
if not ADMIN_PIN:
    logger.warning(
        "ADMIN_PIN not set — remote control is DISABLED. "
        "Set ADMIN_PIN in your .env (min 6 chars) to enable it."
    )
    ADMIN_PIN = secrets.token_hex(16)

if ADMIN_PIN and len(ADMIN_PIN) < 6:
    logger.warning(f"ADMIN_PIN is too short ({len(ADMIN_PIN)} chars). Use at least 6.")


def check_auth(pin: str) -> bool:
    return pin == ADMIN_PIN


# ---------------------------------------------------------------------------
# Socket.IO (async ASGI)
# ---------------------------------------------------------------------------

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


async def fetch_stats() -> dict:
    """Build the same stats dict the dashboard UI expects on `stats_update`."""
    try:
        global_stats = await stats_manager.get_global_stats()
    except Exception:
        global_stats = {}

    mem = psutil.virtual_memory()
    return {
        "total_plays": global_stats.get("total_plays", 0),
        "active_guilds": global_stats.get("active_guilds", 0),
        "recent_plays": global_stats.get("recent_plays", 0),
        "most_played": global_stats.get("most_played", {}),
        "system": {
            "cpu": psutil.cpu_percent(),
            "memory": mem.percent,
            "status": "Online",
        },
        "analytics": {
            "top_listeners": global_stats.get("top_listeners", []),
            "peak_activity": global_stats.get("peak_activity", [0] * 24),
            "command_usage": global_stats.get("command_usage", {}),
        },
        "servers": global_stats.get("servers", []),
    }


async def _stats_push_loop():
    while True:
        try:
            stats = await fetch_stats()
            await sio.emit("stats_update", stats)
        except Exception as e:
            logger.error("dashboard_background_push", e)
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from utils import db

    await db.init_db()
    task = asyncio.create_task(_stats_push_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Music Bot Dashboard", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "dashboard_enhanced.html",
        {"request": request},
    )


@app.get("/api/stats")
async def get_stats():
    return await fetch_stats()


@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/system")
async def system_info():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory": {
            "total_mb": round(mem.total / 1024 / 1024),
            "used_mb": round(mem.used / 1024 / 1024),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "percent": disk.percent,
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/guilds/{guild_id}/top-songs")
async def guild_top_songs(guild_id: int):
    try:
        songs = await stats_manager.get_server_top_songs(guild_id, limit=10)
        return {"guild_id": guild_id, "songs": [{"title": t, "plays": c} for t, c in songs]}
    except Exception as e:
        logger.error("api_guild_top_songs", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/control")
async def remote_control(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    pin = data.get("pin")
    action = data.get("action")
    guild_id = data.get("guild_id")

    if not check_auth(pin):
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Invalid PIN"},
        )

    if not action or not guild_id:
        return {"success": False, "error": "Missing action or guild_id"}

    payload = data.get("data", {})
    try:
        success = await stats_manager.queue_action(int(guild_id), action, payload)
        if success:
            return {"success": True, "message": f"Action {action} queued"}
        return {"success": False, "error": "Failed to queue action"}
    except Exception as e:
        logger.error("remote_control_api", e)
        return {"success": False, "error": str(e)}


@sio.event
async def connect(sid, environ):
    await sio.emit("status", {"msg": "Connected to Music Bot dashboard"}, room=sid)


# ASGI entrypoint for Uvicorn: Socket.IO handles engine.io; everything else goes to FastAPI.
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)


def run_dashboard():
    """Run with Uvicorn (same as: uvicorn dashboard:asgi_app --host 0.0.0.0 --port $PORT)."""
    import uvicorn

    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting dashboard (FastAPI + Socket.IO) on port {port}")
    uvicorn.run(asgi_app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    run_dashboard()

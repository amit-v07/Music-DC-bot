"""
Flask-SocketIO dashboard for Music Bot.
Runs in a SEPARATE container with gevent (incompatible with uvloop, which only
runs in the bot container).

Changes vs. original:
- Replaced threading.Thread with socketio.start_background_task (gevent-safe).
- Removed the broken _run_async wrapper; dashboard has its own sync event loop.
- Background push interval increased to 5 s (was 2 s) to reduce CPU pressure.
- Added /api/system endpoint.
- Added /api/guilds/<guild_id>/queue  endpoint (reads stats DB).
"""

import os
import secrets
import asyncio
import time
from flask import Flask, render_template, jsonify, request, session
from flask_socketio import SocketIO, emit
import psutil
import logging
from datetime import datetime
from config import config
from utils.logger import logger
from utils.stats_manager import stats_manager


# ---------------------------------------------------------------------------
# Async helper  (used only for calls that NEED async, e.g. aiosqlite)
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from synchronous gevent context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Flask + SocketIO setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

flask_secret = os.getenv("FLASK_SECRET_KEY")
if not flask_secret:
    flask_secret = secrets.token_hex(32)
    logger.warning(
        "FLASK_SECRET_KEY not set — using generated key. "
        "Sessions will NOT persist across restarts! "
        "Set FLASK_SECRET_KEY in your .env for production."
    )
app.secret_key = flask_secret

# gevent is the async mode for the dashboard container (NOT uvloop)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Silence Werkzeug request spam
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

ADMIN_PIN = os.getenv("ADMIN_PIN")
if not ADMIN_PIN:
    logger.warning(
        "ADMIN_PIN not set — remote control is DISABLED. "
        "Set ADMIN_PIN in your .env (min 6 chars) to enable it."
    )
    ADMIN_PIN = secrets.token_hex(16)  # Random unusable PIN

if ADMIN_PIN and len(ADMIN_PIN) < 6:
    logger.warning(f"ADMIN_PIN is too short ({len(ADMIN_PIN)} chars). Use at least 6.")


def check_auth(pin: str) -> bool:
    return pin == ADMIN_PIN


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('dashboard_enhanced.html')


@app.route('/api/stats')
def get_stats():
    """Raw stats dump — same payload as the WebSocket push."""
    return jsonify(_fetch_stats())


@app.route('/api/health')
def health_check():
    """Lightweight health endpoint (checked by docker-compose healthcheck)."""
    return jsonify({
        'status': 'online',
        'cpu': psutil.cpu_percent(),
        'memory': psutil.virtual_memory().percent,
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/system')
def system_info():
    """Detailed system resource snapshot."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return jsonify({
        'cpu_percent': psutil.cpu_percent(interval=None),
        'memory': {
            'total_mb': round(mem.total / 1024 / 1024),
            'used_mb':  round(mem.used  / 1024 / 1024),
            'percent':  mem.percent,
        },
        'disk': {
            'total_gb': round(disk.total / 1024 / 1024 / 1024, 1),
            'used_gb':  round(disk.used  / 1024 / 1024 / 1024, 1),
            'percent':  disk.percent,
        },
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/guilds/<int:guild_id>/top-songs')
def guild_top_songs(guild_id: int):
    """Top 10 songs for a specific guild."""
    try:
        from utils import db
        songs = _run_async(db.get_server_top_songs(guild_id, limit=10))
        return jsonify({'guild_id': guild_id, 'songs': [{'title': t, 'plays': c} for t, c in songs]})
    except Exception as e:
        logger.error("api_guild_top_songs", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/control', methods=['POST'])
def remote_control():
    """Queue a remote action for the bot to execute."""
    data = request.json or {}
    pin = data.get('pin')
    action = data.get('action')
    guild_id = data.get('guild_id')

    if not check_auth(pin):
        return jsonify({'success': False, 'error': 'Invalid PIN'}), 401

    if not action or not guild_id:
        return jsonify({'success': False, 'error': 'Missing action or guild_id'}), 400

    payload = data.get('data', {})
    try:
        success = _run_async(stats_manager.queue_action(int(guild_id), action, payload))
        if success:
            return jsonify({'success': True, 'message': f'Action {action} queued'})
        return jsonify({'success': False, 'error': 'Failed to queue action'}), 500
    except Exception as e:
        logger.error("remote_control_api", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    emit('status', {'msg': 'Connected to Music Bot dashboard'})


# ---------------------------------------------------------------------------
# Background stats push  (uses gevent greenlet via start_background_task)
# ---------------------------------------------------------------------------

def _fetch_stats() -> dict:
    """Synchronous stats fetch — called from gevent greenlet."""
    try:
        global_stats = _run_async(stats_manager.get_global_stats())
    except Exception:
        global_stats = {}

    mem = psutil.virtual_memory()
    return {
        'total_plays':  global_stats.get('total_plays', 0),
        'active_guilds': global_stats.get('active_guilds', 0),
        'recent_plays': global_stats.get('recent_plays', 0),
        'most_played':  global_stats.get('most_played', {}),
        'system': {
            'cpu':    psutil.cpu_percent(),
            'memory': mem.percent,
            'status': 'Online',
        },
        'analytics': {
            'top_listeners':  global_stats.get('top_listeners', []),
            'peak_activity':  global_stats.get('peak_activity', [0] * 24),
            'command_usage':  global_stats.get('command_usage', {}),
        },
        'servers': global_stats.get('servers', []),
    }


def background_stats_push():
    """
    Gevent background task: pushes updated stats to all connected clients
    every 5 seconds via WebSocket.
    """
    while True:
        try:
            stats = _fetch_stats()
            socketio.emit('stats_update', stats)
        except Exception as e:
            logger.error("dashboard_background_push", e)

        socketio.sleep(5)  # gevent-aware sleep — yields to other greenlets


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_dashboard():
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting dashboard on port {port}")

    # Start background stats push as a gevent greenlet (not a thread)
    socketio.start_background_task(background_stats_push)

    socketio.run(app, host='0.0.0.0', port=port, use_reloader=False)


if __name__ == "__main__":
    run_dashboard()
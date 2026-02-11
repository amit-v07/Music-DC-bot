
import eventlet
eventlet.monkey_patch()

import os
import secrets
from flask import Flask, render_template, jsonify, request, session
from flask_socketio import SocketIO, emit
import psutil
import logging
from config import config
from utils.logger import logger
from utils.stats_manager import stats_manager
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key-change-this")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Hide Werkzeug logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Admin PIN for remote control (defaults to 1234 if not set)
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")

# Basic auth helper
def check_auth(pin):
    return pin == ADMIN_PIN

@app.route('/')
def index():
    return render_template('dashboard_enhanced.html')

@app.route('/api/stats')
async def get_stats():
    """API endpoint for raw stats"""
    stats = await stats_manager.get_global_stats()
    return jsonify(stats)

@app.route('/api/control', methods=['POST'])
async def remote_control():
    """API endpoint for remote control actions"""
    data = request.json
    pin = data.get('pin')
    action = data.get('action')
    guild_id = data.get('guild_id')

    if not check_auth(pin):
        return jsonify({'success': False, 'error': 'Invalid PIN'}), 401
    
    if not action or not guild_id:
        return jsonify({'success': False, 'error': 'Missing action or guild_id'}), 400
        
    try:
        success = await stats_manager.queue_action(int(guild_id), action)
        if success:
            return jsonify({'success': True, 'message': f'Action {action} queued'})
        else:
            return jsonify({'success': False, 'error': 'Failed to queue action'}), 500
    except Exception as e:
        logger.error("remote_control_api", e)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """API endpoint for system health"""
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    
    return jsonify({
        'status': 'online',
        'cpu': cpu_percent,
        'memory': memory.percent,
        'timestamp': datetime.now().isoformat()
    })

# WebSocket Connection
@socketio.on('connect')
def handle_connect():
    emit('status', {'msg': 'Connected to dashboard backend'})

# Background task to push updates
def background_stats_update():
    """Push stats updates to connected clients"""
    while True:
        try:
            # Create a new event loop for this thread if needed
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Fetch stats
            stats = loop.run_until_complete(_fetch_fresh_stats())
            
            # Emit to all clients
            socketio.emit('stats_update', stats)
            
            # Sleep for 2 seconds
            eventlet.sleep(2)
            
        except Exception as e:
            logger.error("dashboard_background_task", e)
            eventlet.sleep(5)

async def _fetch_fresh_stats():
    """Helper to fetch and format all stats"""
    global_stats = await stats_manager.get_global_stats()
    
    # Get system stats
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    
    # Calculate uptime (mockup for now, could be improved)
    # in a real scenario we'd track process start time
    
    return {
        'total_plays': global_stats.get('total_plays', 0),
        'active_guilds': global_stats.get('active_guilds', 0),
        'recent_plays': global_stats.get('recent_plays', 0),
        'most_played': global_stats.get('most_played', {}),
        'system': {
            'cpu': cpu_percent,
            'memory': memory.percent,
            'status': 'Online'
        },
        'analytics': {
            'top_listeners': global_stats.get('top_listeners', []),
            'peak_activity': global_stats.get('peak_activity', []), # returns list of 24 ints
            'command_usage': global_stats.get('command_usage', {})
        },
        'servers': global_stats.get('servers', [])
    }

def run_dashboard():
    """Run the Flask-SocketIO server"""
    try:
        # Start background task
        socketio.start_background_task(background_stats_update)
        
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Starting dashboard on port {port}")
        
        # Run server
        socketio.run(app, host='0.0.0.0', port=port, use_reloader=False)
        
    except Exception as e:
        logger.error("dashboard_server", e)
        raise

if __name__ == "__main__":
    run_dashboard()
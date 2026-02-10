"""
Enhanced Web Dashboard for Music Bot
Real-time monitoring and statistics
"""
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import asyncio
import threading
import time
import os
import secrets
from datetime import datetime, timedelta
from utils.logger import logger
from utils.stats_manager import stats_manager
import json


app = Flask(__name__)
# Use environment variable for SECRET_KEY with secure fallback
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Allow all origins for remote access
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables for caching
cached_stats = {}
cache_timestamp = 0
CACHE_DURATION = 30  # Cache for 30 seconds


class DashboardManager:
    """Manages dashboard data and real-time updates"""
    
    def __init__(self):
        self.connected_clients = 0
        self.running = False
        
        # Initialize a dedicated event loop for async operations
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._start_background_loop, daemon=True)
        self.loop_thread.start()
    
    def _start_background_loop(self):
        """Start the dedicated event loop in a separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start_background_updates(self):
        """Start scheduled updates on the dedicated loop"""
        if self.running:
            return
            
        self.running = True
        # Schedule the update task on the loop safely
        asyncio.run_coroutine_threadsafe(self._update_task(), self.loop)
        logger.info("Dashboard background updates started")
    
    def stop_background_updates(self):
        """Stop background updates"""
        self.running = False
        logger.info("Dashboard background updates stopped")
    
    async def _update_task(self):
        """Async task for sending updates"""
        while self.running:
            try:
                if self.connected_clients > 0:
                    # Get fresh stats directly (we are in async context now)
                    stats = await self._fetch_fresh_stats()
                    
                    # Add real-time connection info
                    stats['connected_clients'] = self.connected_clients
                    
                    # Update cache
                    global cached_stats, cache_timestamp
                    cached_stats = stats
                    cache_timestamp = time.time()
                    
                    # Emit to all connected clients
                    socketio.emit('stats_update', {
                        'stats': stats,
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Update every 10 seconds
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error("dashboard_update_loop", e)
                await asyncio.sleep(5)

    def get_cached_stats(self, force_refresh=False):
        """Get statistics with caching"""
        global cached_stats, cache_timestamp
        
        current_time = time.time()
        
        if force_refresh or (current_time - cache_timestamp) > CACHE_DURATION:
            try:
                # Run the coroutine on the dedicated loop and wait for result
                future = asyncio.run_coroutine_threadsafe(self._fetch_fresh_stats(), self.loop)
                fresh_stats = future.result(timeout=5)
                
                cached_stats = fresh_stats
                cache_timestamp = current_time
                
            except Exception as e:
                logger.error("get_cached_stats", e)
                # Return cached stats if available
                pass
        
        return cached_stats
    
    async def _fetch_fresh_stats(self):
        """Fetch fresh statistics from JSON-based stats system"""
        try:
            # Get stats from our new stats manager
            global_stats = await stats_manager.get_global_stats()
            
            enhanced_stats = {
                'total_plays': global_stats['total_plays'],
                'most_played': global_stats['most_played'],
                'active_guilds': global_stats['active_guilds'],
                'recent_plays': global_stats['recent_plays'],
                'servers': global_stats['servers'],  # Include server data
                'timestamp': datetime.now().isoformat(),
                'uptime': self._calculate_uptime(),
                'memory_usage': self._get_memory_usage(),
                'cache_info': {
                    'cached_at': datetime.fromtimestamp(cache_timestamp).isoformat() if cache_timestamp else None,
                    'cache_age': time.time() - cache_timestamp if cache_timestamp else 0
                }
            }
            
            return enhanced_stats
            
        except Exception as e:
            logger.error("fetch_fresh_stats", e)
            return {
                'total_plays': 0,
                'most_played': {},
                'active_guilds': 0,
                'recent_plays': 0,
                'servers': [],
                'error': str(e)
            }
    
    def _calculate_uptime(self):
        """Calculate dashboard uptime"""
        # This is a simplified uptime calculation
        # In a real implementation, you'd track actual start time
        return "Dashboard running"
    
    def _get_memory_usage(self):
        """Get memory usage information"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
                'vms_mb': round(memory_info.vms / 1024 / 1024, 2)
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}


# Initialize dashboard manager
dashboard_manager = DashboardManager()


@app.route('/')
def index():
    """Main dashboard page"""
    try:
        stats = dashboard_manager.get_cached_stats()
        return render_template('dashboard_enhanced.html', stats=stats)
    except Exception as e:
        logger.error("dashboard_index", e)
        return render_template('dashboard_enhanced.html', stats={
            'error': 'Failed to load statistics',
            'total_plays': 0,
            'most_played': {},
            'active_guilds': 0,
            'recent_plays': 0,
            'servers': []
        })


@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    try:
        stats = dashboard_manager.get_cached_stats()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error("api_stats", e)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'connected_clients': dashboard_manager.connected_clients
    })


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    dashboard_manager.connected_clients += 1
    logger.info(f"Dashboard client connected. Total: {dashboard_manager.connected_clients}")
    
    # Immediately broadcast updated count to all clients
    socketio.emit('stats_update', {
        'stats': {'connected_clients': dashboard_manager.connected_clients},
        'timestamp': datetime.now().isoformat()
    })
    
    # Start background updates if this is the first client
    if dashboard_manager.connected_clients == 1:
        dashboard_manager.start_background_updates()
    
    # Send initial stats to the new client
    stats = dashboard_manager.get_cached_stats()
    emit('stats_update', {
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    dashboard_manager.connected_clients = max(0, dashboard_manager.connected_clients - 1)
    logger.info(f"Dashboard client disconnected. Total: {dashboard_manager.connected_clients}")
    
    # Immediately broadcast updated count to remaining clients
    if dashboard_manager.connected_clients > 0:
        socketio.emit('stats_update', {
            'stats': {'connected_clients': dashboard_manager.connected_clients},
            'timestamp': datetime.now().isoformat()
        })
    
    # Stop background updates if no clients are connected
    if dashboard_manager.connected_clients == 0:
        dashboard_manager.stop_background_updates()


@socketio.on('request_stats')
def handle_stats_request():
    """Handle manual stats request"""
    try:
        stats = dashboard_manager.get_cached_stats(force_refresh=True)
        emit('stats_update', {
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error("handle_stats_request", e)
        emit('error', {'message': 'Failed to fetch statistics'})


if __name__ == '__main__':
    try:
        logger.info("Starting enhanced dashboard on http://127.0.0.1:5000")
        socketio.run(app, host='127.0.0.1', port=5000, debug=True)
    except Exception as e:
        logger.error("dashboard_startup", e)
        print(f"Failed to start dashboard: {e}")
    finally:
        dashboard_manager.stop_background_updates() 
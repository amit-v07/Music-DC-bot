#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Function to check if a process is running
check_process() {
    if [ -f "$1" ]; then
        pid=$(cat "$1")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

echo "Starting Music Bot System..."

# Start Dashboard (Gunicorn)
if check_process "dashboard.pid"; then
    echo "Dashboard is already running (PID: $(cat dashboard.pid))"
else
    echo "Starting Dashboard..."
    # Run gunicorn with 1 worker, binding to 0.0.0.0:5000
    # Using gevent worker class for async support with Flask-SocketIO
    nohup gunicorn -k gevent -w 1 -b 0.0.0.0:5000 dashboard:app > dashboard.log 2>&1 &
    echo $! > dashboard.pid
    echo "Dashboard started (PID: $(cat dashboard.pid))"
fi

# Wait a moment
sleep 2

# Start Discord Bot
if check_process "bot.pid"; then
    echo "Bot is already running (PID: $(cat bot.pid))"
else
    echo "Starting Discord Bot..."
    nohup python bot.py > bot.log 2>&1 &
    echo $! > bot.pid
    echo "Bot started (PID: $(cat bot.pid))"
fi

echo "All systems go! Logs are in bot.log and dashboard.log"

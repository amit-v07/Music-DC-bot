#!/bin/bash
# stop.sh - Stop Bot and Dashboard

if [ -f "bot.pid" ]; then
    PID=$(cat bot.pid)
    echo "Stopping Bot (PID: $PID)..."
    kill $PID 2>/dev/null || echo "Bot process not found"
    rm bot.pid
else
    echo "No bot.pid found. Trying pkill..."
    pkill -f "python bot.py"
fi

if [ -f "dashboard.pid" ]; then
    PID=$(cat dashboard.pid)
    echo "Stopping Dashboard (PID: $PID)..."
    kill $PID 2>/dev/null || echo "Dashboard process not found"
    rm dashboard.pid
else
    echo "No dashboard.pid found. Trying pkill..."
    pkill -f "gunicorn"
fi

echo "Stopped."

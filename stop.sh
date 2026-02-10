#!/bin/bash

echo "Stopping Music Bot System..."

# Stop Discord Bot
if [ -f "bot.pid" ]; then
    pid=$(cat bot.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping Bot (PID: $pid)..."
        kill "$pid"
        rm bot.pid
        echo "Bot stopped."
    else
        echo "Bot process not found (stale PID file removed)."
        rm bot.pid
    fi
else
    echo "Bot is not running (no PID file)."
fi

# Stop Dashboard
if [ -f "dashboard.pid" ]; then
    pid=$(cat dashboard.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping Dashboard (PID: $pid)..."
        kill "$pid"
        rm dashboard.pid
        echo "Dashboard stopped."
    else
        echo "Dashboard process not found (stale PID file removed)."
        rm dashboard.pid
    fi
else
    echo "Dashboard is not running (no PID file)."
fi

echo "All stopped."

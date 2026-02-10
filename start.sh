#!/bin/bash
# start.sh - Start Bot and Dashboard in background

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start Dashboard (Gunicorn)
echo "Starting Dashboard..."
nohup gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:5000 dashboard:app > dashboard.log 2>&1 &
echo $! > dashboard.pid

# Start Bot
echo "Starting Music Bot..."
nohup python bot.py > bot.log 2>&1 &
echo $! > bot.pid

echo "Bot and Dashboard started!"
echo "Logs: tail -f bot.log dashboard.log"

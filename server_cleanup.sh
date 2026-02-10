#!/bin/bash
echo "Killing all bot processes..."
pkill -f "python bot.py"
pkill -f "gunicorn"
pkill -f "dashboard.py"
echo "Cleaning up PID files..."
rm -f bot.pid dashboard.pid
echo "Done. All bot instances should be dead."

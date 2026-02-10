#!/bin/bash
echo "Stopping systemd service (if exists)..."
sudo systemctl stop musicbot 2>/dev/null || echo "Service not found or already stopped."
sudo systemctl disable musicbot 2>/dev/null

echo "Killing all bot processes..."
pkill -f "python bot.py"
pkill -f "gunicorn"
pkill -f "dashboard.py"

echo "Cleaning up PID files..."
rm -f bot.pid dashboard.pid

echo "Checks:"
ps aux | grep bot.py
ps aux | grep dashboard.py

echo "Done. All bot instances should be dead."

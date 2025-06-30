#!/bin/bash
# Wispr Health Check & Auto-Restart Script
LOG_FILE="/var/log/wispr/monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Check application health
if ! curl -f -s http://localhost:5000/healthz > /dev/null; then
    echo "[$DATE] ERROR: Wispr not responding, restarting..." >> $LOG_FILE
    systemctl restart wispr
    sleep 30
fi

echo "[$DATE] Health check completed" >> $LOG_FILE 
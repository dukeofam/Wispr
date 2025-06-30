#!/bin/bash
# Wispr Production Deployment Script
set -e

# Load environment variables from .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Activate virtual environment
source wispr_env/bin/activate

# Ensure log directory exists
LOG_DIR=${LOG_DIR:-/var/log/wispr}
mkdir -p "$LOG_DIR"
LOG_FILE=${LOG_FILE:-$LOG_DIR/wispr.log}

# Set default session secret if not set (should be overridden in production!)
if [ -z "$SESSION_SECRET" ]; then
    echo "❌ SESSION_SECRET is not set! Refusing to start in production."
    exit 1
fi

# Run Gunicorn with eventlet worker for SocketIO
exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 --timeout 120 --log-file "$LOG_FILE" --log-level info main:app 
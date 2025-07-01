#!/bin/bash
echo "🚀 Starting Wispr (Development Mode)..."
source wispr_env/bin/activate
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found!"
    exit 1
fi
# Remove old database for a clean run
if [ -f instance/team_collaboration.db ]; then
    echo "Removing old database..."
    rm instance/team_collaboration.db
fi
# Always set a default session secret for development if not set
export SESSION_SECRET="k2d83c03jtn2lk5kj2v5k3bk5l6bk2bkjb2lk"
echo "🌐 Running on http://localhost:5000"
echo "📋 Default login: admin / admin123"
python3 main.py

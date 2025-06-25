#!/bin/bash
echo "🚀 Starting Wispr..."
source wispr_env/bin/activate
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found!"
    exit 1
fi
if [ -z "$SESSION_SECRET" ]; then
    export SESSION_SECRET="dev-secret-key-change-in-production"
    echo "⚠️  Using default session secret!"
fi
echo "🌐 Running on http://localhost:5000"
echo "📋 Default login: admin / admin123"
python main.py

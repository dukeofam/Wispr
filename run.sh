#!/bin/bash

# Wispr Runner Script

echo "🚀 Starting Wispr..."

# Activate virtual environment
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    source wispr_env/Scripts/activate
else
    source wispr_env/bin/activate
fi

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found! Make sure you're in the Wispr directory."
    exit 1
fi

# Set default environment variables if not set
if [ -z "$SESSION_SECRET" ]; then
    export SESSION_SECRET="dev-secret-key-change-in-production"
    echo "⚠️  Using default session secret. Set SESSION_SECRET environment variable for production!"
fi

echo "🌐 Starting server on http://localhost:5000"
echo "📋 Default login: admin / admin123"
echo "🛑 Press Ctrl+C to stop"
echo ""

# Run the application
python main.py
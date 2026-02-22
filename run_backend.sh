#!/bin/bash

# ChangeSense Backend Startup Script
# This script sets up and runs the FastAPI backend server

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "🚀 Starting ChangeSense Backend..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Navigate to backend directory
cd "$BACKEND_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Optional: Check for Gemini API key
if [ -z "$GEMINI_API_KEY" ]; then
    echo "ℹ️  Note: GEMINI_API_KEY not set (AI features will be disabled)"
    echo "   To enable: export GEMINI_API_KEY='your-key-here'"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Backend starting on http://localhost:8000"
echo "📚 API docs available at http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the server
uvicorn app.main:app --reload --port 8000

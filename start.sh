#!/bin/bash

# ChangeSense Full Stack Startup Script
# This script runs both backend and frontend concurrently

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Starting ChangeSense Full Stack Application..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if required directories exist
if [ ! -d "$SCRIPT_DIR/backend" ]; then
    echo "❌ Error: backend directory not found"
    exit 1
fi

if [ ! -d "$SCRIPT_DIR/frontend" ]; then
    echo "❌ Error: frontend directory not found"
    exit 1
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

# Trap Ctrl+C and call cleanup
trap cleanup INT TERM

# Start backend in background
echo "Starting backend server..."
"$SCRIPT_DIR/run_backend.sh" > /tmp/changesense-backend.log 2>&1 &
BACKEND_PID=$!

# Wait a moment for backend to initialize
sleep 2

# Start frontend in background
echo "Starting frontend server..."
"$SCRIPT_DIR/run_frontend.sh" > /tmp/changesense-frontend.log 2>&1 &
FRONTEND_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ChangeSense is running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Frontend: http://localhost:5173"
echo "🔧 Backend:  http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Logs:"
echo "   Backend:  tail -f /tmp/changesense-backend.log"
echo "   Frontend: tail -f /tmp/changesense-frontend.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

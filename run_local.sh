#!/bin/bash

echo "========================================"
echo " PM Update Tool - Starting Dev Servers"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    echo "[SUCCESS] Python setup complete!"
else
    source venv/bin/activate
fi

# Check if node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo "[INFO] Installing frontend dependencies..."
    cd frontend && npm install && cd ..
    echo "[SUCCESS] Frontend setup complete!"
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "[WARNING] .env file not found!"
    echo "Please copy .env.example to .env and fill in your credentials."
    exit 1
fi

echo "[INFO] Starting backend (port 8001) and frontend (port 5173)..."
echo "[INFO] Backend API: http://localhost:8001"
echo "[INFO] Frontend:    http://localhost:5173"
echo "[INFO] Press Ctrl+C to stop"
echo ""

# Start backend in background
python -m uvicorn backend.main:app --reload --reload-include '*.env' --port 8001 &
BACKEND_PID=$!

# Start frontend
cd frontend && npm run dev &
FRONTEND_PID=$!

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait

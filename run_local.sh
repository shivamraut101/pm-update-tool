#!/bin/bash

echo "========================================"
echo " PM Update Tool - Starting Server..."
echo "========================================"
echo

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment not found!"
    echo
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo
    echo "Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
    echo
    echo "[SUCCESS] Setup complete!"
    echo
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "[WARNING] .env file not found!"
    echo "Please create .env file with your credentials."
    echo "See QUICKSTART.md for required configuration."
    echo
    read -p "Press Enter to continue..."
fi

echo "[INFO] Starting FastAPI server..."
echo "[INFO] Server: http://localhost:8001"
echo "[INFO] Press Ctrl+C to stop"
echo

# Start the server
python -m uvicorn backend.main:app --reload --port 8001

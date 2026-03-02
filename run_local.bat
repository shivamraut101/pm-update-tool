@echo off
echo ========================================
echo  PM Update Tool - Starting Dev Servers
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo [SUCCESS] Python setup complete!
    echo.
) else (
    call venv\Scripts\activate.bat
)

REM Check if node_modules exists
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    cd frontend && npm install && cd ..
    echo [SUCCESS] Frontend setup complete!
    echo.
)

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Please copy .env.example to .env and fill in your credentials.
    echo.
    pause
    exit /b 1
)

echo [INFO] Starting backend (port 8001) and frontend (port 5173)...
echo [INFO] Backend API: http://localhost:8001
echo [INFO] Frontend:    http://localhost:5173
echo [INFO] Press Ctrl+C to stop
echo.

REM Start both servers
start "PM-Backend" cmd /c "call venv\Scripts\activate.bat && python -m uvicorn backend.main:app --reload --reload-include *.env --port 8001"
start "PM-Frontend" cmd /c "cd frontend && npm run dev"

echo [INFO] Both servers started in new windows.
echo [INFO] Open http://localhost:5173 in your browser.
pause

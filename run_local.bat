@echo off
echo ========================================
echo  PM Update Tool - Starting Server...
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo.
    echo Creating virtual environment...
    python -m venv venv
    echo.
    echo Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo.
    echo [SUCCESS] Setup complete!
    echo.
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Please create .env file with your credentials.
    echo See QUICKSTART.md for required configuration.
    echo.
    pause
)

echo [INFO] Starting FastAPI server...
echo [INFO] Server: http://localhost:8001
echo [INFO] Press Ctrl+C to stop
echo.

REM Start the server
python -m uvicorn backend.main:app --reload --port 8001

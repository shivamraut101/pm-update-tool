Write-Host "========================================" -ForegroundColor Cyan
Write-Host " PM Update Tool - Starting Server..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-Not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host ""
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
    pip install -r requirements.txt
    Write-Host ""
    Write-Host "[SUCCESS] Setup complete!" -ForegroundColor Green
    Write-Host ""
}

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

# Check if .env exists
if (-Not (Test-Path ".env")) {
    Write-Host "[WARNING] .env file not found!" -ForegroundColor Yellow
    Write-Host "Please create .env file with your credentials." -ForegroundColor Yellow
    Write-Host "See QUICKSTART.md for required configuration." -ForegroundColor Yellow
    Write-Host ""
    Pause
}

Write-Host "[INFO] Starting FastAPI server..." -ForegroundColor Green
Write-Host "[INFO] Server: http://localhost:8001" -ForegroundColor Green
Write-Host "[INFO] Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Start the server
python -m uvicorn backend.main:app --reload --port 8001

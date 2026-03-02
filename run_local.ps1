Write-Host "========================================" -ForegroundColor Cyan
Write-Host " PM Update Tool - Starting Dev Servers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check virtual environment
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "[INFO] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    & venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Write-Host "[SUCCESS] Python setup complete!" -ForegroundColor Green
} else {
    & venv\Scripts\Activate.ps1
}

# Check node_modules
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "[INFO] Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend; npm install; Set-Location ..
    Write-Host "[SUCCESS] Frontend setup complete!" -ForegroundColor Green
}

# Check .env
if (-not (Test-Path ".env")) {
    Write-Host "[WARNING] .env file not found!" -ForegroundColor Red
    Write-Host "Please copy .env.example to .env and fill in your credentials."
    exit 1
}

Write-Host "[INFO] Starting backend (port 8001) and frontend (port 5173)..." -ForegroundColor Green
Write-Host "[INFO] Backend API: http://localhost:8001" -ForegroundColor Gray
Write-Host "[INFO] Frontend:    http://localhost:5173" -ForegroundColor Gray
Write-Host "[INFO] Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Start both servers
Start-Process -NoNewWindow powershell -ArgumentList "-Command", "& venv\Scripts\Activate.ps1; python -m uvicorn backend.main:app --reload --reload-include *.env --port 8001"
Start-Process -NoNewWindow powershell -ArgumentList "-Command", "Set-Location frontend; npm run dev"

Write-Host "[INFO] Both servers started. Open http://localhost:5173" -ForegroundColor Cyan
Write-Host "Press any key to stop..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

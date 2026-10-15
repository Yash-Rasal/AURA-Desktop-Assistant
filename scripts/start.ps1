$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "$Root\backend\.venv\Scripts\python.exe"

Write-Host "Cleaning up old companion backend processes..." -ForegroundColor Gray
Get-CimInstance Win32_Process -Filter "name like 'python%'" -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*run.py*" -or $_.CommandLine -like "*desktop-ai-assistant*backend*" } | 
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# Check & start Ollama
Write-Host "[1/3] Checking Ollama..." -ForegroundColor Cyan
$ollamaReady = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
    if ($r.StatusCode -eq 200) { $ollamaReady = $true }
} catch {}

if (-not $ollamaReady) {
    Write-Host "      Starting Ollama daemon in background..." -ForegroundColor Gray
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Host "      Ollama daemon started!" -ForegroundColor Green
} else {
    Write-Host "      Ollama is already running." -ForegroundColor Green
}

Write-Host "[2/3] Starting backend API..." -ForegroundColor Cyan
$backend = Start-Process -FilePath $Python `
    -ArgumentList "run.py" `
    -WorkingDirectory "$Root\backend" `
    -WindowStyle Hidden `
    -PassThru

# Wait until backend is actually responding (max 15s)
Write-Host "      Waiting for backend on port 8765..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}

if (-not $ready) {
    Write-Host "      [WARNING] Backend did not respond in time. Continuing anyway..." -ForegroundColor Yellow
} else {
    Write-Host "      Backend is ready!" -ForegroundColor Green
}

Write-Host "[3/3] Starting Electron app..." -ForegroundColor Cyan
$env:SKIP_BACKEND = "1"
Set-Location "$Root\frontend\electron-app"
npm start

# Cleanup when Electron exits
Write-Host "`nCleaning up background processes..." -ForegroundColor Gray
if ($backend -and -not $backend.HasExited) {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  Stopped backend." -ForegroundColor Gray
}
Write-Host "Done." -ForegroundColor Green

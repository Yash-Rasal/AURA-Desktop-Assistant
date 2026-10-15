$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Write-Host "Setting up Python backend..."
Set-Location "$Root\backend"
python -m venv .venv
& ".\.venv\Scripts\pip.exe" install -r requirements.txt

Write-Host "Setting up Electron frontend..."
Set-Location "$Root\frontend\electron-app"
npm install

Write-Host "Done. Run: .\scripts\start.ps1"

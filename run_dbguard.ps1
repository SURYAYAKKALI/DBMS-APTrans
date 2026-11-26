# DBGuard PowerShell Launcher
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  DBGuard: Intelligent Database Integrity & Concurrency" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

$VenvPython = ".\.venv\Scripts\python.exe"

if (-Not (Test-Path $VenvPython)) {
    Write-Host "[!] Virtual environment not found. Setting up..." -ForegroundColor Yellow
    python -m venv .venv
    & ".\.venv\Scripts\pip.exe" install -r requirements.txt
}

Write-Host "`n[*] Starting DBGuard Web Server on http://127.0.0.1:5000 ..." -ForegroundColor Green
Write-Host "[*] Open your browser and navigate to: http://127.0.0.1:5000`n" -ForegroundColor Green

& $VenvPython "run.py"

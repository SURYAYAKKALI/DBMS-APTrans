# DBGuard PowerShell Launcher
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  DBGuard: Intelligent Database Integrity & Concurrency" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$VenvPython = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

Write-Host "`n[*] Starting APTrans / DBGuard Web Server on http://127.0.0.1:5000 ..." -ForegroundColor Green
Write-Host "[*] Open your browser and navigate to: http://127.0.0.1:5000`n" -ForegroundColor Green

& $VenvPython "run.py"

# APTrans Faculty Showcase Launcher (PowerShell)
# ACM SIGMOD 2026 Paper Reconstruction & Interactive Showcase

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   APTrans: Anomaly Pattern-guided Transaction Bug Testing" -ForegroundColor White
Write-Host "   ACM SIGMOD 2026 Paper Reconstruction & Interactive Showcase" -ForegroundColor Gray
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PyCmd = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

Write-Host "[1/2] Starting APTrans Web Server..." -ForegroundColor Yellow
$proc = Start-Process -FilePath $PyCmd -ArgumentList "run.py" -PassThru

Start-Sleep -Seconds 2

Write-Host "[2/2] Opening Interactive Web Console in default browser..." -ForegroundColor Green
Start-Process "http://127.0.0.1:5000"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   Web Platform is running at: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "   To run terminal faculty presentation walkthrough:" -ForegroundColor Yellow
Write-Host "     $PyCmd demo_aptrans_presentation.py" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan

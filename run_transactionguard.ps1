# TransactionGuard PowerShell Launcher
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "  Starting TransactionGuard Platform..." -ForegroundColor Green
Write-Host "  Web Dashboard & REST API: http://127.0.0.1:8080" -ForegroundColor Yellow
Write-Host "  OpenAPI Documentation:    http://127.0.0.1:8080/docs" -ForegroundColor Yellow
Write-Host "=========================================================================" -ForegroundColor Cyan

if (Test-Path ".\.venv\Scripts\python.exe") {
    & ".\.venv\Scripts\python.exe" run.py --port 8080
} else {
    python run.py --port 8080
}

@echo off
title TransactionGuard - Database Concurrency Assurance Platform
echo =========================================================================
echo   Starting TransactionGuard Platform...
echo   Web Dashboard & REST API: http://127.0.0.1:8080
echo   OpenAPI Documentation:    http://127.0.0.1:8080/docs
echo =========================================================================

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe run.py --port 8080
) else (
    python run.py --port 8080
)
pause

@echo off
title DBGuard Server & Concurrency Control
echo =======================================================
echo   DBGuard: Intelligent Database Integrity & Concurrency
echo =======================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Creating .venv...
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
)

echo Starting DBGuard Web Server on http://127.0.0.1:5000 ...
echo Press Ctrl+C to stop.
echo.
.\.venv\Scripts\python.exe run.py
pause

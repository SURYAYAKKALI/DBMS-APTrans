@echo off
title DBGuard Server & Concurrency Control
echo =======================================================
echo   DBGuard: Intelligent Database Integrity & Concurrency
echo =======================================================
echo.

cd /d "%~dp0"

IF EXIST ".venv\Scripts\python.exe" (
    SET "PY_CMD=.\.venv\Scripts\python.exe"
) ELSE (
    SET "PY_CMD=python"
)

echo Starting DBGuard Web Server on http://127.0.0.1:5000 ...
echo Press Ctrl+C to stop.
echo.
%PY_CMD% run.py
pause

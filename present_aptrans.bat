@echo off
title APTrans Faculty Showcase Launcher
color 0b
echo ======================================================================
echo    APTrans: Anomaly Pattern-guided Transaction Bug Testing
echo    ACM SIGMOD 2026 Paper Reconstruction ^& Interactive Showcase
echo ======================================================================
echo.

cd /d "%~dp0"

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [*] First-time setup detected. Configuring virtual environment (.venv)...
    python -m venv .venv
    IF EXIST ".venv\Scripts\pip.exe" (
        echo [*] Installing required dependencies from requirements.txt...
        .\.venv\Scripts\pip.exe install -r requirements.txt
    )
)

IF EXIST ".venv\Scripts\python.exe" (
    SET "PY_CMD=.\.venv\Scripts\python.exe"
) ELSE (
    SET "PY_CMD=python"
)

echo [1/2] Launching APTrans Web Application & REST API Server...
start "APTrans Server (Keep Open)" cmd /k "%PY_CMD% run.py"

timeout /t 3 /nobreak >nul

echo [2/2] Opening Interactive Web Dashboard in your default browser...
start http://127.0.0.1:5000

echo.
echo ======================================================================
echo    Web Server is running at http://127.0.0.1:5000
echo    Keep the server terminal window open while interacting with the app.
echo.
echo    To run the interactive CLI presentation walkthrough, open another terminal and run:
echo      %PY_CMD% demo_aptrans_presentation.py
echo ======================================================================
echo.
pause

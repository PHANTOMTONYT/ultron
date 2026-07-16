@echo off
title Living Desktop AI Companion Launcher
echo =========================================
echo  LIVING DESKTOP AI COMPANION LAUNCHER
echo =========================================
echo.

:: Check for .env file
if not exist .env (
    echo [WARNING] .env file not found. Copying .env.example...
    copy .env.example .env
)

echo [1/2] Launching Python Backend (serves the web app + WebSocket)...
start "Companion Backend" cmd /k ".\venv\Scripts\python -m backend.app"

echo [2/2] Opening companion in your default browser...
timeout /t 2 /nobreak >nul
start http://localhost:8765/

echo.
echo Backend is running in the other window. Close it to stop the companion.
pause

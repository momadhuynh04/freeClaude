@echo off
title freeClaude Starter
color 0b

echo =========================================
echo    freeClaude - Universal Proxy Server
echo =========================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found (venv^)!
    echo [!] Please run: python -m venv venv and install dependencies first.
    echo.
    pause
    exit /b 1
)

echo [*] Activating Python virtual environment (venv^)...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [!] Failed to activate venv.
    echo.
    pause
    exit /b 1
)

echo [*] Starting Proxy Server (FastAPI^)...
echo     Press Ctrl+C in the new window to stop the server.
echo.

start "freeClaude Proxy Server" cmd /k "title freeClaude Proxy & color 0a & echo Starting freeClaude Proxy... & python -m cli.main 2>&1 & echo. & echo [!] Server exited with code %ERRORLEVEL% & echo. & pause"

echo [*] Waiting for server to start (3 seconds^)...
timeout /t 3 /nobreak > nul

echo [*] Opening WebUI in browser: http://127.0.0.1:8082 ...
start "" http://127.0.0.1:8082

echo.
echo =========================================
echo [OK] freeClaude launcher finished.
echo - To stop the server, close the "freeClaude Proxy Server" window.
echo - You can close this launcher window safely.
echo =========================================
echo.
pause
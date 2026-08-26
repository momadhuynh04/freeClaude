@echo off
title freeClaude Starter
color 0b

echo =========================================
echo    freeClaude - Universal Proxy Server
echo =========================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found (venv)!
    echo [!] Please run: python -m venv venv and install dependencies first.
    pause
    exit /b
)

echo [*] Activating Python virtual environment (venv)...
call venv\Scripts\activate.bat

echo [*] Starting Proxy Server (FastAPI)...
:: Mo mot cua so terminal rieng de chay server cho gon
start "freeClaude Proxy Server" cmd /k "title freeClaude Proxy & color 0a & python -m cli.main"

echo [*] Waiting for server to start...
timeout /t 2 /nobreak > nul

echo [*] Opening WebUI in browser...
start http://127.0.0.1:8082

echo.
echo =========================================
echo [OK] freeClaude is running successfully!
echo =========================================
echo - To stop the server, close the "freeClaude Proxy Server" window.
echo - You can close this window now.
echo.
pause

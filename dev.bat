@echo off
title freeClaude Development Mode
color 0e

echo =========================================
echo    freeClaude - Development Mode
echo =========================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found (venv^)!
    echo [!] Run: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [*] Starting Backend Proxy (Port 8082^)...
start "freeClaude Backend DEV" cmd /k "title Backend API & color 0a & echo Starting backend... & call venv\Scripts\activate.bat & python -m cli.main 2>&1 & echo. & echo [!] Backend exited with code %ERRORLEVEL% & echo. & pause"

echo [*] Starting Frontend Vite (Port 5173^)...
if not exist "webui\package.json" (
    echo [!] webui\package.json not found. Skipping frontend.
) else (
    start "freeClaude Frontend DEV" cmd /k "title Frontend UI & color 0d & echo Starting frontend... & cd webui && npm run dev 2>&1 & echo. & echo [!] Frontend exited with code %ERRORLEVEL% & echo. & pause"
)

echo [*] Waiting 4 seconds for services to come up...
timeout /t 4 /nobreak > nul

echo [*] Opening WebUI Dev: http://localhost:5173 ...
start "" http://localhost:5173

echo.
echo =========================================
echo [DEV MODE LAUNCHER DONE]
echo - Backend:  http://127.0.0.1:8082
echo - Frontend: http://localhost:5173
echo - Close the individual windows to stop each service.
echo =========================================
echo.
pause
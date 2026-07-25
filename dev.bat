@echo off
title freeClaude Development Mode
color 0e

echo =========================================
echo    freeClaude - Development Mode
echo =========================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [!] Khong tim thay venv! 
    pause
    exit /b
)

echo [*] Khoi dong Backend Proxy (Port 8082)...
start "freeClaude Backend DEV" cmd /k "title Backend API & color 0a & call venv\Scripts\activate.bat & python -m cli.main"

echo [*] Khoi dong Frontend Vite (Port 5173)...
start "freeClaude Frontend DEV" cmd /k "title Frontend UI & color 0d & cd webui && npm run dev"

echo [*] Cho cac service len sóng...
timeout /t 3 /nobreak > nul

echo [*] Mo WebUI Dev...
start http://localhost:5173

echo.
echo =========================================
echo [DEV MODE RUNNING] 
echo - Backend: http://127.0.0.1:8082
echo - Frontend: http://localhost:5173
echo =========================================
pause

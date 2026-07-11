@echo off
title freeClaude Starter
color 0b

echo =========================================
echo    freeClaude - Universal Proxy Server
echo =========================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [!] Khong tim thay moi truong ao venv! 
    echo [!] Vui long chay: python -m venv venv va cai dat dependencies truoc.
    pause
    exit /b
)

echo [*] Kich hoat moi truong ao Python (venv)...
call venv\Scripts\activate.bat

echo [*] Khoi dong Proxy Server (FastAPI)...
:: Mo mot cua so terminal rieng de chay server cho gon
start "freeClaude Proxy Server" cmd /k "title freeClaude Proxy & color 0a & python -m cli.main"

echo [*] Cho Server khoi dong...
timeout /t 2 /nobreak > nul

echo [*] Mo trinh duyet WebUI...
start http://127.0.0.1:8082

echo.
echo =========================================
echo [OK] freeClaude da duoc chay thanh cong!
echo =========================================
echo - De tat server, hay dong cua so "freeClaude Proxy Server".
echo - Ban co the dong cua so hien tai ngay bay gio.
echo.
pause

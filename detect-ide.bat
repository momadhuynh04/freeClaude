@echo off
title freeClaude - IDE Detection Refresh
color 0b

echo =========================================
echo   freeClaude - IDE Detection Refresh
echo =========================================
echo.

curl -s http://127.0.0.1:8082/api/ide-detect-refresh > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Server not running at http://127.0.0.1:8082
    echo [!] Start the proxy first: start.bat or uvicorn proxy.server:app
    pause
    exit /b
)

echo [OK] Detection refreshed!
echo.

curl -s http://127.0.0.1:8082/api/ide-detect -o "%TEMP%\ide-detect.json" 2>nul
if %ERRORLEVEL% NEQ 0 goto :done

powershell -NoProfile -Command "$d = (Get-Content '%TEMP%\ide-detect.json' -Raw | ConvertFrom-Json).detected; if ($d.PSObject.Properties.Count -gt 0) { foreach ($k in $d.PSObject.Properties.Name) { Write-Host \"  $k - $($d.$k.name) (v$($d.$k.version))\" } } else { Write-Host '  No IDEs detected on this system.' }"
del "%TEMP%\ide-detect.json" 2>nul

:done
echo.
pause

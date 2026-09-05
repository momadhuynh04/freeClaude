@echo off
title freeClaude - IDE Detection Refresh
color 0b

echo =========================================
echo   freeClaude - IDE Detection Refresh
echo =========================================
echo.

curl -s -o nul -w "HTTP_CODE=%%{http_code}\n" http://127.0.0.1:8082/api/ide-detect-refresh
if errorlevel 1 (
    echo [!] curl failed or server not running at http://127.0.0.1:8082
    echo [!] Start the proxy first: start.bat or: python -m cli.main
    echo.
    pause
    exit /b 1
)

echo [OK] Detection refreshed!
echo.

set "TMPJSON=%TEMP%\ide-detect.json"
del "%TMPJSON%" 2>nul
curl -s -o "%TMPJSON%" http://127.0.0.1:8082/api/ide-detect
if errorlevel 1 (
    echo [!] Failed to fetch /api/ide-detect
    echo.
    pause
    exit /b 1
)

if not exist "%TMPJSON%" (
    echo [!] No response file produced.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d = (Get-Content -LiteralPath '%TMPJSON%' -Raw | ConvertFrom-Json).detected;" ^
  "if ($null -eq $d) { Write-Host '  No IDEs detected on this system.' }" ^
  "elseif ($d.PSObject.Properties.Count -eq 0) { Write-Host '  No IDEs detected on this system.' }" ^
  "else { foreach ($k in $d.PSObject.Properties.Name) { $item = $d.$k; Write-Host (\"  {0} - {1} (v{2})\" -f $k, $item.name, $item.version) } }"

del "%TMPJSON%" 2>nul

echo.
pause
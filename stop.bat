@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo nas-note 서버를 끕니다.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "foreach ($p in 8000,5173) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
echo 종료했습니다.
pause

@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo nas-note 설치/실행 중... 처음이면 몇 분 걸릴 수 있습니다.
echo 주소는 http://localhost:5173/
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 (
  echo.
  echo 실행에 실패했습니다. 위 메시지 또는 start.log 를 확인하세요.
  echo 다시 start.bat 을 실행하면 설치를 이어서 시도합니다.
  pause
  exit /b 1
)

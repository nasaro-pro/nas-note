@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0.' -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue"

echo nas-note 설치/실행 중... 처음이면 몇 분 걸릴 수 있습니다.
echo 주소는 http://localhost:5173/
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 (
  echo.
  echo 실행에 실패했습니다. start.log 또는 data\logs 를 확인하세요.
  echo start.bat 이 차단되면: 우클릭 - 속성 - 차단 해제 - 확인
  pause
  exit /b 1
)

echo.
echo 켜졌습니다. http://localhost:5173/
echo 끌 때는 stop.bat 을 더블클릭하세요.
pause

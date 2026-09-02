@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM GitHub ZIP / 브라우저로 받으면 Windows가 start.bat 을 인터넷 파일로 차단함
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0.' -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue"

echo nas-note 설치/실행 중... 처음이면 몇 분 걸릴 수 있습니다.
echo 주소는 http://localhost:5173/
echo 이 창이 바로 닫히거나 차단되면 start.bat 우클릭 - 속성 - 차단 해제 후 다시 실행
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 (
  echo.
  echo 실행에 실패했습니다. 위 메시지 또는 start.log 를 확인하세요.
  echo start.bat 이 차단되면: 우클릭 - 속성 - 아래쪽 차단 해제 - 확인
  echo 또는 PowerShell에서: Get-ChildItem -Recurse -File ^| Unblock-File
  echo 그다음: powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
  pause
  exit /b 1
)

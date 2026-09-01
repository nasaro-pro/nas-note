#Requires -Version 5.1
<#
  nas-note first-run + start (Windows)
  - Already-installed tools are skipped
  - Missing Python / Node / FFmpeg are installed with winget over Wi-Fi
  - API keys stay in .env (gitignored) and are never printed
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-RealCommand([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { return $false }
    $src = "$($cmd.Source)"
    if ($src -like "*WindowsApps*") { return $false }
    return $true
}

function Get-PythonLauncher {
    Refresh-Path
    if (Test-RealCommand "py") { return @{ Exe = "py"; Args = @("-3") } }
    if (Test-RealCommand "python") { return @{ Exe = "python"; Args = @() } }
    if (Test-RealCommand "python3") { return @{ Exe = "python3"; Args = @() } }
    return $null
}

function Install-WingetId([string]$Id) {
    Write-Host "설치 중: $Id"
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget이 없습니다. Microsoft Store에서 '앱 설치 관리자'를 설치한 뒤 다시 실행하세요."
    }
    & winget install --id $Id -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    Refresh-Path
}

function Ensure-Python {
    $py = Get-PythonLauncher
    if ($py) {
        Write-Host "Python: 이미 있음"
        return $py
    }
    Write-Host "Python이 없어 winget으로 설치합니다."
    Install-WingetId "Python.Python.3.12"
    Refresh-Path
    Start-Sleep -Seconds 2
    $py = Get-PythonLauncher
    if (-not $py) {
        throw "Python 설치 후 터미널을 한 번 닫았다가 start.bat을 다시 실행하세요."
    }
    return $py
}

function Ensure-Node {
    Refresh-Path
    if (Test-RealCommand "node") {
        Write-Host "Node.js: 이미 있음"
        return
    }
    Write-Host "Node.js가 없어 winget으로 설치합니다."
    Install-WingetId "OpenJS.NodeJS.LTS"
    Refresh-Path
    if (-not (Test-RealCommand "node")) {
        throw "Node.js 설치 후 터미널을 한 번 닫았다가 start.bat을 다시 실행하세요."
    }
}

function Ensure-Ffmpeg {
    Refresh-Path
    $extra = @(
        "C:\ffmpeg\bin",
        "$env:ProgramFiles\ffmpeg\bin",
        "${env:ProgramFiles(x86)}\ffmpeg\bin"
    )
    foreach ($dir in $extra) {
        if (Test-Path (Join-Path $dir "ffmpeg.exe")) {
            $env:Path = "$dir;$env:Path"
        }
    }
    if (Test-RealCommand "ffmpeg" -and (Test-RealCommand "ffprobe")) {
        Write-Host "FFmpeg: 이미 있음"
        return
    }
    Write-Host "FFmpeg가 없어 winget으로 설치합니다."
    Install-WingetId "Gyan.FFmpeg"
    Refresh-Path
    foreach ($dir in $extra) {
        if (Test-Path (Join-Path $dir "ffmpeg.exe")) {
            $env:Path = "$dir;$env:Path"
        }
    }
    if (-not (Test-RealCommand "ffmpeg")) {
        throw "FFmpeg 설치 후 터미널을 한 번 닫았다가 start.bat을 다시 실행하세요."
    }
}

function Read-DotEnvKey([string]$Path, [string]$Key) {
    if (-not (Test-Path $Path)) { return "" }
    foreach ($line in Get-Content $Path -Encoding UTF8) {
        if ($line -match "^\s*#" -or $line -notmatch "=") { continue }
        $name, $rest = $line.Split("=", 2)
        if ($name.Trim() -eq $Key) { return $rest.Trim() }
    }
    return ""
}

function Set-DotEnvKey([string]$Path, [string]$Key, [string]$Value) {
    $lines = @()
    if (Test-Path $Path) { $lines = Get-Content $Path -Encoding UTF8 }
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*$Key\s*=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $found) { $out += "$Key=$Value" }
    Set-Content -Path $Path -Value $out -Encoding UTF8
}

function Ensure-EnvFile {
    $envPath = Join-Path $Root ".env"
    $example = Join-Path $Root ".env.example"
    if (-not (Test-Path $envPath)) {
        Copy-Item $example $envPath
        Write-Host ".env 파일을 만들었습니다. GitHub에는 올라가지 않습니다."
    }
    $groq = Read-DotEnvKey $envPath "GROQ_API_KEY"
    $gemini = Read-DotEnvKey $envPath "GEMINI_API_KEY"
    if (-not $groq) {
        Write-Host ""
        Write-Host "Groq 키가 없습니다. https://console.groq.com/keys"
        $input = Read-Host "GROQ_API_KEY"
        if (-not $input) { throw "GROQ_API_KEY가 필요합니다." }
        Set-DotEnvKey $envPath "GROQ_API_KEY" $input
    }
    if (-not $gemini) {
        Write-Host ""
        Write-Host "Gemini 키가 없습니다. https://aistudio.google.com/apikey"
        $input = Read-Host "GEMINI_API_KEY"
        if (-not $input) { throw "GEMINI_API_KEY가 필요합니다." }
        Set-DotEnvKey $envPath "GEMINI_API_KEY" $input
    }
    Write-Host "API 키: .env에서 확인됨 (값은 출력하지 않음)"
}

Write-Host "=== nas-note 준비 ==="
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$py = Ensure-Python
Ensure-Node
Ensure-Ffmpeg
Ensure-EnvFile

$venvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
$venvPip = Join-Path $Root "backend\.venv\Scripts\pip.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Python 가상환경 생성"
    & $py.Exe @($py.Args + @("-m", "venv", "backend\.venv"))
}
Write-Host "Python 패키지"
& $venvPip install -r (Join-Path $Root "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install 실패" }

Write-Host "Node 패키지"
Push-Location (Join-Path $Root "frontend")
try {
    if (Test-Path "package-lock.json") {
        npm ci
        if ($LASTEXITCODE -ne 0) { npm install }
    } else {
        npm install
    }
    if ($LASTEXITCODE -ne 0) { throw "npm install 실패" }
}
finally {
    Pop-Location
}

function Stop-Port([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        if ($c.OwningProcess) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Stop-Port 8000
Stop-Port 5173

Write-Host "백엔드 시작"
$backend = Start-Process -FilePath $venvPython -ArgumentList @(
    "-m", "uvicorn", "backend.main:app",
    "--host", "127.0.0.1", "--port", "8000"
) -WorkingDirectory $Root -PassThru -WindowStyle Minimized

Write-Host "프론트 시작"
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
if (-not $npm) { $npm = Get-Command npm }
$frontend = Start-Process -FilePath $npm.Source -ArgumentList @("run", "dev") -WorkingDirectory (Join-Path $Root "frontend") -PassThru -WindowStyle Minimized

Write-Host "서버가 켜질 때까지 대기"
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5173/api/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

Start-Process "http://localhost:5173/"
Write-Host ""
Write-Host "nas-note: http://localhost:5173/"
if (-not $ok) {
    Write-Host "아직 응답이 없으면 몇 초 뒤 새로고침하세요."
}
Write-Host "이 창을 닫으면 서버를 같이 종료합니다. 끝내려면 아무 키나 누르세요."
[void][System.Console]::ReadKey($true)

if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
Stop-Port 8000
Stop-Port 5173
Write-Host "종료했습니다."

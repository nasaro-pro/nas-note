#Requires -Version 5.1
$ErrorActionPreference = "Continue"
try { chcp 65001 | Out-Null } catch {}
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Get-ChildItem -LiteralPath $Root -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
$LogFile = Join-Path $Root "start.log"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $Message
}

function Fail([string]$Message) {
    Write-Log "오류: $Message"
    throw $Message
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
    $extra = @(
        "$env:LocalAppData\Programs\Python\Python313",
        "$env:LocalAppData\Programs\Python\Python313\Scripts",
        "$env:LocalAppData\Programs\Python\Python312",
        "$env:LocalAppData\Programs\Python\Python312\Scripts",
        "$env:LocalAppData\Programs\Python\Python311",
        "$env:LocalAppData\Programs\Python\Python311\Scripts",
        "$env:LocalAppData\Programs\nodejs",
        "$env:ProgramFiles\nodejs",
        "$env:ProgramFiles\ffmpeg\bin",
        "${env:ProgramFiles(x86)}\ffmpeg\bin",
        "C:\ffmpeg\bin"
    )
    foreach ($dir in $extra) {
        if ($dir -and (Test-Path $dir)) {
            $env:Path = "$dir;$env:Path"
        }
    }
}

function Test-RealCommand([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { return $false }
    $src = "$($cmd.Source)"
    if ($src -like "*WindowsApps*") { return $false }
    return $true
}

function Find-Python {
    Refresh-Path
    if (Test-RealCommand "py") {
        return @{ Exe = (Get-Command py).Source; Args = @("-3") }
    }
    foreach ($name in @("python", "python3")) {
        if (Test-RealCommand $name) {
            return @{ Exe = (Get-Command $name).Source; Args = @() }
        }
    }
    $candidates = @(
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:LocalAppData\Programs\Python\Python313\python.exe",
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return @{ Exe = $p; Args = @() } }
    }
    $pyHome = "$env:LocalAppData\Programs\Python"
    if (Test-Path $pyHome) {
        foreach ($dir in Get-ChildItem $pyHome -Directory -ErrorAction SilentlyContinue) {
            $p = Join-Path $dir.FullName "python.exe"
            if (Test-Path $p) { return @{ Exe = $p; Args = @() } }
        }
    }
    return $null
}

function Find-Node {
    Refresh-Path
    if (Test-RealCommand "node") { return (Get-Command node).Source }
    foreach ($p in @(
            "$env:ProgramFiles\nodejs\node.exe",
            "$env:LocalAppData\Programs\nodejs\node.exe"
        )) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Find-Npm {
    $node = Find-Node
    if ($node) {
        $npm = Join-Path (Split-Path $node) "npm.cmd"
        if (Test-Path $npm) { return $npm }
    }
    $cmd = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if ($cmd -and "$($cmd.Source)" -notlike "*WindowsApps*") { return $cmd.Source }
    return $null
}

function Test-Http([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Find-Ffmpeg {
    Refresh-Path
    if (Test-RealCommand "ffmpeg") { return (Get-Command ffmpeg).Source }
    $roots = @(
        "C:\ffmpeg\bin\ffmpeg.exe",
        "$env:ProgramFiles\ffmpeg\bin\ffmpeg.exe",
        "${env:ProgramFiles(x86)}\ffmpeg\bin\ffmpeg.exe"
    )
    foreach ($p in $roots) {
        if (Test-Path $p) { return $p }
    }
    $wingetRoot = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages"
    if (Test-Path $wingetRoot) {
        foreach ($dir in Get-ChildItem $wingetRoot -Directory -Filter "Gyan.FFmpeg*" -ErrorAction SilentlyContinue) {
            $hit = Get-ChildItem $dir.FullName -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hit) { return $hit.FullName }
        }
    }
    return $null
}

function Install-WingetId([string]$Id) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Fail "winget이 없습니다. Microsoft Store에서 '앱 설치 관리자'를 설치한 뒤 start.bat을 다시 실행하세요."
    }
    Write-Log "설치 중: $Id"
    $okCodes = @(0, -1978335189, -1978335135)
    $common = @(
        "install", "--id", $Id, "-e",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity"
    )
    & winget @($common + @("--scope", "user"))
    if ($okCodes -contains $LASTEXITCODE) { Refresh-Path; return }
    Write-Log "사용자 설치 실패(코드 $LASTEXITCODE). 전체 설치를 다시 시도합니다."
    & winget $common
    if ($okCodes -contains $LASTEXITCODE) { Refresh-Path; return }
    Write-Log "winget 경고: $Id 코드 $LASTEXITCODE. PATH에서 다시 찾습니다."
    Refresh-Path
}

function Wait-For([scriptblock]$Probe, [string]$Label, [int]$Tries = 16) {
    for ($i = 1; $i -le $Tries; $i++) {
        Refresh-Path
        if (& $Probe) { return $true }
        Start-Sleep -Seconds 2
        Write-Log "$Label 확인 중 ($i/$Tries)"
    }
    return $false
}

function Ensure-Python {
    $py = Find-Python
    if ($py) {
        Write-Log "Python: 이미 있음"
        return $py
    }
    Write-Log "Python이 없어 설치합니다."
    Install-WingetId "Python.Python.3.12"
    if (-not (Wait-For { $null -ne (Find-Python) } "Python")) {
        Fail "Python을 찾지 못했습니다. start.ps1을 한 번 더 실행하세요."
    }
    return (Find-Python)
}

function Ensure-Node {
    if (Find-Node) {
        Write-Log "Node.js: 이미 있음"
        return
    }
    Write-Log "Node.js가 없어 설치합니다."
    Install-WingetId "OpenJS.NodeJS.LTS"
    if (-not (Wait-For { $null -ne (Find-Node) } "Node.js")) {
        Fail "Node.js를 찾지 못했습니다. start.ps1을 한 번 더 실행하세요."
    }
}

function Ensure-Ffmpeg {
    $exe = Find-Ffmpeg
    if ($exe) {
        $dir = Split-Path $exe
        $env:Path = "$dir;$env:Path"
        Write-Log "FFmpeg: 이미 있음"
        return
    }
    Write-Log "FFmpeg가 없어 설치합니다."
    try { Install-WingetId "Gyan.FFmpeg" } catch { Write-Log $_.Exception.Message }
    if (-not (Wait-For { $null -ne (Find-Ffmpeg) } "FFmpeg" 8)) {
        Write-Log "FFmpeg는 나중에 설치해도 됩니다. 사이트는 먼저 켭니다."
        return
    }
    $exe = Find-Ffmpeg
    if ($exe) {
        $env:Path = "$(Split-Path $exe);$env:Path"
    }
}

function Set-DotEnvKey([string]$Path, [string]$Key, [string]$Value) {
    $lines = @()
    if (Test-Path $Path) { $lines = @(Get-Content $Path -Encoding UTF8) }
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*$Key\s*=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $found) { $out = @($out) + "$Key=$Value" }
    Set-Content -Path $Path -Value $out -Encoding UTF8
}

function Ensure-EnvFile {
    $envPath = Join-Path $Root ".env"
    $example = Join-Path $Root ".env.example"
    if (-not (Test-Path $envPath) -and (Test-Path $example)) {
        Copy-Item $example $envPath
        Write-Log ".env 파일을 만들었습니다. 키는 사이트 안내에서 넣으면 됩니다."
    }
    $groq = ""
    $gemini = ""
    if (Test-Path $envPath) {
        foreach ($line in Get-Content $envPath -Encoding UTF8) {
            if ($line -match "^\s*GROQ_API_KEY\s*=\s*(.*)$") { $groq = $Matches[1].Trim() }
            if ($line -match "^\s*GEMINI_API_KEY\s*=\s*(.*)$") { $gemini = $Matches[1].Trim() }
        }
    }
    if (-not $groq -or -not $gemini) {
        Write-Log "API 키가 비어 있습니다. 사이트는 먼저 엽니다. 키는 .env 에 넣으면 됩니다."
    } else {
        Write-Log "API 키: .env에서 확인됨 (값은 출력하지 않음)"
    }
}

function Stop-Port([int]$Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            if ($c.OwningProcess) {
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        $lines = netstat -ano | Select-String ":$Port\s.+LISTENING"
        foreach ($line in $lines) {
            $procId = ($line.ToString().Trim() -split "\s+")[-1]
            if ($procId -match "^\d+$") {
                Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Invoke-Checked([scriptblock]$Cmd, [string]$Label) {
    Write-Log $Label
    & $Cmd
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Fail "$Label 실패 (코드 $LASTEXITCODE)"
    }
}

$script:failed = $false
try {
    Write-Host "nas-note 시작합니다. 처음이면 몇 분 걸릴 수 있습니다."
    Write-Log "=== nas-note 준비 ==="
    $py = Ensure-Python
    Ensure-Node
    Ensure-Ffmpeg
    Ensure-EnvFile

    $env:TMP = Join-Path $env:LOCALAPPDATA "Temp"
    $env:TEMP = $env:TMP
    New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null

    $venvDir = Join-Path $Root "backend\.venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Log "Python 가상환경 생성"
        & $py.Exe @($py.Args + @("-m", "venv", $venvDir))
        if (-not (Test-Path $venvPython)) {
            Fail "가상환경을 만들지 못했습니다."
        }
    }

    $req = Join-Path $Root "backend\requirements.txt"
    Write-Log "pip 준비"
    & $venvPython -m ensurepip --upgrade 2>$null
    & $venvPython -m pip install --upgrade pip setuptools wheel --disable-pip-version-check
    Write-Log "Python 패키지 설치 중..."
    $pipOk = $false
    foreach ($try in 1, 2) {
        & $venvPython -m pip install -r $req --disable-pip-version-check --no-cache-dir --prefer-binary
        if ($LASTEXITCODE -eq 0) { $pipOk = $true; break }
        Write-Log "패키지 설치 재시도 $try"
        Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
        & $py.Exe @($py.Args + @("-m", "venv", $venvDir))
        & $venvPython -m ensurepip --upgrade 2>$null
        & $venvPython -m pip install --upgrade pip setuptools wheel --disable-pip-version-check
    }
    if (-not $pipOk) { Fail "Python 패키지 설치 실패. 인터넷을 확인하고 start.ps1을 다시 실행하세요." }

    Refresh-Path
    $npm = Find-Npm
    if (-not $npm) { Fail "npm을 찾지 못했습니다. start.ps1을 한 번 더 실행하세요." }
    $nodeDir = Split-Path $npm
    $env:Path = "$nodeDir;$env:Path"

    $feDir = Join-Path $Root "frontend"
    Write-Log "Node 패키지 설치 중..."
    $npmInstall = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "`"$npm`" install") -WorkingDirectory $feDir -Wait -PassThru -NoNewWindow
    if ($npmInstall.ExitCode -ne 0) { Fail "npm install 실패" }

    Stop-Port 8000
    Stop-Port 5173

    $logDir = Join-Path $Root "data\logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $backendOut = Join-Path $logDir "backend.out.log"
    $backendErr = Join-Path $logDir "backend.err.log"
    Remove-Item $backendOut, $backendErr -ErrorAction SilentlyContinue

    Write-Log "백엔드 시작"
    $backend = Start-Process -FilePath $venvPython -ArgumentList @(
        "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ) -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

    Write-Log "프론트 시작"
    $frontend = Start-Process -FilePath "cmd.exe" -ArgumentList @(
        "/c", "set `"PATH=$nodeDir;%PATH%`" && `"$npm`" run dev"
    ) -WorkingDirectory $feDir -PassThru -WindowStyle Minimized

    Write-Log "서버 응답 대기"
    $site = ""
    for ($i = 0; $i -lt 90; $i++) {
        $back = Test-Http "http://127.0.0.1:8000/api/health"
        if (Test-Http "http://localhost:5173/") { $site = "http://localhost:5173/" }
        elseif (Test-Http "http://127.0.0.1:5173/") { $site = "http://127.0.0.1:5173/" }
        if ($back -and $site) { break }
        if ($backend.HasExited) {
            if (Test-Path $backendErr) { Get-Content $backendErr -Tail 30 | ForEach-Object { Write-Log $_ } }
            Fail "백엔드가 바로 종료되었습니다. data\logs\backend.err.log 를 확인하세요."
        }
        Start-Sleep -Milliseconds 700
    }

    if (-not $site) {
        Fail "화면 서버가 켜지지 않았습니다. 다시 start.ps1 을 실행하세요."
    }
    if (-not (Test-Http "http://127.0.0.1:8000/api/health")) {
        Write-Log "백엔드는 아직 느릴 수 있습니다. 화면은 먼저 엽니다."
    }

    Start-Process $site
    Write-Log "nas-note 켜짐: $site"
    Write-Host "브라우저가 안 열리면 주소창에 $site 을 넣으세요."
    Write-Host "끌 때는 같은 폴더의 stop.ps1 을 실행하세요."
} catch {
    Write-Log $_.Exception.Message
    Write-Host "실패했습니다. start.log 또는 data\logs 를 확인하세요."
    $script:failed = $true
}
if ($script:failed) { exit 1 }

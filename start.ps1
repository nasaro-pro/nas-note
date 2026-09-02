#Requires -Version 5.1
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
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
    $hits = @()
    foreach ($base in @(
            "$env:LocalAppData\Programs\Python",
            "$env:ProgramFiles",
            "${env:ProgramFiles(x86)}"
        )) {
        if (Test-Path $base) {
            $hits += Get-ChildItem $base -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -notmatch "WindowsApps|Miniconda|Anaconda" } |
                Select-Object -First 8
        }
    }
    $exe = $hits | Select-Object -First 1
    if ($exe) { return @{ Exe = $exe.FullName; Args = @() } }
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
        $hit = Get-ChildItem $wingetRoot -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.FullName }
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
        Fail "Python을 찾지 못했습니다. start.bat을 한 번 더 실행하세요."
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
        Fail "Node.js를 찾지 못했습니다. start.bat을 한 번 더 실행하세요."
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
    Install-WingetId "Gyan.FFmpeg"
    if (-not (Wait-For { $null -ne (Find-Ffmpeg) } "FFmpeg")) {
        Fail "FFmpeg를 찾지 못했습니다. start.bat을 한 번 더 실행하세요."
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
        Write-Log "API 키가 비어 있습니다. 사이트는 열고, 키는 .env 에 넣으면 업로드가 됩니다."
        Write-Log "Groq: https://console.groq.com/keys"
        Write-Log "Gemini: https://aistudio.google.com/apikey"
        try {
            if (-not $groq) {
                $keyVal = Read-Host "GROQ_API_KEY (지금은 건너뛰려면 Enter)"
                if ($keyVal) {
                    Set-DotEnvKey $envPath "GROQ_API_KEY" $keyVal
                }
            }
            if (-not $gemini) {
                $keyVal = Read-Host "GEMINI_API_KEY (지금은 건너뛰려면 Enter)"
                if ($keyVal) {
                    Set-DotEnvKey $envPath "GEMINI_API_KEY" $keyVal
                }
            }
        } catch {
            Write-Log "키 입력을 건너뜁니다."
        }
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
    Write-Log "=== nas-note 준비 ==="
    $py = Ensure-Python
    Ensure-Node
    Ensure-Ffmpeg
    Ensure-EnvFile

    $venvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Log "Python 가상환경 생성"
        & $py.Exe @($py.Args + @("-m", "venv", "backend\.venv"))
        if (-not (Test-Path $venvPython)) {
            Fail "가상환경을 만들지 못했습니다."
        }
    }

    Invoke-Checked { & $venvPython -m pip install --upgrade pip } "pip 준비"
    Invoke-Checked { & $venvPython -m pip install -r (Join-Path $Root "backend\requirements.txt") } "Python 패키지"

    Refresh-Path
    Push-Location (Join-Path $Root "frontend")
    try {
        Write-Log "Node 패키지"
        cmd /c "npm install"
        if ($LASTEXITCODE -ne 0) { Fail "npm install 실패" }
    } finally {
        Pop-Location
    }

    Stop-Port 8000
    Stop-Port 5173

    Write-Log "백엔드 시작"
    $backend = Start-Process -FilePath $venvPython -ArgumentList @(
        "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ) -WorkingDirectory $Root -PassThru -WindowStyle Minimized

    Write-Log "프론트 시작"
    $frontend = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npm run dev") -WorkingDirectory (Join-Path $Root "frontend") -PassThru -WindowStyle Minimized

    Write-Log "http://localhost:5173/ 응답 대기"
    $ok = $false
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:5173/api/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }

    Start-Process "http://localhost:5173/"
    Write-Host ""
    Write-Host "nas-note: http://localhost:5173/"
    if (-not $ok) {
        Write-Log "아직 응답이 없으면 몇 초 뒤 새로고침하세요. 로그: start.log"
    }
    Write-Host "이 창을 닫으면 서버를 같이 종료합니다. 끝내려면 아무 키나 누르세요."
    try {
        [void][System.Console]::ReadKey($true)
    } catch {
        Start-Sleep -Seconds 86400
    }
} catch {
    Write-Log $_.Exception.Message
    Write-Host "실패했습니다. start.log 를 확인하세요."
    $script:failed = $true
} finally {
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    Stop-Port 8000
    Stop-Port 5173
    Write-Log "종료했습니다."
}
if ($script:failed) { exit 1 }

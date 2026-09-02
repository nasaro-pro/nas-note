#Requires -Version 5.1
param([switch]$ProbePython)
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

function Get-PythonVersion($info) {
    try {
        $exe = [string]$info.Exe
        if (-not $exe) { $exe = [string]$info["Exe"] }
        if (-not $exe -or ($exe -like "*WindowsApps*")) { return $null }
        $code = "import sys; print(str(sys.version_info[0]) + chr(46) + str(sys.version_info[1]))"
        $raw = & $exe -c $code
        $text = ([string]$raw).Trim().Trim([char]0xFEFF)
        if ($text -match "(\d+)\.(\d+)") {
            return [version]($Matches[1] + "." + $Matches[2])
        }
    } catch {}
    return $null
}

function Test-PythonNewEnough($info) {
    $v = Get-PythonVersion $info
    return $v -and ($v -ge [version]"3.10")
}

function Add-PythonTry($list, [string]$Exe, $PyArgs) {
    if (-not $Exe) { return }
    try { $Exe = [IO.Path]::GetFullPath($Exe.Trim().Trim('"')) } catch { return }
    if (-not (Test-Path -LiteralPath $Exe)) { return }
    $name = [IO.Path]::GetFileName($Exe)
    # Store python.exe 스텁은 가짜. py.exe 런처는 WindowsApps여도 실제 설치를 가리킨다.
    if ($Exe -like "*WindowsApps*" -and $name -ne "py.exe") { return }
    $key = "$Exe|$($PyArgs -join ' ')"
    if ($list | Where-Object { "$($_.Exe)|$($_.PyArgs -join ' ')" -eq $key }) { return }
    $list.Add(@{ Exe = $Exe; PyArgs = @($PyArgs) })
}

function Find-PyLauncher {
    foreach ($p in @(
            "$env:LocalAppData\Python\bin\py.exe",
            "$env:LocalAppData\Programs\Python\Launcher\py.exe",
            "$env:SystemRoot\py.exe",
            "C:\Windows\py.exe"
        )) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    return $null
}

function Find-Python {
    Refresh-Path
    $tries = New-Object System.Collections.Generic.List[object]

    $launcher = Find-PyLauncher
    if ($launcher) {
        try {
            $listFile = Join-Path $env:TEMP "nas-note-py0p.txt"
            $p0 = Start-Process -FilePath $launcher -ArgumentList @("-0p") -Wait -PassThru -WindowStyle Hidden `
                -RedirectStandardOutput $listFile -RedirectStandardError "$listFile.err"
            if (Test-Path $listFile) {
                foreach ($line in Get-Content $listFile -ErrorAction SilentlyContinue) {
                    if ("$line" -match '(?i)([a-z]:\\[^\r\n]*python\.exe)') {
                        Add-PythonTry $tries $Matches[1] @()
                    }
                }
            }
            Remove-Item $listFile, "$listFile.err" -ErrorAction SilentlyContinue
        } catch {}
    }

    foreach ($p in @(
            "$env:LocalAppData\Python\pythoncore-3.14-64\python.exe",
            "$env:LocalAppData\Python\pythoncore-3.14-arm64\python.exe",
            "$env:LocalAppData\Python\bin\python.exe",
            "$env:LocalAppData\Programs\Python\Python314\python.exe",
            "$env:ProgramFiles\Python314\python.exe",
            "C:\Python314\python.exe",
            "$env:LocalAppData\Programs\Python\Python313\python.exe",
            "$env:LocalAppData\Programs\Python\Python312\python.exe",
            "$env:LocalAppData\Programs\Python\Python312-arm64\python.exe",
            "$env:LocalAppData\Python\pythoncore-3.12-64\python.exe",
            "$env:LocalAppData\Programs\Python\Python311\python.exe",
            "$env:LocalAppData\Programs\Python\Python310\python.exe",
            "$env:ProgramFiles\Python313\python.exe",
            "$env:ProgramFiles\Python312\python.exe",
            "$env:ProgramFiles\Python311\python.exe",
            "$env:ProgramFiles\Python310\python.exe",
            "${env:ProgramFiles(x86)}\Python312-32\python.exe",
            "${env:ProgramFiles(x86)}\Python311-32\python.exe",
            "C:\Python313\python.exe",
            "C:\Python312\python.exe",
            "C:\Python311\python.exe",
            "C:\Python310\python.exe"
        )) {
        Add-PythonTry $tries $p @()
    }

    foreach ($regRoot in @(
            "HKCU:\Software\Python\PythonCore",
            "HKLM:\Software\Python\PythonCore",
            "HKLM:\Software\Wow6432Node\Python\PythonCore"
        )) {
        if (-not (Test-Path $regRoot)) { continue }
        foreach ($ver in Get-ChildItem $regRoot -ErrorAction SilentlyContinue) {
            $ip = Join-Path $ver.PSPath "InstallPath"
            try {
                $dir = (Get-ItemProperty -Path $ip -ErrorAction SilentlyContinue)."(default)"
                if ($dir) { Add-PythonTry $tries (Join-Path $dir "python.exe") @() }
            } catch {}
        }
    }

    foreach ($pySearchRoot in @(
            "$env:LocalAppData\Python",
            "$env:LocalAppData\Programs\Python",
            "$env:ProgramFiles\Python",
            "${env:ProgramFiles(x86)}\Python"
        )) {
        if (-not (Test-Path $pySearchRoot)) { continue }
        foreach ($hit in Get-ChildItem $pySearchRoot -Filter python.exe -Recurse -ErrorAction SilentlyContinue) {
            if ($hit.FullName -match "\\Lib\\venv\\") { continue }
            Add-PythonTry $tries $hit.FullName @()
        }
    }

    $wingetRoot = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages"
    if (Test-Path $wingetRoot) {
        foreach ($dir in Get-ChildItem $wingetRoot -Directory -Filter "Python.Python.3*" -ErrorAction SilentlyContinue) {
            $hit = Get-ChildItem $dir.FullName -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hit) { Add-PythonTry $tries $hit.FullName @() }
        }
    }
    $best = $null
    $bestVer = [version]"0.0"
    Write-Log "Python 후보 $($tries.Count)개"
    foreach ($info in $tries) {
        $v = Get-PythonVersion $info
        if (-not $v) { continue }
        if ($v -lt [version]"3.10") {
            Write-Log "오래된 Python $v 건너뜀: $($info.Exe)"
            continue
        }
        if ($v -gt $bestVer) {
            $best = $info
            $bestVer = $v
        }
    }
    return $best
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
        $v = Get-PythonVersion $py
        Write-Log "Python $v 사용: $($py.Exe) $($py.PyArgs -join ' ')"
        return $py
    }
    Write-Log "Python 3.10+ 가 없습니다. 3.14를 설치합니다."
    Install-WingetId "Python.Python.3.14"
    $launcher = Find-PyLauncher
    if ($launcher) {
        Write-Log "py install 3.14"
        & $launcher install 3.14 2>$null
    }
    if (Wait-For { $null -ne (Find-Python) } "Python" 20) {
        $py = Find-Python
        $v = Get-PythonVersion $py
        Write-Log "Python $v 사용: $($py.Exe) $($py.PyArgs -join ' ')"
        return $py
    }
    Write-Log "3.14를 못 찾아서 3.12를 설치합니다."
    Install-WingetId "Python.Python.3.12"
    if ($launcher -or ($launcher = Find-PyLauncher)) {
        Write-Log "py install 3.12"
        & $launcher install 3.12 2>$null
    }
    if (-not (Wait-For { $null -ne (Find-Python) } "Python" 20)) {
        $dump = Find-PyLauncher
        if ($dump) {
            Write-Log "py -0p:"
            & $dump -0p 2>&1 | ForEach-Object { Write-Log "  $_" }
        }
        Fail "Python 3.10+ 를 찾지 못했습니다. python.org 에서 3.14 또는 3.12를 설치하세요."
    }
    $py = Find-Python
    $v = Get-PythonVersion $py
        Write-Log "Python $v 사용: $($py.Exe) $($py.PyArgs -join ' ')"
    return $py
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

if ($ProbePython) {
    $p = Find-Python
    if ($p) {
        Write-Host ("FOUND " + (Get-PythonVersion $p) + " " + $p.Exe)
        exit 0
    }
    Write-Host "FOUND none"
    exit 1
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

    # 한글/공백 폴더(새 폴더, 바탕 화면)에서는 venv·pip가 자주 깨져서
    # 가상환경은 영문 경로(%LOCALAPPDATA%\nas-note)에 만든다.
    $hash = [BitConverter]::ToString(
        [System.Security.Cryptography.SHA256]::Create().ComputeHash(
            [Text.Encoding]::UTF8.GetBytes($Root)
        )
    ).Replace("-", "").Substring(0, 16).ToLower()
    $venvDir = Join-Path $env:LOCALAPPDATA "nas-note\venv-$hash"
    $localVenv = Join-Path $Root "backend\.venv"
    $localPy = Join-Path $localVenv "Scripts\python.exe"
    $rootHasNonAscii = [regex]::IsMatch($Root, "[^\x00-\x7F]")
    if (-not $rootHasNonAscii -and (Test-Path $localPy)) {
        $venvDir = $localVenv
        Write-Log "기존 backend\\.venv 를 사용합니다."
    }
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    New-Item -ItemType Directory -Force -Path (Split-Path $venvDir) | Out-Null
    if (Test-Path $venvPython) {
        $venvVer = Get-PythonVersion @{ Exe = $venvPython; Args = @() }
        if (-not $venvVer -or $venvVer -lt [version]"3.10") {
            Write-Log "가상환경 Python($venvVer)이 오래되어 지우고 다시 만듭니다."
            Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
        }
    }
    if (-not (Test-Path $venvPython)) {
        Write-Log "Python 가상환경 생성: $venvDir"
        $venvCreate = @()
        if ($py.PyArgs) { $venvCreate += @($py.PyArgs) }
        $venvCreate += @("-m", "venv", $venvDir)
        & $py.Exe @venvCreate
        if (-not (Test-Path $venvPython)) {
            Fail "가상환경을 만들지 못했습니다."
        }
    }

    $req = Join-Path $Root "backend\requirements.txt"
    if (-not (Test-Path -LiteralPath $req)) {
        Fail "backend\requirements.txt 가 없습니다. git clone 이 끝난 폴더에서 실행하세요."
    }
    $reqAscii = Join-Path $env:TMP "nas-note-requirements.txt"
    Copy-Item -LiteralPath $req -Destination $reqAscii -Force
    function Invoke-NasNotePip {
        param([string]$PythonExe)
        $venvVer = Get-PythonVersion @{ Exe = $PythonExe; PyArgs = @() }
        Write-Log "pip 준비 (venv Python $venvVer)"
        if (-not $venvVer -or $venvVer -lt [version]"3.10") { return 99 }
        & $PythonExe -m ensurepip --upgrade
        Write-Log "pip 업그레이드"
        & $PythonExe -m pip install --upgrade pip setuptools wheel --disable-pip-version-check
        Write-Log "Python 패키지 설치 중..."
        & $PythonExe -m pip install -r $reqAscii --disable-pip-version-check --prefer-binary
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 1 }
        if ($code -ne 0) {
            Write-Log "pip 종료 코드 $code. trusted-host 로 다시 시도"
            & $PythonExe -m pip install -r $reqAscii --disable-pip-version-check --prefer-binary `
                --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
            $code = $LASTEXITCODE
            if ($null -eq $code) { $code = 1 }
        }
        return $code
    }
    $pipCode = Invoke-NasNotePip $venvPython
    if ($pipCode -ne 0) {
        Write-Log "패키지 설치 한 번 더 시도 (영문 경로에 가상환경 다시 만듦)"
        $venvDir = Join-Path $env:LOCALAPPDATA "nas-note\venv-$hash"
        $venvPython = Join-Path $venvDir "Scripts\python.exe"
        Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path (Split-Path $venvDir) | Out-Null
        $venvCreate = @()
        if ($py.PyArgs) { $venvCreate += @($py.PyArgs) }
        $venvCreate += @("-m", "venv", $venvDir)
        & $py.Exe @venvCreate
        $pipCode = Invoke-NasNotePip $venvPython
    }
    if ($pipCode -ne 0) {
        Fail "Python 패키지 설치 실패 (코드 $pipCode). 위 pip 에러를 확인하세요."
    }

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

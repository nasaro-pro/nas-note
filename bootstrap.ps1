#Requires -Version 5.1
# 빈 폴더에서 실행. Git이 없어도 GitHub에서 코드를 받은 뒤 start.ps1을 켠다.
$ErrorActionPreference = "Continue"
try { chcp 65001 | Out-Null } catch {}
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
    $OutputEncoding = [Console]::OutputEncoding
} catch {}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location -LiteralPath $Root
$RepoZip = "https://github.com/nasaro-pro/nas-note/archive/refs/heads/main.zip"
$RepoGit = "https://github.com/nasaro-pro/nas-note.git"

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
    foreach ($dir in @(
            "C:\Program Files\Git\cmd",
            "C:\Program Files\Git\bin",
            "$env:LocalAppData\Programs\Git\cmd"
        )) {
        if (Test-Path -LiteralPath $dir) { $env:Path = "$dir;$env:Path" }
    }
}

function Find-Git {
    Refresh-Path
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd -and "$($cmd.Source)" -notlike "*WindowsApps*") { return $cmd.Source }
    foreach ($p in @(
            "C:\Program Files\Git\cmd\git.exe",
            "C:\Program Files\Git\bin\git.exe",
            "$env:LocalAppData\Programs\Git\cmd\git.exe"
        )) {
        if (Test-Path -LiteralPath $p) { return $p }
    }
    return $null
}

function Install-Git {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { return }
    Write-Host "Git이 없어 설치합니다. 1~2분 걸릴 수 있습니다."
    $okCodes = @(0, -1978335189, -1978335135)
    $args = @(
        "install", "--id", "Git.Git", "-e",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity"
    )
    & winget @($args + @("--scope", "user"))
    if ($okCodes -contains $LASTEXITCODE) { Refresh-Path; return }
    & winget $args
    Refresh-Path
}

function Get-CodeFromZip {
    Write-Host "GitHub에서 코드를 받습니다. (Git 없음)"
    $zip = Join-Path $env:TEMP "nas-note.zip"
    $src = Join-Path $env:TEMP "nas-note-src"
    Invoke-WebRequest -UseBasicParsing -Uri $RepoZip -OutFile $zip
    if (Test-Path -LiteralPath $src) { Remove-Item -LiteralPath $src -Recurse -Force }
    Expand-Archive -LiteralPath $zip -DestinationPath $src -Force
    $inner = Join-Path $src "nas-note-main"
    if (-not (Test-Path -LiteralPath $inner)) {
        $inner = Get-ChildItem -LiteralPath $src -Directory | Select-Object -First 1 -ExpandProperty FullName
    }
    Get-ChildItem -LiteralPath $inner -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Root -Recurse -Force
    }
}

$git = Find-Git
if (-not $git) {
    Install-Git
    $git = Find-Git
}

$hasStart = Test-Path -LiteralPath (Join-Path $Root "start.ps1")
$hasGitDir = Test-Path -LiteralPath (Join-Path $Root ".git")

if (-not $hasStart) {
    if ($git) {
        Write-Host "GitHub에서 코드를 받습니다."
        & $git clone $RepoGit .
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            Write-Host "git clone이 실패해서 ZIP으로 다시 받습니다."
            Get-CodeFromZip
        }
    } else {
        Get-CodeFromZip
    }
} elseif ($hasGitDir -and $git) {
    Write-Host "로컬 코드로 시작합니다. (업데이트는 git pull)"
}

$start = Join-Path $Root "start.ps1"
if (-not (Test-Path -LiteralPath $start)) {
    throw "start.ps1 을 받지 못했습니다. 인터넷을 확인한 뒤 빈 폴더에서 다시 실행하세요."
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $start
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$ErrorActionPreference = "SilentlyContinue"
foreach ($port in 8000, 5173) {
    Get-NetTCPConnection -LocalPort $port -State Listen | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force
    }
}
Write-Host "nas-note stopped"

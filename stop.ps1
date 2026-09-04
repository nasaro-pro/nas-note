$ErrorActionPreference = "SilentlyContinue"
foreach ($port in 8000, 5173) {
    $killed = $false
    try {
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            $killed = $true
        }
    } catch {}
    if (-not $killed) {
        netstat -ano | Select-String ":$port\s.+LISTENING" | ForEach-Object {
            $procId = ($_.ToString().Trim() -split "\s+")[-1]
            if ($procId -match "^\d+$") {
                Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
Write-Host "nas-note stopped"

# Control local backend (uvicorn; port from backend/.env APP_PORT, default 8888)
#
# Usage:
#   .\scripts\backend.ps1 start|stop|status|restart

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\dev-common.ps1"

$DefaultPort = 8888
$LogFile = Join-Path $DevStateDir "backend.log"
$ErrLogFile = [System.IO.Path]::ChangeExtension($LogFile, ".err.log")

function Get-BackendPort {
    $envFile = Join-Path $DevBackendDir ".env"
    $configured = Get-DevEnvFileValue -EnvFile $envFile -Key "APP_PORT"
    if ($configured -and $configured -match '^\d+$') {
        return [int]$configured
    }
    return $DefaultPort
}

function Get-BackendLogTail {
    param([string[]]$Paths)
    $chunks = foreach ($path in $Paths) {
        if (-not (Test-Path $path)) { continue }
        $lines = @(Get-Content $path -Tail 20 -ErrorAction SilentlyContinue)
        if ($lines.Count -eq 0) { continue }
        "--- $path ---`n$($lines -join "`n")"
    }
    return ($chunks -join "`n`n")
}

function Get-StatusMessage {
    $Port = Get-BackendPort
    $pids = @(Get-DevPortPids $Port)
    $code = Get-DevHttpCode "http://localhost:$Port/health"
    if ($code -eq "200") {
        $pidText = if ($pids.Count) { ", pid(s) $($pids -join ' ')" } else { "" }
        return "running (port $Port, health OK$pidText)"
    }
    if ($pids.Count) {
        return "starting or unhealthy (port $Port, pid(s) $($pids -join ' '))"
    }
    return "stopped"
}

function Test-IsRunning {
    $Port = Get-BackendPort
    return (Get-DevHttpCode "http://localhost:$Port/health") -eq "200"
}

function Start-Backend {
    $Port = Get-BackendPort

    if (Test-IsRunning) {
        Write-Host "Already running. Use: .\scripts\backend.ps1 restart"
        return
    }

    $envFile = Join-Path $DevBackendDir ".env"
    $envExample = Join-Path $DevBackendDir ".env.example"
    if (-not (Test-Path $envFile)) {
        if (Test-Path $envExample) {
            Copy-Item $envExample $envFile
            Write-Host "Created backend/.env from .env.example"
        } else {
            throw "Missing backend/.env"
        }
    }

    $uvicorn = Join-Path $DevBackendDir ".venv\Scripts\uvicorn.exe"
    if (-not (Test-Path $uvicorn)) {
        throw "Backend venv not found. Run: cd backend; python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    }

    $portOwner = Get-DevPortOwnerSummary $Port
    if ($portOwner) {
        $healthCode = Get-DevHttpCode "http://localhost:$Port/health"
        if ($healthCode -ne "200") {
            throw @"
Port $Port is already in use by another process:
$portOwner

Stop that process, set APP_PORT in backend/.env to a free port, or run: .\scripts\backend.ps1 stop
"@
        }
    }

    Write-Host "backend: starting..."
    Start-DevDetachedProcess `
        -WorkingDirectory $DevBackendDir `
        -LogFile $LogFile `
        -FilePath $uvicorn `
        -ArgumentList @("bebcare.main:app", "--host", "0.0.0.0", "--port", "$Port", "--reload")

    for ($i = 0; $i -lt 30; $i++) {
        if ((Get-DevHttpCode "http://localhost:$Port/health") -eq "200") {
            Write-Host "backend: started -> http://localhost:$Port (log: .dev/backend.log)"
            return
        }
        Start-Sleep -Seconds 1
    }

    $logTail = Get-BackendLogTail @($LogFile, $ErrLogFile)
    $message = "Backend launched but health check failed on port $Port."
    if ($logTail) {
        throw "$message`n`n$logTail"
    }
    throw "$message See .dev/backend.log and .dev/backend.err.log"
}

function Stop-Backend {
    $Port = Get-BackendPort
    if (Stop-DevPort $Port) {
        Write-Host "backend: stopped"
    } else {
        Write-Host "backend: not running"
    }
}

if (-not $Action) {
    Write-Host "Usage: .\scripts\backend.ps1 <start|stop|status|restart>"
    exit 1
}

switch ($Action) {
    "start" { Start-Backend }
    "stop" { Stop-Backend }
    "status" { Write-Host "backend: $(Get-StatusMessage)" }
    "restart" { Stop-Backend; Start-Backend }
}

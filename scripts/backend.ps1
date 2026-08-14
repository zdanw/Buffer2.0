# Control local backend (uvicorn on :8080)
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

$Port = 8080
$LogFile = Join-Path $DevStateDir "backend.log"

function Get-StatusMessage {
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
    return (Get-DevHttpCode "http://localhost:$Port/health") -eq "200"
}

function Start-Backend {
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

    throw "Backend launched but health check failed. See .dev/backend.log"
}

function Stop-Backend {
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

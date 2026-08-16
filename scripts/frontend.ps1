# Control local frontend (Vite on :5174)
#
# Usage:
#   .\scripts\frontend.ps1 start|stop|status|restart

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\dev-common.ps1"

$Port = 5174
$LogFile = Join-Path $DevStateDir "frontend.log"

function Get-StatusMessage {
    $pids = @(Get-DevPortPids $Port)
    $code = Get-DevHttpCode "http://localhost:$Port/"
    if ($code -eq "200") {
        $pidText = if ($pids.Count) { ", pid(s) $($pids -join ' ')" } else { "" }
        return "running (port $Port$pidText)"
    }
    if ($pids.Count) {
        return "starting (port $Port, pid(s) $($pids -join ' '))"
    }
    return "stopped"
}

function Test-IsRunning {
    return (Get-DevHttpCode "http://localhost:$Port/") -eq "200"
}

function Start-Frontend {
    if (Test-IsRunning) {
        Write-Host "Already running. Use: .\scripts\frontend.ps1 restart"
        return
    }

    $nodeModules = Join-Path $DevFrontendDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        throw "Frontend dependencies missing. Run: cd frontend; npm ci"
    }

    Write-Host "frontend: starting..."
    Start-DevDetachedProcess `
        -WorkingDirectory $DevFrontendDir `
        -LogFile $LogFile `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev")

    for ($i = 0; $i -lt 30; $i++) {
        if ((Get-DevHttpCode "http://localhost:$Port/") -eq "200") {
            Write-Host "frontend: started -> http://localhost:$Port (log: .dev/frontend.log)"
            return
        }
        Start-Sleep -Seconds 1
    }

    throw "Frontend launched but not responding yet. See .dev/frontend.log"
}

function Stop-Frontend {
    if (Stop-DevPort $Port) {
        Write-Host "frontend: stopped"
    } else {
        Write-Host "frontend: not running"
    }
}

if (-not $Action) {
    Write-Host "Usage: .\scripts\frontend.ps1 <start|stop|status|restart>"
    exit 1
}

switch ($Action) {
    "start" { Start-Frontend }
    "stop" { Stop-Frontend }
    "status" { Write-Host "frontend: $(Get-StatusMessage)" }
    "restart" { Stop-Frontend; Start-Frontend }
}

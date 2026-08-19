$script:DevRootDir = Split-Path -Parent $PSScriptRoot
$script:DevStateDir = Join-Path $DevRootDir ".dev"
$script:DevBackendDir = Join-Path $DevRootDir "backend"
$script:DevFrontendDir = Join-Path $DevRootDir "frontend"

New-Item -ItemType Directory -Force -Path $DevStateDir | Out-Null

function Get-DevPortPids([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Stop-DevPort([int]$Port) {
    $pids = @(Get-DevPortPids $Port)
    if ($pids.Count -eq 0) { return $false }
    foreach ($processId in $pids) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    return $true
}

function Get-DevHttpCode([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return [string]$response.StatusCode
    } catch {
        return "000"
    }
}

function Get-DevPortOwnerSummary([int]$Port) {
    $pids = @(Get-DevPortPids $Port)
    if ($pids.Count -eq 0) { return $null }

    $details = foreach ($processId in $pids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if (-not $proc) {
            "pid $processId"
            continue
        }

        $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue).CommandLine
        if ($commandLine) {
            "pid $processId ($($proc.ProcessName)): $commandLine"
        } else {
            "pid $processId ($($proc.ProcessName))"
        }
    }

    return ($details -join "; ")
}

function Get-DevEnvFileValue {
    param(
        [Parameter(Mandatory)]
        [string]$EnvFile,
        [Parameter(Mandatory)]
        [string]$Key
    )

    if (-not (Test-Path $EnvFile)) { return $null }

    foreach ($line in Get-Content $EnvFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        if ($trimmed -match "^\s*$([regex]::Escape($Key))\s*=\s*(.+?)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }

    return $null
}

function Start-DevDetachedProcess {
    param(
        [Parameter(Mandatory)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory)]
        [string]$LogFile,
        [Parameter(Mandatory)]
        [string]$FilePath,
        [Parameter(Mandatory)]
        [string[]]$ArgumentList
    )

    $stderrLog = [System.IO.Path]::ChangeExtension($LogFile, ".err.log")
    Start-Process -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden
}

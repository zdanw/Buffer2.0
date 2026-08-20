$script:DevRootDir = Split-Path -Parent $PSScriptRoot
$script:DevStateDir = Join-Path $DevRootDir ".dev"
$script:DevBackendDir = Join-Path $DevRootDir "backend"
$script:DevFrontendDir = Join-Path $DevRootDir "frontend"

New-Item -ItemType Directory -Force -Path $DevStateDir | Out-Null

function Get-DevPortPids([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Get-DevProcessTreePids([int[]]$RootPids) {
    $roots = @($RootPids | Where-Object { $_ -and $_ -gt 0 } | Select-Object -Unique)
    if ($roots.Count -eq 0) { return @() }

    $all = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($root in $roots) { [void]$all.Add([int]$root) }

    $procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($proc in $procs) {
            $processId = [int]$proc.ProcessId
            $parentId = [int]$proc.ParentProcessId
            if ($all.Contains($parentId) -and -not $all.Contains($processId)) {
                [void]$all.Add($processId)
                $changed = $true
            }
        }
    }

    # uvicorn --reload orphans can keep serving after the listen PID is dead;
    # their cmdline still references parent_pid=<listenPid>.
    $parentPattern = ($roots | ForEach-Object { [regex]::Escape([string]$_) }) -join "|"
    foreach ($proc in $procs) {
        if ($proc.CommandLine -and $proc.CommandLine -match "parent_pid=($parentPattern)\b") {
            [void]$all.Add([int]$proc.ProcessId)
        }
    }

    return @($all)
}

function Stop-DevPort([int]$Port) {
    $listenPids = @(Get-DevPortPids $Port)
    $pids = @(Get-DevProcessTreePids $listenPids)
    if ($pids.Count -eq 0) { return $false }

    foreach ($processId in $pids) {
        # /T kills children even when the listen PID is already a Windows ghost entry.
        # Use cmd redirection so a missing PID does not throw under ErrorActionPreference=Stop.
        cmd.exe /c "taskkill /PID $processId /T /F >nul 2>&1" | Out-Null
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Milliseconds 400
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

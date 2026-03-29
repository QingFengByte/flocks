$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

function Stop-PortProcess {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if (-not $connections) {
        return
    }

    $processIds = $connections |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -and $_ -gt 0 }

    foreach ($processId in $processIds) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Warn "Stopped process on port $Port (PID: $processId)"
        } catch {
            Write-Warn ("Failed to stop PID {0} on port {1}: {2}" -f $processId, $Port, $_.Exception.Message)
        }
    }
}

function Test-HttpHealth {
    param(
        [string]$PythonExe,
        [string[]]$Urls
    )

    foreach ($url in $Urls) {
        try {
            $healthArgs = @(
                "-c",
                "import sys, urllib.request; url = sys.argv[1]; code = urllib.request.urlopen(url, timeout=2).getcode(); raise SystemExit(0 if 200 <= code < 300 else 1)",
                $url
            )

            $null = & $PythonExe @healthArgs 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $true
            }
        } catch {
        }
    }

    return $false
}

Write-Info "Starting Flocks production environment..."

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$webuiDir = Join-Path $projectRoot "webui"
$distDir = Join-Path $webuiDir "dist"
$logsDir = Join-Path $projectRoot "logs"
$backendStdout = Join-Path $logsDir "flocks-backend.out.log"
$backendStderr = Join-Path $logsDir "flocks-backend.err.log"
$frontendStdout = Join-Path $logsDir "webui-preview.out.log"
$frontendStderr = Join-Path $logsDir "webui-preview.err.log"
$backendPidFile = Join-Path $logsDir "backend.pid"
$frontendPidFile = Join-Path $logsDir "frontend.pid"

if (-not (Test-Path $pythonExe)) {
    Write-Fail "Python venv not found: $pythonExe"
    Write-Host "Run 'uv sync --group dev' or create the virtual environment first."
    exit 1
}

if (-not (Test-Path (Join-Path $webuiDir "package.json"))) {
    Write-Fail "WebUI directory is missing package.json: $webuiDir"
    exit 1
}

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

Write-Info "Cleaning existing processes..."
Stop-PortProcess -Port 8000
Stop-PortProcess -Port 5173
Start-Sleep -Seconds 1

Write-Info "Building WebUI frontend..."
Push-Location $webuiDir
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

if (-not (Test-Path $distDir)) {
    Write-Fail "Frontend build failed: webui/dist does not exist."
    exit 1
}

Write-Success "Frontend build completed."

Write-Info "Starting backend service on port 8000..."
$backendArgs = @(
    "-m", "uvicorn",
    "flocks.server.app:app",
    "--host", "127.0.0.1",
    "--port", "8000"
)

$backendProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $backendArgs `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendStdout `
    -RedirectStandardError $backendStderr `
    -PassThru

Set-Content -Path $backendPidFile -Value $backendProcess.Id
Write-Warn "Backend PID: $($backendProcess.Id)"

$backendReady = $false
Write-Info "Waiting for backend startup..."
for ($attempt = 1; $attempt -le 15; $attempt++) {
    Start-Sleep -Seconds 2

    if (Test-HttpHealth -PythonExe $pythonExe -Urls @("http://localhost:8000/api/health", "http://localhost:8000/health")) {
        $backendReady = $true
        break
    }
}

if (-not $backendReady) {
    Write-Fail "Backend failed health check within 30 seconds."
    if (Test-Path $backendStdout) {
        Write-Host ""
        Write-Host "Backend stdout tail:"
        Get-Content -Path $backendStdout -Tail 20
    }
    if (Test-Path $backendStderr) {
        Write-Host ""
        Write-Host "Backend stderr tail:"
        Get-Content -Path $backendStderr -Tail 20
    }
    Stop-PortProcess -Port 8000
    exit 1
}

Write-Success "Backend started successfully."
Write-Warn "Backend stdout log: $backendStdout"
Write-Warn "Backend stderr log: $backendStderr"

Write-Info "Starting WebUI preview on port 5173..."
$frontendArgs = @(
    "run", "preview", "--",
    "--host", "127.0.0.1",
    "--port", "5173"
)

$frontendProcess = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList $frontendArgs `
    -WorkingDirectory $webuiDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $frontendStdout `
    -RedirectStandardError $frontendStderr `
    -PassThru

Set-Content -Path $frontendPidFile -Value $frontendProcess.Id
Write-Warn "Frontend PID: $($frontendProcess.Id)"

$frontendReady = $false
Write-Info "Waiting for frontend startup..."
for ($attempt = 1; $attempt -le 10; $attempt++) {
    Start-Sleep -Seconds 2

    if (Test-HttpHealth -PythonExe $pythonExe -Urls @("http://localhost:5173/")) {
        $frontendReady = $true
        break
    }
}

if (-not $frontendReady) {
    Write-Fail "Frontend failed health check within 20 seconds."
    if (Test-Path $frontendStdout) {
        Write-Host ""
        Write-Host "Frontend stdout tail:"
        Get-Content -Path $frontendStdout -Tail 20
    }
    if (Test-Path $frontendStderr) {
        Write-Host ""
        Write-Host "Frontend stderr tail:"
        Get-Content -Path $frontendStderr -Tail 20
    }
    Stop-PortProcess -Port 5173
    Stop-PortProcess -Port 8000
    exit 1
}

Write-Success "Frontend started successfully."
Write-Warn "Frontend stdout log: $frontendStdout"
Write-Warn "Frontend stderr log: $frontendStderr"

Write-Success "Flocks production environment started."
Write-Warn "Backend URL: http://localhost:8000"
Write-Warn "Frontend URL: http://localhost:5173"
Write-Warn ("Stop services: Stop-Process -Id {0},{1} -Force" -f $backendProcess.Id, $frontendProcess.Id)

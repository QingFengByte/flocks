param(
    [ValidateSet("start", "stop", "restart", "status", "logs", "")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Add-PathEntry {
    param([string]$PathEntry)

    if ([string]::IsNullOrWhiteSpace($PathEntry) -or -not (Test-Path $PathEntry)) {
        return
    }

    $pathItems = $env:Path -split ";"
    if ($pathItems -contains $PathEntry) {
        return
    }

    $env:Path = "$PathEntry;$env:Path"
}

function Refresh-Path {
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:Path = "$userPath;$machinePath"

    $uvBin = Join-Path $HOME ".local\bin"
    $cargoBin = Join-Path $HOME ".cargo\bin"
    $bunBin = Join-Path $HOME ".bun\bin"
    $windowsAppsBin = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"

    foreach ($pathEntry in @($uvBin, $cargoBin, $bunBin, $windowsAppsBin)) {
        Add-PathEntry $pathEntry
    }
}

function Main {
    Refresh-Path

    $flocksCommand = Get-Command flocks -ErrorAction SilentlyContinue
    if ($flocksCommand) {
        & $flocksCommand.Source $Action
        exit $LASTEXITCODE
    }

    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand) {
        Push-Location $RootDir
        try {
            & $uvCommand.Source run flocks $Action
            exit $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "[flocks] error: 未检测到 flocks 或 uv，请先执行安装脚本后重试。" -ForegroundColor Red
    Write-Host "[flocks] 可用命令："
    Write-Host "  flocks start"
    Write-Host "  flocks stop"
    Write-Host "  flocks restart"
    Write-Host "  flocks status"
    Write-Host "  flocks logs"
    exit 1
}

Main

param(
    [switch]$InstallTui,
    [string]$Version = $env:VERSION,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$RepoSlug = if ([string]::IsNullOrWhiteSpace($env:FLOCKS_REPO_SLUG)) { "AgentFlocks/Flocks" } else { $env:FLOCKS_REPO_SLUG }
$DefaultBranch = if ([string]::IsNullOrWhiteSpace($env:FLOCKS_DEFAULT_BRANCH)) { "main" } else { $env:FLOCKS_DEFAULT_BRANCH }
$DefaultInstallDir = Join-Path (Get-Location) "flocks"
$InstallDir = if ([string]::IsNullOrWhiteSpace($env:FLOCKS_INSTALL_DIR)) { $DefaultInstallDir } else { $env:FLOCKS_INSTALL_DIR }

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $DefaultBranch
}

function Write-Info {
    param([string]$Message)
    Write-Host "[flocks-bootstrap] $Message"
}

function Fail {
    param([string]$Message)
    Write-Host "[flocks-bootstrap] error: $Message" -ForegroundColor Red
    exit 1
}

function Show-Usage {
    Write-Host "Usage: install.ps1 [-InstallTui] [-Version <tag-or-branch>] [-Help]"
    Write-Host ""
    Write-Host "Bootstrap installer for Flocks."
    Write-Host "This script downloads the GitHub source archive to a temporary directory,"
    Write-Host "copies it to a persistent install location, and delegates to scripts/install.ps1."
    Write-Host "By default it creates a 'flocks' subdirectory under the current directory."
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -InstallTui          Also install TUI dependencies."
    Write-Host "  -Version <value>     Install from a Git tag or branch. Defaults to: $DefaultBranch"
    Write-Host "  -Help                Show this help message."
    Write-Host ""
    Write-Host "Environment variables:"
    Write-Host "  VERSION                Same as -Version."
Write-Host "  FLOCKS_INSTALL_DIR     Override persistent install location. Defaults to: $InstallDir"
    Write-Host "  FLOCKS_REPO_SLUG       Override GitHub repo, e.g. owner/repo."
    Write-Host "  FLOCKS_DEFAULT_BRANCH  Override default branch. Defaults to: $DefaultBranch"
}

function New-TemporaryDirectory {
    $basePath = [System.IO.Path]::GetTempPath()
    $name = [System.IO.Path]::GetRandomFileName()
    $path = Join-Path $basePath $name
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
}

function Get-ArchiveCandidateUrls {
    $baseUrl = "https://github.com/$RepoSlug/archive/refs"

    if ($Version -eq $DefaultBranch) {
        return @("$baseUrl/heads/$Version.zip")
    }

    return @(
        "$baseUrl/tags/$Version.zip",
        "$baseUrl/heads/$Version.zip"
    )
}

function Download-Archive {
    param([string]$ArchivePath)

    $lastErrorMessage = $null

    foreach ($url in Get-ArchiveCandidateUrls) {
        Write-Info "尝试下载源码包: $url"
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $ArchivePath
            return $url
        }
        catch {
            $lastErrorMessage = $_.Exception.Message
        }
    }

    Fail "无法从 GitHub 下载版本 '$Version' 的源码包。最后一次错误: $lastErrorMessage"
}

function Resolve-ProjectRoot {
    param([string]$TempDir)

    $candidate = Get-ChildItem -Path $TempDir -Directory | Where-Object {
        Test-Path (Join-Path $_.FullName "scripts\install.ps1")
    } | Select-Object -First 1

    if ($candidate) {
        return $candidate.FullName
    }

    return $null
}

function Main {
    if ($Help) {
        Show-Usage
        return
    }

    $tempDir = New-TemporaryDirectory
    $archivePath = Join-Path $tempDir "flocks.zip"

    try {
        Write-Info "仓库: $RepoSlug"
        Write-Info "版本: $Version"
        Write-Info "临时目录: $tempDir"

        $downloadUrl = Download-Archive -ArchivePath $archivePath

        Write-Info "解压源码包..."
        Expand-Archive -Path $archivePath -DestinationPath $tempDir -Force

        $projectRoot = Resolve-ProjectRoot -TempDir $tempDir
        if ([string]::IsNullOrWhiteSpace($projectRoot)) {
            Fail "解压完成，但未找到 scripts\install.ps1。"
        }

        $installParent = Split-Path -Parent $InstallDir
        if (-not [string]::IsNullOrWhiteSpace($installParent)) {
            New-Item -ItemType Directory -Path $installParent -Force | Out-Null
        }
        if (Test-Path $InstallDir) {
            Remove-Item -Path $InstallDir -Recurse -Force
        }
        Copy-Item -Path $projectRoot -Destination $InstallDir -Recurse -Force

        $installerPath = Join-Path $InstallDir "scripts\install.ps1"
        Write-Info "下载来源: $downloadUrl"
        Write-Info "安装目录: $InstallDir"
        Write-Info "转调安装脚本: $installerPath"

        $installerArgs = @()
        if ($InstallTui) {
            $installerArgs += "-InstallTui"
        }

        & $installerPath @installerArgs
    }
    finally {
        if (-not [string]::IsNullOrWhiteSpace($tempDir) -and (Test-Path $tempDir)) {
            Remove-Item -Path $tempDir -Recurse -Force
        }
    }
}

Main

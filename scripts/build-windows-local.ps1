param(
  [string]$OutputDir = "$env:USERPROFILE\Desktop\fpi-agent-windows-output",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "=== $Message ===" -ForegroundColor Cyan
}

function Test-Command {
  param([string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-WingetInstall {
  param(
    [string]$Id,
    [string[]]$ExtraArgs = @()
  )

  if ($SkipInstall) {
    throw "Missing dependency $Id and -SkipInstall was supplied."
  }
  if (-not (Test-Command "winget")) {
    throw "winget is not available. Install Python 3.12, Node.js 20+, Rust, Visual Studio Build Tools C++ workload, WebView2 Runtime, and NSIS manually."
  }

  Write-Step "Installing $Id"
  $args = @(
    "install",
    "--id", $Id,
    "-e",
    "--accept-source-agreements",
    "--accept-package-agreements"
  ) + $ExtraArgs
  & winget @args
  if ($LASTEXITCODE -ne 0) {
    throw "winget install failed for $Id with exit code $LASTEXITCODE"
  }
}

function Ensure-Command {
  param(
    [string]$Command,
    [string]$WingetId,
    [string[]]$ExtraArgs = @()
  )

  if (-not (Test-Command $Command)) {
    Invoke-WingetInstall -Id $WingetId -ExtraArgs $ExtraArgs
  }
}

function Refresh-BuildPath {
  $paths = @(
    "$env:USERPROFILE\.cargo\bin",
    "$env:LOCALAPPDATA\Programs\Python\Python312",
    "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
    "$env:ProgramFiles\nodejs",
    "${env:ProgramFiles(x86)}\NSIS",
    "$env:ProgramFiles\NSIS"
  )
  $env:PATH = (($paths | Where-Object { $_ -and (Test-Path $_) }) -join ";") + ";" + $env:PATH
}

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory
  )

  Write-Host "> $FilePath $($ArgumentList -join ' ')" -ForegroundColor DarkGray
  Push-Location $WorkingDirectory
  try {
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
      throw "$FilePath failed with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Write-Step "Repository"
Write-Host $repoRoot

Write-Step "Checking build dependencies"
Refresh-BuildPath
Ensure-Command -Command "py" -WingetId "Python.Python.3.12"
Ensure-Command -Command "node" -WingetId "OpenJS.NodeJS.LTS"
Ensure-Command -Command "npm" -WingetId "OpenJS.NodeJS.LTS"
Ensure-Command -Command "rustup" -WingetId "Rustlang.Rustup"
Ensure-Command -Command "cargo" -WingetId "Rustlang.Rustup"
Ensure-Command -Command "makensis" -WingetId "NSIS.NSIS"

if (-not (Test-Command "link.exe")) {
  Invoke-WingetInstall -Id "Microsoft.VisualStudio.2022.BuildTools" -ExtraArgs @(
    "--override",
    "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
  )
}

if (-not (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\*" -ErrorAction SilentlyContinue | Where-Object { $_.name -like "*WebView2*" })) {
  Invoke-WingetInstall -Id "Microsoft.EdgeWebView2Runtime"
}

Refresh-BuildPath

Write-Step "Tool versions"
Invoke-Checked -FilePath "node" -ArgumentList @("--version") -WorkingDirectory $repoRoot
Invoke-Checked -FilePath "npm" -ArgumentList @("--version") -WorkingDirectory $repoRoot
Invoke-Checked -FilePath "rustup" -ArgumentList @("default", "stable") -WorkingDirectory $repoRoot
Invoke-Checked -FilePath "cargo" -ArgumentList @("--version") -WorkingDirectory $repoRoot
Invoke-Checked -FilePath "py" -ArgumentList @("-3.12", "--version") -WorkingDirectory $repoRoot

Write-Step "Installing JavaScript dependencies"
Invoke-Checked -FilePath "npm" -ArgumentList @("install", "--legacy-peer-deps") -WorkingDirectory $repoRoot
Invoke-Checked -FilePath "npm" -ArgumentList @("ci", "--legacy-peer-deps") -WorkingDirectory (Join-Path $repoRoot "frontend")
Invoke-Checked -FilePath "npm" -ArgumentList @("install") -WorkingDirectory (Join-Path $repoRoot "admin-frontend")
Invoke-Checked -FilePath "npm" -ArgumentList @("install") -WorkingDirectory (Join-Path $repoRoot "desktop-tauri")

Write-Step "Building admin console"
Invoke-Checked -FilePath "npm" -ArgumentList @("run", "build") -WorkingDirectory (Join-Path $repoRoot "admin-frontend")

Write-Step "Building desktop frontend"
$env:DESKTOP_BUILD = "true"
$env:NEXT_PUBLIC_DESKTOP_BUILD = "true"
Invoke-Checked -FilePath "npm" -ArgumentList @("run", "build") -WorkingDirectory (Join-Path $repoRoot "frontend")

Write-Step "Building Python backend"
$backendDir = Join-Path $repoRoot "backend"
$venvPython = Join-Path $backendDir "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Invoke-Checked -FilePath "py" -ArgumentList @("-3.12", "-m", "venv", "venv") -WorkingDirectory $backendDir
}
Invoke-Checked -FilePath $venvPython -ArgumentList @("-m", "pip", "install", "--upgrade", "pip") -WorkingDirectory $backendDir
Invoke-Checked -FilePath $venvPython -ArgumentList @("-m", "pip", "install", "-r", "requirements.txt", "pyinstaller") -WorkingDirectory $backendDir
Invoke-Checked -FilePath $venvPython -ArgumentList @("-m", "PyInstaller", "openyak.spec", "--noconfirm") -WorkingDirectory $backendDir

Write-Step "Verifying backend bundle"
Invoke-Checked -FilePath "node" -ArgumentList @("scripts\verify-bundle.mjs", "backend\dist\openyak-backend") -WorkingDirectory $repoRoot

Write-Step "Downloading bundled Node.js runtime"
Invoke-Checked -FilePath $venvPython -ArgumentList @("scripts\download_node.py") -WorkingDirectory $backendDir

Write-Step "Building Tauri Windows installer"
$tauriConfig = '{"build":{"beforeBuildCommand":""},"bundle":{"targets":["nsis"]}}'
Invoke-Checked -FilePath "npx" -ArgumentList @("@tauri-apps/cli", "build", "--config", $tauriConfig) -WorkingDirectory (Join-Path $repoRoot "desktop-tauri")

Write-Step "Collecting installer"
$installerDir = Join-Path $repoRoot "desktop-tauri\src-tauri\target\release\bundle\nsis"
$installer = Get-ChildItem $installerDir -Filter "*.exe" -ErrorAction Stop | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) {
  throw "No NSIS installer was produced in $installerDir"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$destination = Join-Path $OutputDir $installer.Name
Copy-Item $installer.FullName $destination -Force

Write-Step "Done"
Write-Host "Windows installer: $destination" -ForegroundColor Green

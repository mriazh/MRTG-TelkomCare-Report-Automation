param (
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if (-not (Test-Path ".venv312")) {
    Write-Host "Error: .venv312 does not exist." -ForegroundColor Red
    exit 1
}

$PyInstallerPath = ".venv312\Scripts\pyinstaller.exe"
if (-not (Test-Path $PyInstallerPath)) {
    Write-Host "Error: pyinstaller is missing." -ForegroundColor Red
    Write-Host "Please run: .venv312\Scripts\python -m pip install pyinstaller" -ForegroundColor Yellow
    exit 1
}

if ($Clean) {
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

Write-Host "Building MRTG-TelkomCare.exe..." -ForegroundColor Cyan
& $PyInstallerPath mrtg_telkomcare.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Creating runtime data folders..." -ForegroundColor Cyan

# Create empty runtime directories
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\config" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\data\MRTG-Data" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\reports" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\state" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\screenshots" | Out-Null

# Copy only safe config files
$safeConfigs = @(
    "config\.env.example",
    "config\list_mrtg_targets.csv",
    "config\list_mrtg_data_position.txt",
    "config\list_mrtg_data_position_img_only.txt"
)
foreach ($file in $safeConfigs) {
    if (Test-Path $file) {
        Copy-Item -Force $file "dist\MRTG-TelkomCare\config\"
    }
}

# Copy templates if they exist
if (Test-Path "templates") {
    Copy-Item -Recurse -Force "templates" "dist\MRTG-TelkomCare\"
}

# Copy assets if they exist
if (Test-Path "assets") {
    Copy-Item -Recurse -Force "assets" "dist\MRTG-TelkomCare\"
}

Write-Host "Build complete! Output location:" -ForegroundColor Green
Write-Host "dist\MRTG-TelkomCare\MRTG-TelkomCare.exe" -ForegroundColor Green

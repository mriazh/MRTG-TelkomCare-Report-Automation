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

Write-Host "Build complete! Output location:" -ForegroundColor Green
Write-Host "dist\MRTG-TelkomCare\MRTG-TelkomCare.exe" -ForegroundColor Green

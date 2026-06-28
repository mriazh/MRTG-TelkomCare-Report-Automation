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
& $PyInstallerPath -y mrtg_telkomcare.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Verifying required runtime files..." -ForegroundColor Cyan
$InternalDir = "dist\MRTG-TelkomCare\_internal"
$RequiredFiles = @(
    "python312.dll",
    "python3.dll",
    "base_library.zip"
)

# Workaround for missing base_library.zip
$BaseLibDist = Join-Path $InternalDir "base_library.zip"
$BaseLibBuild = "build\mrtg_telkomcare\base_library.zip"
if (-not (Test-Path $BaseLibDist)) {
    if (Test-Path $BaseLibBuild) {
        Write-Host "Workaround: Copying base_library.zip from build directory..." -ForegroundColor Yellow
        if (-not (Test-Path $InternalDir)) {
            New-Item -ItemType Directory -Force -Path $InternalDir | Out-Null
        }
        Copy-Item -Path $BaseLibBuild -Destination $BaseLibDist -Force
    }
}

$MissingFiles = $false
foreach ($file in $RequiredFiles) {
    $FilePath = Join-Path $InternalDir $file
    if (-not (Test-Path $FilePath)) {
        Write-Host "Error: Required runtime file is missing: $FilePath" -ForegroundColor Red
        $MissingFiles = $true
    }
}

if ($MissingFiles) {
    Write-Host "Build failed due to missing runtime files." -ForegroundColor Red
    exit 1
}


Write-Host "Creating runtime data folders..." -ForegroundColor Cyan

# Create empty runtime directories
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\config" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\data\MRTG-Data" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\reports" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\state" | Out-Null
New-Item -ItemType Directory -Force -Path "dist\MRTG-TelkomCare\output\screenshots" | Out-Null

# Explicitly ensure paddlex configs exist for OCR
$PaddlexConfigsSrc = ".venv312\Lib\site-packages\paddlex\configs"
$PaddlexConfigsDst = "dist\MRTG-TelkomCare\_internal\paddlex\configs"
if (Test-Path $PaddlexConfigsSrc) {
    if (-not (Test-Path $PaddlexConfigsDst)) {
        New-Item -ItemType Directory -Force -Path $PaddlexConfigsDst | Out-Null
    }
    Copy-Item -Path "$PaddlexConfigsSrc\*" -Destination $PaddlexConfigsDst -Recurse -Force
}

# Explicitly ensure paddle native libs exist for OCR
$PaddleLibsSrc = ".venv312\Lib\site-packages\paddle\libs"
$PaddleLibsDst = "dist\MRTG-TelkomCare\_internal\paddle\libs"
if (Test-Path $PaddleLibsSrc) {
    if (-not (Test-Path $PaddleLibsDst)) {
        New-Item -ItemType Directory -Force -Path $PaddleLibsDst | Out-Null
    }
    Copy-Item -Path "$PaddleLibsSrc\*" -Destination $PaddleLibsDst -Recurse -Force
}

$MklmlPath = Join-Path $PaddleLibsDst "mklml.dll"
if (-not (Test-Path $MklmlPath)) {
    Write-Host "Error: Paddle native lib mklml.dll is missing from $MklmlPath" -ForegroundColor Red
    exit 1
}

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

Write-Host "Verifying safe release assets..." -ForegroundColor Cyan
$RequiredReleaseFiles = @(
    "config\.env.example",
    "config\list_mrtg_targets.csv",
    "config\list_mrtg_data_position.txt",
    "config\list_mrtg_data_position_img_only.txt",
    "templates\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
    "templates\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
    "assets\app_icon.ico",
    "_internal\paddlex\configs\pipelines\OCR.yaml",
    "_internal\paddle\libs\mklml.dll"
)

$MissingReleaseFiles = $false
foreach ($file in $RequiredReleaseFiles) {
    $FilePath = Join-Path "dist\MRTG-TelkomCare" $file
    if (-not (Test-Path $FilePath)) {
        Write-Host "Error: Required release file is missing: $FilePath" -ForegroundColor Red
        $MissingReleaseFiles = $true
    }
}

if ($MissingReleaseFiles) {
    Write-Host "Build failed due to missing safe release assets. Please check copy permissions." -ForegroundColor Red
    exit 1
}

Write-Host "Build complete! Output location:" -ForegroundColor Green
Write-Host "dist\MRTG-TelkomCare\MRTG-TelkomCare.exe" -ForegroundColor Green

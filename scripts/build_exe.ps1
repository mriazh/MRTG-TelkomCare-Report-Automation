param (
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$VenvDir = Join-Path $RepoRoot ".venv312"
$PyInstallerPath = Join-Path $VenvDir "Scripts\pyinstaller.exe"
$SpecFile = Join-Path $RepoRoot "mrtg_telkomcare.spec"
$DistDir = Join-Path $RepoRoot "dist"
$ExpectedExeDir = Join-Path $DistDir "MRTG-TelkomCare"
$ExpectedExe = Join-Path $ExpectedExeDir "MRTG-TelkomCare.exe"

# Fail Fast: Prerequisite checks
if (-not (Test-Path $VenvDir)) {
    Write-Host "Error: .venv312 does not exist at $VenvDir." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $PyInstallerPath)) {
    Write-Host "Error: pyinstaller is missing at $PyInstallerPath." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $SpecFile)) {
    Write-Host "Error: mrtg_telkomcare.spec is missing at $SpecFile." -ForegroundColor Red
    exit 1
}

if (Test-Path (Join-Path $RepoRoot "build")) { Remove-Item -Recurse -Force (Join-Path $RepoRoot "build") }
if (Test-Path (Join-Path $RepoRoot "dist")) { Remove-Item -Recurse -Force (Join-Path $RepoRoot "dist") }
if (Test-Path (Join-Path $RepoRoot "staging")) { Remove-Item -Recurse -Force (Join-Path $RepoRoot "staging") }

Write-Host "Building MRTG-TelkomCare.exe using $SpecFile..." -ForegroundColor Cyan
& $PyInstallerPath -y $SpecFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# Immediate Validation
if (-not (Test-Path $ExpectedExe)) {
    Write-Host "Error: Expected executable not found at $ExpectedExe." -ForegroundColor Red
    exit 1
}
Write-Host "Build verified. Executable found at $ExpectedExe" -ForegroundColor Green

Write-Host "Verifying required runtime files..." -ForegroundColor Cyan
$InternalDir = Join-Path $ExpectedExeDir "_internal"
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
    "config\list_mrtg_targets.example.csv",
    "config\list_mrtg_data_position.txt",
    "config\list_mrtg_data_position_img_only.txt"
)
foreach ($file in $safeConfigs) {
    if (Test-Path $file) {
        Copy-Item -Force $file "dist\MRTG-TelkomCare\config\"
    }
}

# Copy approved release templates and assets only
$ApprovedReleaseFiles = @(
    "config\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
    "config\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
    "assets\app_icon.ico"
)
foreach ($file in $ApprovedReleaseFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "Error: Approved release file is missing: $file" -ForegroundColor Red
        exit 1
    }
    $destination = Join-Path "dist\MRTG-TelkomCare" $file
    $destinationDir = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    Copy-Item -Force $file $destination
}

Write-Host "Verifying safe release assets..." -ForegroundColor Cyan
$RequiredReleaseFiles = @(
    "config\.env.example",
    "config\list_mrtg_targets.example.csv",
    "config\list_mrtg_data_position.txt",
    "config\list_mrtg_data_position_img_only.txt",
    "config\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
    "config\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
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

# Generate manifest of all files to be packaged
Write-Host "Generating packaging manifest..." -ForegroundColor Cyan
$DistAppDir = "dist\MRTG-TelkomCare"
$ManifestPath = Join-Path $DistAppDir "packaging.manifest"
$DistAppDirAbs = (Resolve-Path $DistAppDir).Path
$ForbiddenFiles = @(
    "config\.env",
    "config\SID-MRTG.txt",
    "config\GRAPH-TITLE-MRTG.txt",
    "config\report-items.txt",
    "config\list_mrtg_targets.csv"
)
$ForbiddenDirs = @(
    "data",
    "output"
)

$AllFiles = Get-ChildItem -Path $DistAppDir -Recurse -File
$ManifestEntries = @()
foreach ($file in $AllFiles) {
    $relPath = $file.FullName.Substring($DistAppDirAbs.Length + 1).Replace('\', '/')

    # Check if file is forbidden
    $isForbidden = $false
    foreach ($forbidden in $ForbiddenFiles) {
        if ($relPath -ieq $forbidden) {
            $isForbidden = $true
            break
        }
    }
    if ($isForbidden) { continue }

    foreach ($forbiddenDir in $ForbiddenDirs) {
        if ($relPath.StartsWith($forbiddenDir + '/')) {
            $isForbidden = $true
            break
        }
    }
    if ($isForbidden) { continue }

    # Also skip the manifest itself
    if ($relPath -ieq 'packaging.manifest') { continue }

    $ManifestEntries += $relPath
}

# Sort manifest entries for reproducibility
$ManifestEntries = $ManifestEntries | Sort-Object
$ManifestEntries | Set-Content -Path $ManifestPath -Encoding UTF8
Write-Host "Manifest generated at $ManifestPath with $($ManifestEntries.Count) entries" -ForegroundColor Green

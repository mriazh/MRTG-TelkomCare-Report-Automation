param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$AppInfoPath = Join-Path $RootDir "src\mrtg_automation\app_info.py"
if (-not (Test-Path $AppInfoPath)) {
    Write-Host "Error: Cannot find $AppInfoPath" -ForegroundColor Red
    exit 1
}

$AppVersion = $null
$Lines = Get-Content $AppInfoPath
foreach ($Line in $Lines) {
    if ($Line -match 'APP_VERSION\s*=\s*"([^"]+)"') {
        $AppVersion = $matches[1]
        break
    }
}

if (-not $AppVersion) {
    Write-Host "Error: Failed to parse APP_VERSION from $AppInfoPath" -ForegroundColor Red
    exit 1
}

$ExePath = Join-Path $RootDir "dist\MRTG-TelkomCare\MRTG-TelkomCare.exe"
if (-not (Test-Path $ExePath)) {
    Write-Host "Error: Cannot find $ExePath" -ForegroundColor Red
    Write-Host "Please build the EXE first using .\scripts\build_exe.ps1" -ForegroundColor Yellow
    exit 1
}

$DistAppDir = Join-Path $RootDir "dist\MRTG-TelkomCare"
$ManifestPath = Join-Path $DistAppDir "packaging.manifest"
if (-not (Test-Path $ManifestPath)) {
    Write-Host "Error: Packaging manifest not found at $ManifestPath" -ForegroundColor Red
    Write-Host "Please run build_exe.ps1 first to generate the manifest" -ForegroundColor Yellow
    exit 1
}

# Create clean staging directory for installer
$StagingDir = Join-Path $RootDir "staging\MRTG-TelkomCare-Installer"
if (Test-Path $StagingDir) {
    Remove-Item -Recurse -Force $StagingDir
}
New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

Write-Host "Populating clean installer staging directory from manifest..." -ForegroundColor Cyan

# Read manifest entries
$ManifestEntries = Get-Content $ManifestPath -Encoding UTF8

$MissingFiles = 0
foreach ($relPath in $ManifestEntries) {
    $srcPath = Join-Path $DistAppDir $relPath
    $dstPath = Join-Path $StagingDir $relPath

    if (-not (Test-Path $srcPath)) {
        Write-Host "Error: Required file missing from dist: $relPath" -ForegroundColor Red
        $MissingFiles++
        continue
    }

    $dstDir = Split-Path -Parent $dstPath
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    }
    Copy-Item -Path $srcPath -Destination $dstPath -Force
    Write-Host "  Copied: $relPath" -ForegroundColor Gray
}

if ($MissingFiles -gt 0) {
    Write-Host "Error: $MissingFiles required files missing from dist. Cannot create installer." -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

# Verify forbidden files are NOT in staging (should be excluded by manifest, but double-check)
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

$ForbiddenFound = 0
foreach ($file in $ForbiddenFiles) {
    $checkFile = Join-Path $StagingDir $file
    if (Test-Path $checkFile) {
        Write-Host "Error: Forbidden file found in staging: $file" -ForegroundColor Red
        $ForbiddenFound++
    }
}
foreach ($dir in $ForbiddenDirs) {
    $checkDir = Join-Path $StagingDir $dir
    if (Test-Path $checkDir) {
        $items = Get-ChildItem -Path $checkDir -Recurse -File
        if ($items.Count -gt 0) {
            Write-Host "Error: Forbidden files found in staging directory: $dir" -ForegroundColor Red
            $ForbiddenFound++
        }
    }
}

if ($ForbiddenFound -gt 0) {
    Write-Host "Error: $ForbiddenFound forbidden entries found in staging. Aborting." -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

# FINAL STAGING MANIFEST VALIDATION: reject any file not in the manifest
Write-Host "Validating staging manifest against generated manifest..." -ForegroundColor Cyan
$AllStagedFiles = Get-ChildItem -Path $StagingDir -Recurse -File
$StagingDirAbs = (Resolve-Path $StagingDir).Path
$ManifestViolations = 0
$ManifestSet = @{}
foreach ($entry in $ManifestEntries) {
    $ManifestSet[$entry] = $true
}
foreach ($file in $AllStagedFiles) {
    $relPath = $file.FullName.Substring($StagingDirAbs.Length + 1).Replace('\', '/')
    if (-not $ManifestSet.ContainsKey($relPath)) {
        Write-Host "Error: Staged file not in manifest: $relPath" -ForegroundColor Red
        $ManifestViolations++
    }
}

if ($ManifestViolations -gt 0) {
    Write-Host "Error: $ManifestViolations files in staging violate the manifest. Aborting." -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "Staging manifest validation passed." -ForegroundColor Green

# Check required files in staging
$RequiredDistFiles = @(
    "config\.env.example",
    "config\list_mrtg_targets.example.csv",
    "config\list_mrtg_data_position.txt",
    "config\list_mrtg_data_position_img_only.txt",
    "config\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
    "config\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
    "assets\app_icon.ico",
    "_internal\base_library.zip",
    "_internal\paddlex\configs\pipelines\OCR.yaml",
    "_internal\paddle\libs\mklml.dll"
)

$MissingDistFiles = 0
foreach ($req in $RequiredDistFiles) {
    $reqPath = Join-Path $StagingDir $req
    if (-not (Test-Path $reqPath)) {
        Write-Host "Error: Required file missing from staging: $reqPath" -ForegroundColor Red
        $MissingDistFiles++
    }
}

if ($MissingDistFiles -gt 0) {
    Write-Host "Error: Installer validation failed. Missing $MissingDistFiles required files." -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

$ReleaseDir = Join-Path $RootDir "release"
if (-not (Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
}

$InstallerName = "MRTG-TelkomCare-Setup-v$AppVersion.exe"
$ExpectedInstallerPath = Join-Path $ReleaseDir $InstallerName
if (Test-Path $ExpectedInstallerPath) {
    if ($Force) {
        Write-Host "Force specified: removing existing installer: $ExpectedInstallerPath" -ForegroundColor Yellow
        Remove-Item -Path $ExpectedInstallerPath -Force
    } else {
        Write-Host "Error: Output installer already exists at $ExpectedInstallerPath. Use -Force to overwrite." -ForegroundColor Red
        exit 1
    }
}

$ISCCPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$ISCC = $null
foreach ($Path in $ISCCPaths) {
    if (Test-Path $Path) {
        $ISCC = $Path
        break
    }
}

if ($null -eq $ISCC) {
    $ISCCCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($ISCCCmd) {
        $ISCC = $ISCCCmd.Source
    }
}

if ($null -eq $ISCC) {
    Write-Host "Error: Inno Setup 6 compiler (ISCC.exe) not found." -ForegroundColor Red
    Write-Host "Install Inno Setup 6 from https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
    exit 1
}

$IssPath = Join-Path $RootDir "installer\MRTG-TelkomCare.iss"
if (-not (Test-Path $IssPath)) {
    Write-Host "Error: Cannot find $IssPath" -ForegroundColor Red
    exit 1
}

# Calculate relative path from installer script to staging directory
$StagingRelativePath = "..\staging\MRTG-TelkomCare-Installer"

Write-Host "Building installer using $ISCC with staging source: $StagingRelativePath" -ForegroundColor Cyan
& $ISCC "/DMyAppVersion=$AppVersion" "/DSourceDir=$StagingRelativePath" $IssPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "Inno Setup compilation failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit $LASTEXITCODE
}

if (-not (Test-Path $ExpectedInstallerPath)) {
    Write-Host "Error: Expected installer output file not found at $ExpectedInstallerPath" -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

# Clean up staging
Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue

Write-Host "Success! Installer created in release\MRTG-TelkomCare-Setup-v$AppVersion.exe ($ExpectedInstallerPath)" -ForegroundColor Green
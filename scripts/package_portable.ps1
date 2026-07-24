param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$DistDir = Join-Path $RootDir "dist\MRTG-TelkomCare"
$ExePath = Join-Path $DistDir "MRTG-TelkomCare.exe"
$ManifestPath = Join-Path $DistDir "packaging.manifest"

if (-not (Test-Path $ExePath)) {
    Write-Host "Error: Cannot find $ExePath" -ForegroundColor Red
    Write-Host "Please build the EXE first using .\scripts\build_exe.ps1" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $ManifestPath)) {
    Write-Host "Error: Packaging manifest not found at $ManifestPath" -ForegroundColor Red
    Write-Host "Please run build_exe.ps1 first to generate the manifest" -ForegroundColor Yellow
    exit 1
}

# Read version - fail-fast if app_info.py missing or APP_VERSION not parseable
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

$ReleaseDir = Join-Path $RootDir "release"
if (-not (Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
}

$ZipName = "MRTG-TelkomCare-v$AppVersion-portable.zip"
$ExpectedZipPath = Join-Path $ReleaseDir $ZipName

if (Test-Path $ExpectedZipPath) {
    if ($Force) {
        Write-Host "Force specified: removing existing ZIP: $ExpectedZipPath" -ForegroundColor Yellow
        Remove-Item -Path $ExpectedZipPath -Force
    } else {
        Write-Host "Error: Output ZIP already exists at $ExpectedZipPath. Use -Force to overwrite." -ForegroundColor Red
        exit 1
    }
}

# Create clean staging directory for portable package
$StagingDir = Join-Path $RootDir "staging\MRTG-TelkomCare-Portable"
if (Test-Path $StagingDir) {
    Remove-Item -Recurse -Force $StagingDir
}
New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

Write-Host "Populating clean staging directory from manifest..." -ForegroundColor Cyan

# Read manifest entries
$ManifestEntries = Get-Content $ManifestPath -Encoding UTF8

$MissingFiles = 0
foreach ($relPath in $ManifestEntries) {
    $srcPath = Join-Path $DistDir $relPath
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
    Write-Host "Error: $MissingFiles required files missing from dist. Cannot create package." -ForegroundColor Red
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

# Check tar.exe availability - prefer the Windows libarchive tar in System32 over
# any GNU tar (e.g. Git Bash) that may appear first in PATH
$TarCmd = $null
foreach ($candidate in @("$env:WINDIR\System32\tar.exe", "$env:WINDIR\Sysnative\tar.exe")) {
    if (Test-Path $candidate) {
        $TarCmd = $candidate
        break
    }
}
if (-not $TarCmd) {
    $FoundTar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($FoundTar) {
        $TarCmd = $FoundTar.Source
    }
}
if (-not $TarCmd) {
    Write-Host "Error: tar.exe compiler / utility not found." -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "Creating portable ZIP: $ZipName using tar.exe from clean staging" -ForegroundColor Cyan
$StagingParentDir = Join-Path $RootDir "staging"
& $TarCmd -a -cf $ExpectedZipPath -C $StagingParentDir MRTG-TelkomCare-Portable
$TarExitCode = $LASTEXITCODE

if ($TarExitCode -ne 0 -or -not (Test-Path $ExpectedZipPath)) {
    Write-Host "Error: tar.exe failed to create ZIP." -ForegroundColor Red
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

# Verify ZIP contents
Write-Host "Validating ZIP contents..." -ForegroundColor Cyan
$BadZipEntries = 0
$AllZipContents = & $TarCmd -tf $ExpectedZipPath

foreach ($line in $AllZipContents) {
    $normalizedLine = $line.Replace("\", "/")
    if ($normalizedLine -match "^MRTG-TelkomCare-Portable/config/\.env$" -or
        $normalizedLine -match "MRTG-TelkomCare-Portable/config/SID-MRTG\.txt" -or
        $normalizedLine -match "MRTG-TelkomCare-Portable/config/GRAPH-TITLE-MRTG\.txt" -or
        $normalizedLine -match "MRTG-TelkomCare-Portable/config/report-items\.txt" -or
        $normalizedLine -match "MRTG-TelkomCare-Portable/config/list_mrtg_targets\.csv$" -or
        $normalizedLine -match "MRTG-TelkomCare-Portable/data/." -or
        $normalizedLine -match "MRTG-TelkomCare-Portable/output/.") {
        Write-Host "Error: Forbidden entry found in ZIP: $line" -ForegroundColor Red
        $BadZipEntries++
    }
}

if ($BadZipEntries -gt 0) {
    Write-Host "Error: ZIP validation failed. Found $BadZipEntries forbidden entries." -ForegroundColor Red
    Remove-Item -Path $ExpectedZipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

# Verify required files in ZIP
$RequiredZipFiles = @(
    "MRTG-TelkomCare-Portable/MRTG-TelkomCare.exe",
    "MRTG-TelkomCare-Portable/_internal/base_library.zip",
    "MRTG-TelkomCare-Portable/_internal/paddlex/configs/pipelines/OCR.yaml",
    "MRTG-TelkomCare-Portable/_internal/paddle/libs/mklml.dll",
    "MRTG-TelkomCare-Portable/config/.env.example",
    "MRTG-TelkomCare-Portable/config/list_mrtg_targets.example.csv",
    "MRTG-TelkomCare-Portable/config/list_mrtg_data_position.txt",
    "MRTG-TelkomCare-Portable/config/list_mrtg_data_position_img_only.txt",
    "MRTG-TelkomCare-Portable/templates/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
    "MRTG-TelkomCare-Portable/templates/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
    "MRTG-TelkomCare-Portable/assets/app_icon.ico"
)

$MissingZipFiles = 0
foreach ($req in $RequiredZipFiles) {
    $found = $false
    foreach ($line in $AllZipContents) {
        if ($line.Replace("\", "/") -eq $req) {
            $found = $true
            break
        }
    }
    if (-not $found) {
        Write-Host "Error: Required file MISSING from ZIP: $req" -ForegroundColor Red
        $MissingZipFiles++
    }
}

if ($MissingZipFiles -gt 0) {
    Write-Host "Error: ZIP validation failed. Missing $MissingZipFiles required entries." -ForegroundColor Red
    Remove-Item -Path $ExpectedZipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    exit 1
}

# Clean up staging
Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue

$FileInfo = Get-Item $ExpectedZipPath
$SizeMB = [math]::Round($FileInfo.Length / 1MB, 2)

Write-Host "ZIP validation passed. bad_entries=0, all required files present." -ForegroundColor Green
Write-Host "Success! Created $ExpectedZipPath ($SizeMB MB)" -ForegroundColor Green

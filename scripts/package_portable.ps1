param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$DistDir = Join-Path $RootDir "dist\MRTG-TelkomCare"
$ExePath = Join-Path $DistDir "MRTG-TelkomCare.exe"

if (-not (Test-Path $ExePath)) {
    Write-Host "Error: Cannot find $ExePath" -ForegroundColor Red
    Write-Host "Please build the EXE first using .\scripts\build_exe.ps1" -ForegroundColor Yellow
    exit 1
}

# Read version
$AppInfoPath = Join-Path $RootDir "src\mrtg_automation\app_info.py"
$AppVersion = "0.0.0"
if (Test-Path $AppInfoPath) {
    $Lines = Get-Content $AppInfoPath
    foreach ($Line in $Lines) {
        if ($Line -match 'APP_VERSION\s*=\s*"([^"]+)"') {
            $AppVersion = $matches[1]
            break
        }
    }
}

$ReleaseDir = Join-Path $RootDir "release"
if (-not (Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
}

$ZipName = "MRTG-TelkomCare-v$AppVersion-portable.zip"
$ZipPath = Join-Path $ReleaseDir $ZipName

if (Test-Path $ZipPath) {
    Remove-Item -Path $ZipPath -Force
}

# Validate dist does not contain forbidden files before zipping
$ForbiddenFiles = @(
    "config\.env",
    "config\SID-MRTG.txt",
    "config\GRAPH-TITLE-MRTG.txt",
    "config\report-items.txt"
)
$ForbiddenDirs = @(
    "data\MRTG-Data",
    "output"
)

foreach ($file in $ForbiddenFiles) {
    $checkFile = Join-Path $DistDir $file
    if (Test-Path $checkFile) {
        Write-Host "Error: Forbidden file found in dist before packaging: $file" -ForegroundColor Red
        Write-Host "Please clean dist or run build_exe.ps1 -Clean" -ForegroundColor Yellow
        exit 1
    }
}

foreach ($dir in $ForbiddenDirs) {
    $checkDir = Join-Path $DistDir $dir
    if (Test-Path $checkDir) {
        $items = Get-ChildItem -Path $checkDir -Recurse | Where-Object { -not $_.PSIsContainer }
        if ($items.Count -gt 0) {
            Write-Host "Error: Forbidden files found in directory before packaging: $dir" -ForegroundColor Red
            Write-Host "Please clean dist or run build_exe.ps1 -Clean" -ForegroundColor Yellow
            exit 1
        }
    }
}

Write-Host "Creating portable ZIP: $ZipName using tar.exe" -ForegroundColor Cyan
Set-Location $RootDir

$PaddleLibsSrc = ".venv312\Lib\site-packages\paddle\libs"
$PaddleLibsDst = "dist\MRTG-TelkomCare\_internal\paddle\libs"
if (Test-Path $PaddleLibsSrc) {
    if (-not (Test-Path $PaddleLibsDst)) {
        New-Item -ItemType Directory -Force -Path $PaddleLibsDst | Out-Null
    }
    Copy-Item -Path "$PaddleLibsSrc\*" -Destination $PaddleLibsDst -Recurse -Force
}

$CheckPath = "dist\MRTG-TelkomCare\_internal\paddle\libs\mklml.dll"
if (Test-Path $CheckPath) {
    Write-Host "Confirmed mklml.dll exists right before tar: $CheckPath" -ForegroundColor Green
} else {
    Write-Host "Warning: mklml.dll is MISSING before tar! Defender might have deleted it!" -ForegroundColor Red
}

$MaxRetries = 10
$RetryCount = 0
$ZipSuccess = $false

while (-not $ZipSuccess -and $RetryCount -lt $MaxRetries) {
    Write-Host "Creating portable ZIP: $ZipName using tar.exe (Attempt $($RetryCount + 1))" -ForegroundColor Cyan
    & tar.exe -a -cf $ZipPath -C dist MRTG-TelkomCare
    $TarExitCode = $LASTEXITCODE
    
    if ($TarExitCode -eq 0 -and (Test-Path $ZipPath)) {
        # Verify the tricky DLL is actually in the zip and wasn't skipped due to Defender lock
        $ZipCheck = & tar.exe -tf $ZipPath | Select-String "mklml.dll"
        if ($ZipCheck) {
            $ZipSuccess = $true
        } else {
            Write-Host "Warning: mklml.dll missing from zip (likely Defender lock). Retrying in 5 seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
            Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
            $RetryCount++
        }
    } else {
        Write-Host "Warning: tar.exe failed or zip not created. Retrying in 5 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        $RetryCount++
    }
}
Set-Location $RootDir

if (-not $ZipSuccess) {
    Write-Host "Error: tar.exe failed to create a valid zip containing all dependencies after $MaxRetries attempts." -ForegroundColor Red
    exit 1
}

$FileInfo = Get-Item $ZipPath
$SizeMB = [math]::Round($FileInfo.Length / 1MB, 2)

Write-Host "Validating ZIP contents for forbidden files..." -ForegroundColor Cyan
$BadZipEntries = 0
$AllZipContents = & tar.exe -tf $ZipPath

foreach ($line in $AllZipContents) {
    $normalizedLine = $line.Replace("\", "/")
    # Ignore directory entries (they end with '/') for data and output folders
    if ($normalizedLine -match "^MRTG-TelkomCare/config/\.env$" -or
        $normalizedLine -match "MRTG-TelkomCare/config/SID-MRTG\.txt" -or
        $normalizedLine -match "MRTG-TelkomCare/config/GRAPH-TITLE-MRTG\.txt" -or
        $normalizedLine -match "MRTG-TelkomCare/config/report-items\.txt" -or
        ($normalizedLine -match "MRTG-TelkomCare/data/MRTG-Data/.+" -and -not $normalizedLine.EndsWith("/")) -or
        ($normalizedLine -match "MRTG-TelkomCare/output/.+" -and -not $normalizedLine.EndsWith("/"))) {
        Write-Host "Error: Forbidden file found in ZIP: $line" -ForegroundColor Red
        $BadZipEntries++
    }
}

if ($BadZipEntries -gt 0) {
    Write-Host "Error: ZIP validation failed. Found $BadZipEntries forbidden entries." -ForegroundColor Red
    Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "Validating ZIP contents for required safe files..." -ForegroundColor Cyan
$RequiredZipFiles = @(
    "MRTG-TelkomCare/config/.env.example",
    "MRTG-TelkomCare/config/list_mrtg_targets.csv",
    "MRTG-TelkomCare/config/list_mrtg_data_position.txt",
    "MRTG-TelkomCare/config/list_mrtg_data_position_img_only.txt",
    "MRTG-TelkomCare/templates/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
    "MRTG-TelkomCare/templates/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
    "MRTG-TelkomCare/assets/app_icon.ico",
    "MRTG-TelkomCare/_internal/base_library.zip",
    "MRTG-TelkomCare/_internal/paddlex/configs/pipelines/OCR.yaml",
    "MRTG-TelkomCare/_internal/paddle/libs/mklml.dll"
)

$MissingZipFiles = 0
foreach ($req in $RequiredZipFiles) {
    # Replace backslashes since tar output will have forward slashes on Windows often, or we just string match
    $found = $false
    foreach ($line in $AllZipContents) {
        $normalizedLine = $line.Replace("\", "/")
        if ($normalizedLine -eq $req) {
            $found = $true
            break
        }
    }
    if (-not $found) {
        Write-Host "Error: Required safe file MISSING from ZIP: $req" -ForegroundColor Red
        $MissingZipFiles++
    }
}

if ($MissingZipFiles -gt 0) {
    Write-Host "Error: ZIP validation failed. Missing $MissingZipFiles required safe entries." -ForegroundColor Red
    Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "ZIP validation passed. bad_entries=0, all required files present." -ForegroundColor Green
Write-Host "Success! Created $ZipPath ($SizeMB MB)" -ForegroundColor Green

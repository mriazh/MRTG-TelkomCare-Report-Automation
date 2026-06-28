$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$AppInfoPath = Join-Path $RootDir "src\mrtg_automation\app_info.py"
$AppVersion = "1.0.0"
if (Test-Path $AppInfoPath) {
    $Lines = Get-Content $AppInfoPath
    foreach ($Line in $Lines) {
        if ($Line -match 'APP_VERSION\s*=\s*"([^"]+)"') {
            $AppVersion = $matches[1]
            break
        }
    }
}


$ExePath = Join-Path $RootDir "dist\MRTG-TelkomCare\MRTG-TelkomCare.exe"
if (-not (Test-Path $ExePath)) {
    Write-Host "Error: Cannot find $ExePath" -ForegroundColor Red
    Write-Host "Please build the EXE first using .\scripts\build_exe.ps1" -ForegroundColor Yellow
    exit 1
}

$DistAppDir = Join-Path $RootDir "dist\MRTG-TelkomCare"
$ForbiddenFiles = @(
    "config\.env",
    "config\SID-MRTG.txt",
    "config\GRAPH-TITLE-MRTG.txt",
    "config\report-items.txt"
)

foreach ($File in $ForbiddenFiles) {
    $FilePath = Join-Path $DistAppDir $File
    if (Test-Path $FilePath) {
        Write-Host "Error: Forbidden file found in dist: $File" -ForegroundColor Red
        exit 1
    }
}

$DataDir = Join-Path $DistAppDir "data"
if (Test-Path $DataDir) {
    $DataFiles = Get-ChildItem -Path $DataDir -Recurse -File
    if ($DataFiles.Count -gt 0) {
        Write-Host "Error: Forbidden data files found in dist\MRTG-TelkomCare\data" -ForegroundColor Red
        exit 1
    }
}

$OutputDir = Join-Path $DistAppDir "output"
if (Test-Path $OutputDir) {
    $OutputFiles = Get-ChildItem -Path $OutputDir -Recurse -File
    if ($OutputFiles.Count -gt 0) {
        Write-Host "Error: Forbidden output files found in dist\MRTG-TelkomCare\output" -ForegroundColor Red
        exit 1
    }
}

$IssPath = Join-Path $RootDir "installer\MRTG-TelkomCare.iss"
if (-not (Test-Path $IssPath)) {
    Write-Host "Error: Cannot find $IssPath" -ForegroundColor Red
    exit 1
}

Write-Host "Verifying required dist files for installer..." -ForegroundColor Cyan
$RequiredDistFiles = @(
    "config\.env.example",
    "config\list_mrtg_targets.csv",
    "config\list_mrtg_data_position.txt",
    "config\list_mrtg_data_position_img_only.txt",
    "templates\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
    "templates\MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
    "assets\app_icon.ico",
    "_internal\base_library.zip",
    "_internal\paddlex\configs\pipelines\OCR.yaml",
    "_internal\paddle\libs\mklml.dll"
)

$MissingDistFiles = 0
foreach ($req in $RequiredDistFiles) {
    $reqPath = Join-Path $DistAppDir $req
    if (-not (Test-Path $reqPath)) {
        Write-Host "Error: Required file missing from dist: $reqPath" -ForegroundColor Red
        $MissingDistFiles++
    }
}

if ($MissingDistFiles -gt 0) {
    Write-Host "Error: Installer validation failed. Missing $MissingDistFiles required files." -ForegroundColor Red
    exit 1
}

$ReleaseDir = Join-Path $RootDir "release"
if (-not (Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
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
    Write-Host "Error: Inno Setup 6 compiler (ISCC.exe) not found." -ForegroundColor Red
    Write-Host "Install Inno Setup 6 from https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
    exit 1
}

Write-Host "Building installer using $ISCC..." -ForegroundColor Cyan
& $ISCC "/DMyAppVersion=$AppVersion" $IssPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "Inno Setup compilation failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Success! Installer created in release\MRTG-TelkomCare-Setup-v$AppVersion.exe" -ForegroundColor Green

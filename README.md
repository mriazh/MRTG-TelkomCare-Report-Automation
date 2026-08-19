# MRTG-TelkomCare-Report-Automation

Automated end-to-end pipeline that logs in to TelkomCare, captures MRTG traffic graphs, and compiles them into Excel reports. The application provides a Windows GUI and CLI, plus experimental source-only support for Debian/Linux.

## Platform Support

| Platform | Support | Recommended use |
|---|---|---|
| Windows 10/11 | Supported | Portable ZIP (Installer EXE conditional / optional) |
| Windows with Python 3.12 | Supported | Source development and diagnostics |
| Debian/Linux | Experimental | Python source with a visible desktop session |

Scraping requires a visible browser session because TelkomCare authentication can involve CAPTCHA, MFA, and manual interaction. Do not use headless mode for the login phase unless your environment has been specifically validated.

## Windows Distribution

The Windows release is provided as a portable distribution:

- `MRTG-TelkomCare-v1.0.3-portable.zip`: extract-and-run package that does not install into system folders.
- `MRTG-TelkomCare-Setup-v1.0.3.exe`: optional installer format (conditional / built from source with Inno Setup; not included in standard release package).

At least one supported browser must be installed: Chrome, Edge, Firefox, Chromium, or Brave. The GUI labels detected browsers as `Installed` or `Not Installed` and disables unavailable choices.

## Installer Setup (If Built)

1. Run `MRTG-TelkomCare-Setup-v1.0.3.exe`.
2. Choose the installation directory. The default is `%LOCALAPPDATA%\Programs\MRTG TelkomCare`.
3. Launch the application from the Start Menu, desktop shortcut if selected, or `MRTG-TelkomCare.exe`.
4. Open the installed `config` directory.
5. Create the private environment file and target list from the sanitized examples.

PowerShell example:

```powershell
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\MRTG TelkomCare'

Copy-Item (Join-Path $installDir 'config\.env.example') `
          (Join-Path $installDir 'config\.env')
Copy-Item (Join-Path $installDir 'config\list_mrtg_targets.example.csv') `
          (Join-Path $installDir 'config\list_mrtg_targets.csv')

notepad (Join-Path $installDir 'config\.env')
notepad (Join-Path $installDir 'config\list_mrtg_targets.csv')
```

Do not create the files in the repository root or in the current PowerShell directory. They must be under the installed application's `config` directory. Quote paths containing spaces.

## Portable Setup

1. Extract `MRTG-TelkomCare-v1.0.3-portable.zip` into a dedicated writable directory.
2. Open the extracted `MRTG-TelkomCare-Portable\config` directory.
3. Copy `.env.example` to `.env` and `list_mrtg_targets.example.csv` to `list_mrtg_targets.csv`.
4. Edit the two private files, then run `MRTG-TelkomCare.exe` from the extracted package directory.

The portable package is intentionally free of private credentials, target data, screenshots, logs, reports, and resume state. Use a writable extraction directory so the application can create `data` and `output` beside the executable.

## Configuration

### `config/.env`

Start from `config/.env.example`. The important settings are:

| Variable | Purpose |
|---|---|
| `BASE_URL_SID` | TelkomCare URL or route used for SID targets |
| `BASE_URL_GRAPH` | TelkomCare URL or route used for Graph-title targets |
| `WAIT_TIMEOUT` | Normal browser wait timeout in seconds |
| `LONG_TIMEOUT` | Longer page or processing timeout in seconds |
| `LOGIN_WAIT` | Maximum login/MFA wait in seconds |
| `MAX_RETRIES` | General retry count |
| `MAX_GRAPH_RETRIES` | Graph capture retry count |
| `BROWSER_TYPE` | `auto`, `chrome`, `chromium`, `firefox`, or `edge` |
| `BROWSER_BINARY_LOCATION` | Optional absolute browser executable path |
| `AUTO_LOGIN_ENABLED` | Optional automated-login switch; keep disabled unless configured |
| `TELKOM_USER` / `TELKOM_PASSWORD` | Optional automated-login credentials; never share the file |
| `TOTP_SECRET` | Optional automated MFA secret; treat as a credential |
| `GEMINI_API_KEY` | Optional CAPTCHA/OCR fallback credential; never commit it |
| `GEMINI_MODELS` | Comma-separated Gemini model fallback order |
| `OCR_CONFIDENCE_THRESHOLD` | PaddleOCR confidence threshold |
| `OCR_GEMINI_OBSERVE` | Enables optional OCR observation behavior |
| `OCR_MAX_RETRIES` | Maximum finite retries per OCR/report item (default `3`) |

Passwords and API keys are not required for the normal manual-login flow. If automated login or Gemini fallback is enabled, protect the file and rotate credentials if it is ever exposed.

### `config/list_mrtg_targets.csv`

Start from `list_mrtg_targets.example.csv`. Required columns are:

```csv
type,target,ocr_enabled,image_enabled
SID,4700001-EXAMPLE,true,true
Graph-title,EXAMPLE-GRAPH-TITLE,true,true
```

Use `SID` for an exact system ID and `Graph-title` for a graph title. Boolean values should be `true` or `false`. The GUI and source CLI target filter uses these flags:

- `image`: includes rows where `image_enabled=true`.
- `ocr`: includes rows where `ocr_enabled=true`.
- `all`: includes all recognized rows.

Keep the private CSV local. It is deliberately excluded from release artifacts.

### Position maps and Excel templates

All report inputs live in `config/`. The repository ships only sanitized examples:

- `config/list_mrtg_data_position.example.txt`: Example mapping of OCR values and image ranges for the normal OCR report.
- `config/list_mrtg_data_position_img_only.example.txt`: Example mapping of image ranges for the image-only report.
- `config/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx`: OCR report template.
- `config/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx`: Image-only report template.

The application automatically reads `list_mrtg_data_position.txt` (and `_img_only.txt`) if present locally, or falls back to the `.example.txt` files. Active mapping files containing private service IDs are ignored by version control.

## Operation Modes

- **Scrape**: logs in and captures screenshots only.
- **Report**: reads previously captured screenshots and creates an Excel report.
- **Full Pipeline**: runs Scrape followed by Report in one operation.

Target filters are `image`, `ocr`, and `all`. Report modes are `image` and `ocr`:

- **Image-only report**: places screenshots into the image-only workbook.
- **OCR report**: extracts values with PaddleOCR and can fall back to Gemini when PaddleOCR is incomplete or confidence is low, then writes values and images to the OCR workbook.

## GUI Usage

1. Launch the installed or portable `MRTG-TelkomCare.exe`.
2. Select `Scrape`, `Report`, or `Full Pipeline`.
3. Select a single date or date range.
4. Select the target filter and report mode.
5. Select an installed browser.
6. Click Run.
7. Complete TelkomCare login, CAPTCHA, terms, and MFA in the visible browser when prompted.
8. Monitor the live log panel. A successful run ends with `exit_code=0` and a success summary.

The GUI can pause and continue a run. If it detects an unfinished run on startup, choose `Resume`, `Start New`, or `Discard`. Use `Open Output Folder` from the menu to open `output/reports`; the folder is created automatically if it does not exist. Use `Open Log Folder` to open `output/logs`.

## Source CLI Usage

The source CLI is available through `python -m mrtg_automation`. The packaged EXE is built from the GUI launcher and should be treated primarily as a GUI application.

### Windows source

```powershell
\.venv312\Scripts\Activate.ps1

python -m mrtg_automation --help
python -m mrtg_automation scrape --date 20260819 --targets all
python -m mrtg_automation report --mode image --date 20260819
python -m mrtg_automation report --mode ocr --date 20260819
python -m mrtg_automation full --date 20260819 --targets ocr --report-mode ocr
```

Use `--start-date YYYYMMDD --end-date YYYYMMDD` for a date range. Use `--no-images` on report/full commands when values are needed without embedding screenshots. The source CLI reads configuration from the repository's `config` directory.

For a reproducible developer environment, use Python 3.12 with uv:

```powershell
uv sync --locked --extra gui
uv run --locked --extra gui python -m pytest -q
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked mypy
```

uv is a development/verification tool only; packaged end users do not need uv.

### Debian/Linux source

```bash
source .venv/bin/activate
python -m mrtg_automation --help
python -m mrtg_automation full --date 20260819 --targets all --report-mode ocr
```

## GUI Source Launch

```powershell
\.venv312\Scripts\Activate.ps1
python gui_launcher.py
# Or:
python -m mrtg_automation gui
```

On Debian/Linux, use `source .venv/bin/activate` and the same Python commands. A visible desktop session is required for the browser login flow.

## Output and Logs

All runtime data is kept beside the executable in packaged mode, or at the repository root in source mode:

```text
config/.env                         # private local settings, never share
config/list_mrtg_targets.csv        # private local target list, never share
output/data/MRTG-Data/YYYYMMDD/*.png # captured screenshots
output/reports/*.xlsx                # generated Excel reports
output/logs/app.log                  # application log
output/logs/ocr_report.log           # OCR-specific log when OCR is used
output/state/                        # resume state for interrupted runs
output/screenshots/                  # debug screenshots if enabled
```

The report command prints the exact template, mapping, target list, data directory, and output path it uses. A successful full run reports the target summary, OCR engine summary, generated workbook, and `exit_code=0`.

## Troubleshooting

### `pytest` is not installed

Use the same Python interpreter as the source environment:

```powershell
\.venv312\Scripts\python.exe -m pip install pytest
\.venv312\Scripts\python.exe -m pytest -q
```

### PowerShell cannot find a path with spaces

Quote the path or use `Join-Path`:

```powershell
Set-Location "C:\Users\<user>\AppData\Local\Programs\MRTG TelkomCare"
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\MRTG TelkomCare'
```

### `Could not open output folder` / `[WinError 2]`

Use the rebuilt release. The GUI creates runtime directories at startup and creates `output/reports` before opening it. If testing an older installation, reinstall the current installer or manually run:

```powershell
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\MRTG TelkomCare'
New-Item -ItemType Directory -Force (Join-Path $installDir 'output\reports')
```

### No targets are found

Verify that `config/list_mrtg_targets.csv` exists beside the executable, has the four required headers, uses recognized `type` values (`SID` or `Graph-title`), and enables the selected filter with `true` values.

### No report is generated

Run Scrape first and verify that `output/data/MRTG-Data/YYYYMMDD` contains valid PNG files. Then run Report for the same date. Check `output/logs/app.log` and `output/logs/ocr_report.log` for details.

### Browser or login fails

Install a supported browser, select it explicitly in the GUI, verify the configured base URL, and keep the browser visible during login. CAPTCHA, MFA, terms acceptance, and network access must be completed successfully.

### OCR uses Gemini or reports partial values

This is expected when PaddleOCR is incomplete or below the configured confidence threshold. Check the OCR summary and logs. Ensure `GEMINI_API_KEY` is configured only when Gemini fallback is permitted and available. Gemini candidates are attempted in the exact `GEMINI_MODELS` order from `.env.example`; each candidate is abandoned after three observed failed calls for that operation. OCR/report items are retried at most `OCR_MAX_RETRIES` times (default three), and unresolved items remain visible in the final summary. The application does not query provider quota/RPD reset state or wait for a reset.

## Packaging and Release Validation

Build from a clean Windows Python 3.12 environment:

```powershell
\.venv312\Scripts\Activate.ps1
\.venv312\Scripts\python.exe -m pytest tests/test_browser_detection.py tests/test_build_packaging_contract.py tests/test_gui_startup_contract.py tests/test_release_metadata.py tests/test_release_packaging_contract.py -q
\.venv312\Scripts\python.exe -m compileall -q src tests
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\package_portable.ps1 -Force
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1 -Force
```

The build creates the EXE under `dist/MRTG-TelkomCare`, the portable archive under `release`, and the installer under `release`. Release scripts reject private configuration, runtime data, logs, reports, screenshots, state, and unapproved files.

## Security and Privacy

Never commit, upload, or share `config/.env` or `config/list_mrtg_targets.csv`. These files may contain URLs, credentials, API keys, private target identifiers, or operational data. Rotate credentials if they are exposed. Release artifacts intentionally include only sanitized examples and approved templates/maps.

## Project Merger

This repository is the unified successor of:

- [Automated-Daily-MRTG-Telkom-in-GMF](https://github.com/mriazh/Automated-Daily-MRTG-Telkom-in-GMF), which provided TelkomCare scraping.
- [Automated-MRTG-to-Excel-Report](https://github.com/mriazh/Automated-MRTG-to-Excel-Report), which provided Excel reporting and OCR.

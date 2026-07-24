# MRTG-TelkomCare-Report-Automation

Automated end-to-end pipeline to scrape MRTG traffic graphs from TelkomCare and compile them into formal Excel reports.

This application provides a seamless **GUI** and **CLI** experience for operators across both **Windows** and **Debian / Linux** platforms.

---

## 💻 Platform Support

| Platform | Support Level | Execution Method |
|---|---|---|
| **Windows** | Fully Supported | Pre-packaged Installer (`.exe`), Portable (`.zip`), or Python Source |
| **Debian / Linux** | Experimental (Source-only) | Python 3.12 Virtual Environment (`.venv`) from Source |

> **Note on Scraping:** Because TelkomCare requires manual authentication (Captcha / MFA), running scraping operations requires a visible desktop session, VNC, or X forwarding. Pure headless mode without a display is not supported during the login phase.

---

## 📥 Recommended Download (Windows Only)

For Windows operators, pre-packaged distribution formats are available on the releases page:

- **Installer EXE (Recommended)**: `MRTG-TelkomCare-Setup-v1.0.1.exe` — installs the application, configures shortcuts, and sets up dependencies automatically.
- **Portable ZIP**: `MRTG-TelkomCare-v1.0.1-portable.zip` — extract-and-run package for portable execution without modifying system folders.

> **Browser Requirement:** At least one supported web browser (**Google Chrome**, **Microsoft Edge**, **Mozilla Firefox**, **Brave**, or **Chromium**) must be installed on your system.

---

## 🚀 First-Run Setup & Configuration

> [!IMPORTANT]
> For your security, releases **do not** include your environment-specific settings or network target lists. You must set these up locally before running the app.

1. **Setup Runtime Settings**:
   - Copy `config/.env.example` to `config/.env`.
   - Open `.env` in a text editor to configure TelkomCare base URLs and timeout settings.
   - *(Note: Passwords are not stored. You will log into TelkomCare manually in the browser when prompted).*
2. **Prepare Network Targets**:
   - Copy `config/list_mrtg_targets.example.csv` to `config/list_mrtg_targets.csv`
   - Edit `config/list_mrtg_targets.csv` in Excel or text editor.
   - Required columns: `type`, `target`, `ocr_enabled`, `image_enabled`.
   ```csv
   type,target,ocr_enabled,image_enabled
   SID,EXAMPLE-SID,true,true
   Graph-title,EXAMPLE-GRAPH-TITLE,true,true
   ```

---

## ⚙️ Operation Modes

- **Scraping Modes**:
  - **Scrape by SID**: Automatically fetch MRTG traffic graphs using exact system IDs.
  - **Scrape by Graph Title**: Automatically fetch graphs matching assigned titles.
- **Reporting Modes**:
  - **Image Only**: Lightweight mode that generates an Excel report containing graph screenshots.
  - **OCR + Image**: Advanced mode using AI (PaddleOCR) to read data values directly from screenshots, populating exact values and images into Excel cells.

---

## 🌐 Browser Selection & Auto-Detection

The application provides intelligent browser auto-detection and selection across Windows, Linux, and macOS:

- **GUI Selection**: The GUI **Browser** dropdown scans your system upon launch and labels each supported browser with its installation status:
  - `Chrome (Installed)`, `Edge (Installed)`, `Brave (Installed)`
  - `Firefox (Not Installed)`, `Chromium (Not Installed)`
  Uninstalled browsers are automatically disabled in the dropdown to prevent invalid selections. The application defaults to the first available installed browser.
- **Headless Toggle**: Check **Run browser headless** to run scraping in the background (once login session is established).
- **Environment Configuration**: Set `BROWSER_TYPE` in `config/.env` to `chrome`, `edge`, `firefox`, or `chromium`. Optionally specify `BROWSER_BINARY_LOCATION` to use a custom binary path.

---

## 🖥️ GUI Usage & Launch Guide

### 🪟 Windows Execution

#### 1. Via Packaged Executable / Shortcut:
- Double-click `MRTG-TelkomCare.exe` or launch via the Start Menu shortcut.

#### 2. Via PowerShell (Source Code):
```powershell
# Activate Virtual Environment
.\.venv312\Scripts\Activate.ps1

# Launch GUI Launcher
python gui_launcher.py

# Or launch GUI module directly
python -m mrtg_automation gui
```

---

### 🐧 Debian / Linux Execution

#### Via Bash Terminal (Source Code):
```bash
# Activate Virtual Environment
source .venv/bin/activate

# Launch GUI Launcher
python gui_launcher.py

# Or launch GUI module directly
python -m mrtg_automation gui
```

---

### Key GUI Interface Features:
- **Operation Mode**: Select **Scrape**, **Report**, or **Full Pipeline** (Scrape $\rightarrow$ Report).
- **Date Mode**: Choose **Single Date** or **Date Range** (Start Date to End Date).
- **Target Filtering & Report Mode**: Filter targets by `image`, `ocr`, or `all`, and choose report format (`image` or `ocr`).
- **Browser Selector**: Pick any detected installed browser (`Chrome (Installed)`, `Edge (Installed)`, etc.). Uninstalled options are automatically disabled.
- **Pause / Continue Controls**: Pause active scraping or OCR processing tasks at any point and resume seamlessly without losing progress.
- **Unfinished Run Recovery**: If an execution is interrupted, the GUI detects unfinished states on launch and prompts to **Resume**, **Start New**, or **Discard**.
- **Real-Time Streaming Log Panel**: Track progress live with formatted logging, status updates, and network error alerts.

---

## 💻 CLI Usage & Commands Guide

### 🪟 Windows Execution

#### 1. Via PowerShell (Source Code):
```powershell
# Activate Virtual Environment
.\.venv312\Scripts\Activate.ps1

# Scrape all targets for a specific date
python -m mrtg_automation scrape --date YYYYMMDD --targets all --browser chrome

# Generate an OCR report for previously scraped data
python -m mrtg_automation report --mode ocr --date YYYYMMDD

# Run the full pipeline (scrape -> report) sequentially
python -m mrtg_automation full --date YYYYMMDD --targets all --report-mode ocr --browser edge
```

#### 2. Via Packaged Executable CLI:
After extracting `MRTG-TelkomCare-v1.0.1-portable.zip` or installing `MRTG-TelkomCare-Setup-v1.0.1.exe`, run:
```cmd
MRTG-TelkomCare.exe scrape --date YYYYMMDD --targets all --browser chrome
MRTG-TelkomCare.exe report --mode ocr --date YYYYMMDD
MRTG-TelkomCare.exe full --date YYYYMMDD --targets all --report-mode ocr --browser edge
```

---

### 🐧 Debian / Linux Execution

#### Via Bash Terminal (Source Code):
```bash
# Activate Virtual Environment
source .venv/bin/activate

# Scrape all targets for a specific date
python -m mrtg_automation scrape --date YYYYMMDD --targets all --browser chrome

# Generate an OCR report for previously scraped data
python -m mrtg_automation report --mode ocr --date YYYYMMDD

# Run the full pipeline (scrape -> report) sequentially
python -m mrtg_automation full --date YYYYMMDD --targets all --report-mode ocr --browser firefox
```

---

## 📂 File Directory Layout

When you run the automation, local files are organized into standard directories:

- **Screenshots**: `data/MRTG-Data/YYYYMMDD`
- **Excel Reports**: `output/reports`
- **Application Logs**: `output/logs`
- **Resume/State Files**: `output/state` (Used to resume scraping if a session is interrupted)

---

## 🔒 Security & Privacy Note

**Never commit or share your `config/.env` or private target list (`config/list_mrtg_targets.csv`)!**

Automated build scripts validate release packages before distribution to ensure no local configuration files, scraped data, logs, reports, or state files are bundled into public releases.

---

## 🏗️ Project Merger (Legacy Notice)

This repository is the unified successor of two legacy projects:

- [Automated-Daily-MRTG-Telkom-in-GMF](https://github.com/mriazh/Automated-Daily-MRTG-Telkom-in-GMF): Provided the original TelkomCare web scraping capabilities.
- [Automated-MRTG-to-Excel-Report](https://github.com/mriazh/Automated-MRTG-to-Excel-Report): Provided the Excel reporting and OCR capabilities.

# MRTG-TelkomCare-Report-Automation

Automated end-to-end pipeline to scrape MRTG graphs from TelkomCare and generate an Excel report. 

This application provides a seamless GUI and CLI experience for operators who need to automatically gather network traffic statistics and rapidly compile them into formal Excel reports.

---

## 📥 Recommended Download

For Windows users, we provide two ready-to-use distribution formats in the releases page:

- **Installer EXE (Recommended)**: Best for most users. It installs the application, dependencies, and creates convenient shortcuts.
- **Portable ZIP**: Best for users who prefer an extract-and-run approach without modifying system folders.

> **Note:** **Google Chrome** must be installed on your system for the scraper to function.

---

## 🚀 First-Run Setup (Safe Configuration)

> [!IMPORTANT]
> For your security, releases **do not** include your environment-specific settings or network target lists. You must set these up locally the first time you run the app.

1. **Install or Extract** the release artifact to your desired location.
2. Navigate to the `config` folder.
3. **Set up your runtime settings**:
   - Copy `config/.env.example` and rename the copy to `config/.env`.
   - Open `.env` in a text editor to review the TelkomCare base URLs and timeout settings.
   - *(Note: The application does not store passwords. You will log into TelkomCare manually in the browser when prompted during a scraping run).*
4. **Prepare your network targets**:
   - Open `config/list_mrtg_targets.csv` in Excel or a text editor to list the targets you want to scrape or report on.
   - The CSV requires four columns: `type`, `target`, `ocr_enabled`, and `image_enabled`.
   - Example configuration:
     ```csv
     type,target,ocr_enabled,image_enabled
     SID,4700001-0021497479,true,true
     Graph-title,3598,true,true
     ```

---

## ⚙️ Operation Modes

The application supports multiple execution modes depending on your workflow:

**Scraping Modes:**
- **Scrape by SID**: Automatically fetch graphs using their exact system ID.
- **Scrape by Graph Title**: Automatically fetch graphs by matching their assigned titles.

**Reporting Modes:**
- **Image Only**: Lightweight mode that generates an Excel report with only the graph screenshots inserted.
- **OCR + Image**: Advanced mode that uses AI (PaddleOCR) to read the text directly from the screenshots, populating both the exact data values and the images into the Excel cells.

---

## 📂 Where Files Are Saved

When you run the automation, your local files will be neatly organized into the following directories:

- **Screenshots**: `data/MRTG-Data/YYYYMMDD`
- **Excel Reports**: `output/reports`
- **Application Logs**: `output/logs`
- **Resume/State Files**: `output/state` (Used to resume scraping if a session is interrupted)

---

## 🔒 Security & Privacy Note

**Never commit or share your `config/.env` or private target list (`config/list_mrtg_targets.csv`)!**

To protect you, our automated build scripts validate the release packages before they are distributed. The release pipeline explicitly verifies that no local configuration files, scraped data, logs, reports, or state files are accidentally bundled into the public installer or portable ZIP.

---

## 🏗️ Project Merger (Legacy Notice)

This repository is the unified successor of two legacy projects, merging their functionality into a single, cohesive application:

- [Automated-Daily-MRTG-Telkom-in-GMF](https://github.com/mriazh/Automated-Daily-MRTG-Telkom-in-GMF): Provided the original TelkomCare web scraping capabilities.
- [Automated-MRTG-to-Excel-Report](https://github.com/mriazh/Automated-MRTG-to-Excel-Report): Provided the Excel reporting and OCR capabilities.

**Note:** This repository should be used for all new work, updates, and releases going forward.

---

## 👨‍💻 Developer Guide

For developers looking to run the application from source or build custom releases.

### Prerequisites
- **Python 3.12** is required for source builds.
- Google Chrome

### Source Installation
Clone the repository and install the application with all GUI and OCR dependencies:

```bash
pip install -e .[gui,ocr]
```

### Build / Release Pipeline
The project uses strict PowerShell scripts to compile and validate safe releases.

1. **Build the base EXE executable:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -Clean
   ```
2. **Package the Portable ZIP:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\package_portable.ps1
   ```
3. **Compile the Windows Installer** (Requires Inno Setup 6):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
   ```

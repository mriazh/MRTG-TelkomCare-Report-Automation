# MRTG-TelkomCare-Report-Automation

Automated end-to-end pipeline to scrape MRTG graphs from TelkomCare and generate an Excel report. 
Supports both **Image Only** and **OCR + Image** modes.

## Architecture & Modes
- **CLI**: Core operational mode.
- **GUI**: (Upcoming) Wrapper for the CLI logic using PySide6.
- **Modes**:
  - Image Only: Light-weight, inserts screenshot only.
  - OCR + Image: Uses PaddleOCR to extract text from graphs and populate Excel cells.

## Prerequisites
- **Python 3.12+**
- Google Chrome

## Installation
For the core CLI application:
```bash
pip install -e .
```

(Optional) For OCR capability:
```bash
pip install -e .[ocr]
```

## Configuration
Copy `config/.env.example` to `config/.env` and adjust the variables.
Put your target references in `config/SID-MRTG-example.txt` (rename to `SID-MRTG.txt`) and `config/GRAPH-TITLE-MRTG-example.txt` (rename to `GRAPH-TITLE-MRTG.txt`).

## Usage
Run the CLI menu:
```bash
python -m mrtg_automation
```

## Build / Release
To build a standalone executable for Windows:

> [!IMPORTANT]
> Local credentials in `config/.env` and target lists like `config/SID-MRTG.txt` are intentionally **not bundled** into the release output to prevent leaking secrets. After extracting or installing, you must copy `config/.env.example` to `config/.env` in the config folder and provide your credentials before scraping.

1. Install prerequisites:
   ```powershell
   .venv312\Scripts\python -m pip install -e .[gui,ocr]
   .venv312\Scripts\python -m pip install pyinstaller
   ```
2. Build EXE:
   ```powershell
   .\scripts\build_exe.ps1 -Clean
   ```
3. Build portable ZIP (outputs to `release\MRTG-TelkomCare-v1.0.0-portable.zip`):
   ```powershell
   .\scripts\package_portable.ps1
   ```
4. Build installer (outputs to `release\MRTG-TelkomCare-Setup-v1.0.0.exe`, requires [Inno Setup 6](https://jrsoftware.org/isinfo.php)):
   ```powershell
   .\scripts\build_installer.ps1
   ```

## Deprecation Notice
This repository merges and deprecates the following legacy projects:
- `Automated-Daily-MRTG-Telkom-in-GMF`
- `Automated-MRTG-to-Excel-Report`

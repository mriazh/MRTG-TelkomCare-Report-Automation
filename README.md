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

## Build Windows EXE
To build a standalone executable for Windows:

1. Ensure your `.venv312` is activated and dependencies are installed explicitly:
   ```powershell
   .venv312\Scripts\python -m pip install -e .[gui,ocr]
   ```
2. Install PyInstaller if you haven't already:
   ```powershell
   .venv312\Scripts\python -m pip install pyinstaller
   ```
3. Run the build script:
   ```powershell
   .\scripts\build_exe.ps1 -Clean
   ```
4. Find the executable at `dist\MRTG-TelkomCare\MRTG-TelkomCare.exe`.

## Deprecation Notice
This repository merges and deprecates the following legacy projects:
- `Automated-Daily-MRTG-Telkom-in-GMF`
- `Automated-MRTG-to-Excel-Report`

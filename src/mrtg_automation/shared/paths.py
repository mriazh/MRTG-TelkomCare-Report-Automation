import sys
from pathlib import Path

def resolve_root() -> Path:
    """
    Resolve the absolute root directory of the project.
    Designed to work both in script mode and when packaged by PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled PyInstaller executable
        return Path(sys._MEIPASS).resolve()
    else:
        # Running from source (src/mrtg_automation/shared/paths.py)
        # Root is 4 levels up: src/mrtg_automation/shared -> src/mrtg_automation -> src -> root
        return Path(__file__).resolve().parent.parent.parent.parent

ROOT_DIR = resolve_root()

# Main application directories
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data" / "MRTG-Data"
TEMPLATES_DIR = ROOT_DIR / "templates"
OUTPUT_DIR = ROOT_DIR / "output"
REPORTS_DIR = OUTPUT_DIR / "reports"
LOGS_DIR = OUTPUT_DIR / "logs"
STATE_DIR = OUTPUT_DIR / "state"

# Debug directory
SCREENSHOTS_DEBUG_DIR = OUTPUT_DIR / "screenshots"

def ensure_directories():
    """Ensure all required base directories exist."""
    dirs = [
        CONFIG_DIR,
        DATA_DIR,
        TEMPLATES_DIR,
        REPORTS_DIR,
        LOGS_DIR,
        STATE_DIR,
        SCREENSHOTS_DEBUG_DIR
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

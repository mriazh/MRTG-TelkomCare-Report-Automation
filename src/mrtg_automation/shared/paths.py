import os
import sys
from pathlib import Path


def resolve_root() -> Path:
    """
    Resolve the absolute root directory of the project.
    Designed to work both in script mode and when packaged by PyInstaller.
    """
    if getattr(sys, "frozen", False):
        # Running as compiled PyInstaller executable
        return Path(sys.executable).resolve().parent
    else:
        # Running from source (src/mrtg_automation/shared/paths.py)
        # Root is 4 levels up: src/mrtg_automation/shared -> src/mrtg_automation -> src -> root
        return Path(__file__).resolve().parent.parent.parent.parent


ROOT_DIR = resolve_root()

# Main application directories
CONFIG_DIR = Path(os.getenv("MRTG_CONFIG_DIR", ROOT_DIR / "config")).expanduser().resolve()
OUTPUT_DIR = Path(os.getenv("MRTG_OUTPUT_DIR", ROOT_DIR / "output")).expanduser().resolve()
DEFAULT_OUTPUT_DIR = OUTPUT_DIR
DEFAULT_CONFIG_DIR = CONFIG_DIR
DATA_DIR = (
    Path(os.getenv("MRTG_DATA_DIR", OUTPUT_DIR / "data" / "MRTG-Data")).expanduser().resolve()
)
REPORTS_DIR = OUTPUT_DIR / "reports"
LOGS_DIR = OUTPUT_DIR / "logs"
STATE_DIR = OUTPUT_DIR / "state"
SCREENSHOTS_DEBUG_DIR = OUTPUT_DIR / "screenshots"

OCR_TEMPLATE_FILE = (
    CONFIG_DIR / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
)
IMAGE_ONLY_TEMPLATE_FILE = (
    CONFIG_DIR / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
)


class OutputPathsDict(dict):
    """Dictionary supporting both dict keys ('data', 'data_dir') and attribute access (.data_dir)."""

    def __getattr__(self, name: str):
        if name in self:
            return self[name]
        if name.endswith("_dir") and name[:-4] in self:
            return self[name[:-4]]
        raise AttributeError(f"'OutputPathsDict' object has no attribute '{name}'")


def get_output_paths(output_root: Path | str | None = None) -> OutputPathsDict:
    """Get dictionary of derived paths within the given output root."""
    root = Path(output_root).expanduser().resolve() if output_root is not None else OUTPUT_DIR
    return OutputPathsDict(
        {
            "output_root": root,
            "logs": root / "logs",
            "reports": root / "reports",
            "data": root / "data" / "MRTG-Data",
            "state": root / "state",
            "screenshots": root / "screenshots",
            "logs_dir": root / "logs",
            "reports_dir": root / "reports",
            "data_dir": root / "data" / "MRTG-Data",
            "state_dir": root / "state",
            "screenshots_dir": root / "screenshots",
        }
    )


class ConfigPathsDict(dict):
    """Dictionary supporting both dict keys ('env', 'position_ocr') and attribute access (.env, .position_ocr)."""

    def __getattr__(self, name: str):
        if name in self:
            return self[name]
        raise AttributeError(f"'ConfigPathsDict' object has no attribute '{name}'")


def get_config_files(config_root: Path | str | None = None) -> ConfigPathsDict:
    """Get dictionary of expected config files within the given config root."""
    root = Path(config_root).expanduser().resolve() if config_root is not None else CONFIG_DIR
    return ConfigPathsDict(
        {
            "config_root": root,
            "env": root / ".env",
            "position_ocr": root / "list_mrtg_data_position.txt",
            "position_img_only": root / "list_mrtg_data_position_img_only.txt",
            "targets": root / "list_mrtg_targets.csv",
            "template_ocr": root
            / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
            "template_img_only": root
            / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
        }
    )


def ensure_directories(
    output_dir: Path | str | None = None,
    config_dir: Path | str | None = None,
    output_root: Path | str | None = None,
):
    """Ensure all required base directories exist."""
    cfg = Path(config_dir).expanduser().resolve() if config_dir is not None else CONFIG_DIR
    out_arg = output_root if output_root is not None else output_dir
    out = Path(out_arg).expanduser().resolve() if out_arg is not None else OUTPUT_DIR
    out_paths = get_output_paths(out)

    dirs = [
        cfg,
        out,
        out_paths["reports"],
        out_paths["logs"],
        out_paths["state"],
        out_paths["screenshots"],
        out_paths["data"],
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

import re
from datetime import datetime, date
from pathlib import Path
from typing import Union
from .paths import DATA_DIR

def sanitize_target_id(target_id: str) -> str:
    """
    Sanitize target ID string safe for Windows filename.
    Replaces invalid characters with underscores instead of removing them
    to prevent unintended merging of different IDs.
    """
    # Windows invalid characters: \ / * ? " < > | :
    return re.sub(r'[\\/*?:"<>|]', "_", target_id).strip()

def build_canonical_filename(target_id: str, date_obj: Union[datetime, date]) -> str:
    """
    Build canonical format unified for both SID and Graph Title: 
    MRTG_<TARGET_ID>_<YYYYMMDD>.png
    """
    safe_id = sanitize_target_id(target_id)
    date_str = date_obj.strftime("%Y%m%d")
    return f"MRTG_{safe_id}_{date_str}.png"

def get_screenshot_path(target_id: str, date_obj: Union[datetime, date]) -> Path:
    """
    Return full Path object to the canonical screenshot target file.
    """
    date_folder = date_obj.strftime("%Y%m%d")
    filename = build_canonical_filename(target_id, date_obj)
    return DATA_DIR / date_folder / filename

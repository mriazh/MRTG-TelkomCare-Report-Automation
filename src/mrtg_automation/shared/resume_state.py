import json
import logging
from pathlib import Path
from datetime import datetime
from .paths import STATE_DIR

logger = logging.getLogger("mrtg_automation.shared.resume_state")

def get_resume_state_path() -> Path:
    return STATE_DIR / "resume_state.json"

def load_resume_state() -> dict | None:
    path = get_resume_state_path()
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load resume state: {e}")
        return None

def save_resume_state(state: dict) -> None:
    path = get_resume_state_path()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=True)
    except Exception as e:
        logger.error(f"Failed to save resume state: {e}")

def clear_resume_state() -> None:
    path = get_resume_state_path()
    try:
        if path.exists():
            path.unlink()
    except Exception as e:
        logger.error(f"Failed to clear resume state: {e}")

def has_unfinished_resume_state() -> bool:
    state = load_resume_state()
    if not state:
        return False
    return state.get("status") in ("running", "paused", "stopped")

def format_resume_summary(state: dict) -> str:
    lines = []
    lines.append(f"Mode: {state.get('operation_mode', 'Unknown')}")

    date_mode = state.get("date_mode", "")
    if date_mode == "Single Date":
        lines.append(f"Date: {state.get('date_str', 'Unknown')}")
    elif date_mode == "Date Range":
        lines.append(f"Date: {state.get('start_date_str', '')} to {state.get('end_date_str', '')}")

    lines.append(f"Phase: {state.get('current_phase', 'Unknown')}")

    total = state.get('total_items', 0)
    completed = state.get('completed_items_count', 0)
    lines.append(f"Progress: {completed}/{total}")

    phase_total = state.get('phase_total_items', 0)
    if phase_total > 0:
        phase_completed = state.get('phase_completed_items_count', 0)
        lines.append(f"Phase progress: {phase_completed}/{phase_total}")

    lines.append(f"Last completed: {state.get('last_completed', 'None')}")
    lines.append(f"Next item: {state.get('next_item', 'None')}")

    return "\n".join(lines)

def make_item_key(phase: str, mode: str, date_str: str, target: str) -> str:
    return f"{phase}|{mode}|{date_str}|{target}"

def get_completed_item_keys(state: dict) -> set[str]:
    keys = set()
    for item in state.get("completed_items", []):
        if "key" in item:
            keys.add(item["key"])
        else:
            keys.add(make_item_key(item.get("phase", ""), item.get("mode", ""), item.get("date", ""), item.get("target", "")))
    return keys

def mark_item_completed(state: dict, item: dict) -> dict:
    if "completed_items" not in state:
        state["completed_items"] = []

    key = item.get("key")
    if key and key not in get_completed_item_keys(state):
        state["completed_items"].append(item)
        state["completed_items_count"] = len(state["completed_items"])
        state["last_completed"] = key
        state["next_item"] = None
    return state

def count_completed_items_for_phase(state: dict, phase: str) -> int:
    return sum(1 for item in state.get("completed_items", []) if item.get("phase") == phase)

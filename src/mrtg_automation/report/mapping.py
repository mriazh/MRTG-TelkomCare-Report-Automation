import csv
import logging
import re
from pathlib import Path
from typing import Any

from openpyxl.utils import column_index_from_string

from ..shared.config_models import TargetRow

logger = logging.getLogger(__name__)

# Regex pattern to strip "(1) " prefix from IDs in legacy format
RE_STRIP_NUMBERING = re.compile(r"^\(\d+\)\s*")


def parse_image_only_mapping(filepath: Path) -> dict[str, tuple[tuple[int, int], tuple[int, int]]]:
    """
    Parse Image-only mapping file.
    Legacy format example (two lines per item):
        SID : 4700001-0021497479
        -> B12-L23

        SID : 3598
        -> N105-X116
    """
    mapping: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}
    if not filepath.exists():
        logger.error(f"Mapping file not found: {filepath}")
        return mapping

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # We look for lines starting with 'SID :' (legacy labeled all as SID)
        if line.startswith("SID :"):
            id_raw = line.replace("SID :", "").strip()
            id_clean = RE_STRIP_NUMBERING.sub("", id_raw)
            i += 1

            # The next line should be the range '-> A1-B10'
            if i < len(lines) and lines[i].startswith("->"):
                range_str = lines[i][2:].strip()
                if "-" not in range_str:
                    logger.warning(
                        f"Invalid range format (missing '-'): '{range_str}', skipping '{id_clean}'"
                    )
                    i += 1
                    continue

                try:
                    start, end = range_str.split("-", 1)
                    start_col = column_index_from_string(re.match(r"[A-Z]+", start).group())
                    start_row = int(re.search(r"\d+", start).group())
                    end_col = column_index_from_string(re.match(r"[A-Z]+", end).group())
                    end_row = int(re.search(r"\d+", end).group())

                    mapping[id_clean] = ((start_row, start_col), (end_row, end_col))
                except Exception as e:
                    logger.warning(f"Failed to parse range '{range_str}' for '{id_clean}': {e}")

                i += 1
            else:
                i += 1
        else:
            i += 1

    return mapping


def parse_target_list(filepath: Path, enabled_for: str | None = None) -> list[tuple[str, str, str]]:
    """Parse target list (csv or txt) to return [(number, target_type, target_id)]"""
    items: list[tuple[str, str, str]] = []
    if not filepath.exists():
        logger.error(f"Target list not found: {filepath}")
        return items

    if filepath.suffix.lower() == ".csv":
        truthy = {"true", "1", "yes", "y"}
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            display_idx = 1
            for row in reader:
                if enabled_for == "ocr":
                    if row.get("ocr_enabled", "").strip().lower() not in truthy:
                        continue
                elif enabled_for == "image":
                    if row.get("image_enabled", "").strip().lower() not in truthy:
                        continue

                try:
                    target_row = TargetRow.model_validate(row)
                except Exception as exc:
                    logger.warning("Invalid target row skipped: %s", type(exc).__name__)
                    continue
                items.append(target_row.as_legacy_tuple(display_idx))
                display_idx += 1
        return items

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            match = re.match(r"(\d+)\.\s*([^:]+)\s*:\s*(\S+)", line)
            if match:
                items.append((match.group(1), match.group(2).strip(), match.group(3)))
    return items


def parse_ocr_mapping(filepath: Path) -> dict[str, dict[str, Any]]:
    """
    Parse OCR mapping file.
    Format expects:
    Service Id : 4700001-0020265222
    Inbound_Current: E14
    Inbound_Average: E15
    Inbound_Maximum: E16
    Outbound_Current: E17
    Outbound_Average: E18
    Outbound_Maximum: E19
    Image : B21-I35
    """
    mapping: dict[str, dict[str, Any]] = {}
    if not filepath.exists():
        logger.error(f"OCR Mapping file not found: {filepath}")
        return mapping

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("Service Id :"):
            id_raw = line.replace("Service Id :", "").strip()
            id_clean = RE_STRIP_NUMBERING.sub("", id_raw)
            i += 1

            entry = {}
            # Read next lines until next Service Id or EOF
            while i < len(lines) and not lines[i].startswith("Service Id :"):
                kv_line = lines[i]
                if ":" in kv_line:
                    key, val = kv_line.split(":", 1)
                    key = key.strip()
                    val = val.strip()

                    if key == "Image":
                        if "-" not in val:
                            logger.warning(f"Invalid Image range '{val}' for '{id_clean}'")
                        else:
                            try:
                                start, end = val.split("-", 1)
                                start_col = column_index_from_string(
                                    re.match(r"[A-Z]+", start).group()
                                )
                                start_row = int(re.search(r"\d+", start).group())
                                end_col = column_index_from_string(re.match(r"[A-Z]+", end).group())
                                end_row = int(re.search(r"\d+", end).group())
                                entry["Image"] = ((start_row, start_col), (end_row, end_col))
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse Image range '{val}' for '{id_clean}': {e}"
                                )
                    else:
                        match = re.match(r"([A-Z]+)(\d+)", val)
                        if match:
                            col_letter = match.group(1)
                            row = int(match.group(2))
                            col = column_index_from_string(col_letter)
                            entry[key] = (row, col)
                i += 1
            mapping[id_clean] = entry
        else:
            i += 1

    return mapping

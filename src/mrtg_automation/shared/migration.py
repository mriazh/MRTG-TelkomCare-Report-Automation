import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def migrate_legacy_data(data_dir: Path, dry_run: bool = True):
    """
    Scans data_dir for YYYYMMDD folders.
    Finds MRTG_*.png files that don't have the _YYYYMMDD suffix.
    Renames them to MRTG_<TARGET>_<YYYYMMDD>.png.
    """
    if not data_dir.exists():
        print(f"Directory not found: {data_dir}")
        return

    folders = [d for d in os.scandir(data_dir) if d.is_dir() and d.name.isdigit() and len(d.name) == 8]
    
    actions = []
    
    for folder in folders:
        date_str = folder.name
        folder_path = Path(folder.path)
        
        for file in os.scandir(folder_path):
            if file.is_file() and file.name.startswith("MRTG_") and file.name.endswith(".png"):
                # Check if it already ends with _YYYYMMDD.png
                suffix = f"_{date_str}.png"
                if not file.name.endswith(suffix):
                    # It's a legacy file
                    # Old: MRTG_<TARGET>.png
                    # New: MRTG_<TARGET>_<YYYYMMDD>.png
                    target = file.name[5:-4]  # Strip "MRTG_" and ".png"
                    
                    new_name = f"MRTG_{target}_{date_str}.png"
                    old_path = folder_path / file.name
                    new_path = folder_path / new_name
                    
                    actions.append((old_path, new_path))
                    
    if not actions:
        print("No legacy files found to migrate.")
        return
        
    print(f"Found {len(actions)} files to migrate.")
    
    if dry_run:
        print("\n--- DRY RUN MODE (SIMULASI) ---")
        for old, new in actions:
            print(f"Akan direname: {old.name} -> {new.name}")
        print("--- END DRY RUN ---\n")
        print("Untuk menerapkan perubahan, jalankan mode Execute.")
    else:
        print("\n--- EXECUTE MODE ---")
        success_count = 0
        skip_count = 0
        
        for old, new in actions:
            if new.exists():
                print(f"[SKIP] Target already exists, tidak akan di-overwrite: {new.name}")
                skip_count += 1
            else:
                try:
                    old.rename(new)
                    success_count += 1
                    print(f"[OK] Renamed to {new.name}")
                except Exception as e:
                    print(f"[ERROR] Failed to rename {old.name}: {e}")
                    
        print(f"\nMigration complete: {success_count} renamed, {skip_count} skipped.")

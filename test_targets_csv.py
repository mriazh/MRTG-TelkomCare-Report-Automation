import sys
from pathlib import Path
from mrtg_automation.report.mapping import parse_target_list

def main():
    csv_path = Path("config/list_mrtg_targets.csv")
    
    print("Testing 'image' filter...")
    image_items = parse_target_list(csv_path, enabled_for="image")
    assert len(image_items) == 20, f"Expected 20 image items, got {len(image_items)}"
    
    sid_count = sum(1 for item in image_items if 'sid' in item[1].lower())
    gt_count = sum(1 for item in image_items if 'graph' in item[1].lower())
    
    assert sid_count == 18, f"Expected 18 SID targets, got {sid_count}"
    assert gt_count == 2, f"Expected 2 Graph-title targets, got {gt_count}"
    print("[OK] image filter")
    
    print("Testing 'ocr' filter...")
    ocr_items = parse_target_list(csv_path, enabled_for="ocr")
    assert len(ocr_items) == 16, f"Expected 16 ocr items, got {len(ocr_items)}"
    
    ocr_targets = [item[2] for item in ocr_items]
    image_only_extras = [
        "2007544330",
        "1708594520",
        "4700001-0022213361",
        "4700001-0022835321"
    ]
    
    for extra in image_only_extras:
        assert extra not in ocr_targets, f"Target {extra} should be excluded from ocr"
        
    print("[OK] ocr filter")
    return 0

if __name__ == "__main__":
    sys.exit(main())

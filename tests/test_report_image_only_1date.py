import sys
import time
from pathlib import Path
from mrtg_automation.report.excel import ExcelReportGenerator
from mrtg_automation.config import Config
from mrtg_automation.shared.paths import DATA_DIR, CONFIG_DIR, TEMPLATES_DIR, REPORTS_DIR

def main():
    print("=" * 70)
    print("TEST: Image-Only Report Generation")
    print("=" * 70)
    
    mapping = CONFIG_DIR / "list_mrtg_data_position_img_only.txt"
    target_list = CONFIG_DIR / "list_mrtg_targets.csv"
    template = TEMPLATES_DIR / "MRTG-Monthly-Report-image-only.xlsx"
    if not template.exists():
        template = TEMPLATES_DIR / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
    
    output = REPORTS_DIR / "MRTG-Monthly-Report-image-only-smoke.xlsx"
    
    generator = ExcelReportGenerator(Config())
    start_time = time.time()
    
    summary = generator.generate(
        report_mode="IMAGE_ONLY",
        data_dir=DATA_DIR,
        template_path=template,
        output_path=output,
        mapping_file=mapping,
        list_file=target_list,
        date_filter="20260621"
    )
    
    duration = time.time() - start_time
    
    print(f"\nDATES: {summary.get('dates_processed', 0)}")
    print(f"TARGETS: {summary.get('targets', 0)}")
    print(f"EXPECTED: {summary.get('expected', 0)}")
    print(f"IMAGE_INSERTED: {summary.get('image_inserted', 0)}")
    print(f"MISSING_SCREENSHOTS: {summary.get('missing_screenshots', 0)}")
    print(f"MISSING_MAPPINGS: {summary.get('missing_mappings', 0)}")
    print(f"FAILED_INSERTS: {summary.get('failed_inserts', 0)}")
    print(f"SUCCESS: {summary.get('success', False)}")
    print(f"TIME: {duration:.2f}s\n")
    
    if (summary.get("success") is True and
        summary.get("dates_processed") == 1 and
        summary.get("targets") == 20 and
        summary.get("expected") == 20 and
        summary.get("image_inserted") == 20 and
        summary.get("missing_screenshots") == 0 and
        summary.get("missing_mappings") == 0 and
        summary.get("failed_inserts") == 0):
        print("[OK] All smoke test conditions passed.")
        return 0
    else:
        print("[FAIL] Smoke test conditions not met.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

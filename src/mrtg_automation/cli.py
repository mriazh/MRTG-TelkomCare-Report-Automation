import sys
from .shared.paths import ensure_directories
from .shared.logging import setup_logging
from .shared.validators import Validator

def print_menu():
    print("=" * 50)
    print("      MRTG TELKOMCARE REPORT AUTOMATION")
    print("=" * 50)
    print("1. Scrape MRTG screenshots")
    print("2. Generate Excel report")
    print("3. Scrape + Generate Excel")
    print("4. Validate config/templates/data")
    print("5. Migrate Legacy Data (Opsional)")
    print("6. Exit")
    print("=" * 50)

def run_cli():
    # Ensure directories exist on startup
    ensure_directories()
    # Setup minimal logging
    setup_logging()
    
    while True:
        print_menu()
        choice = input("Pilih menu (1-6): ").strip()
        
        if choice == '1':
            print("=> Menjalankan mode Scraper...")
            # Note: CLI parses date here, scraper will receive datetime objects
            pass
        elif choice == '2':
            print("=> Menjalankan mode Report Generator...")
            
            print("Pilih mode report:")
            print("1. Image Only")
            print("2. OCR + Image")
            report_choice = input("Pilihan (1/2): ").strip()
            
            if report_choice == '2':
                from .report.excel import ExcelReportGenerator
                from .config import Config
                from .shared.paths import CONFIG_DIR, DATA_DIR, TEMPLATES_DIR, REPORTS_DIR
                from .shared.logging import setup_ocr_logger
                
                # Setup OCR logger dynamically
                setup_ocr_logger()
                
                print("=> Menjalankan mode Report Generator (OCR + Image)...")
                date_filter = input("Masukkan tanggal untuk diproses (YYYYMMDD) atau tekan Enter untuk semua tanggal: ").strip()
                
                if date_filter and (len(date_filter) != 8 or not date_filter.isdigit()):
                    print("[!] Format tanggal harus YYYYMMDD, contoh 20260401")
                    continue
                
                mapping_file = CONFIG_DIR / "list_mrtg_data_position.txt"
                list_file = CONFIG_DIR / "list_mrtg_targets.csv"
                
                template_file = TEMPLATES_DIR / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
                legacy_template = TEMPLATES_DIR / "MRTG-Monthly-Report.xlsx"
                if not template_file.exists() and legacy_template.exists():
                    template_file = legacy_template
                    
                output_file = REPORTS_DIR / "MRTG-Monthly-Report-ocr.xlsx"
                
                print(f"Template: {template_file}")
                print(f"Mapping : {mapping_file}")
                print(f"Data Dir: {DATA_DIR}")
                if date_filter:
                    print(f"Filter Date: {date_filter}")
                
                cfg = Config()
                generator = ExcelReportGenerator(cfg)
                summary = generator.generate(
                    report_mode='OCR_IMAGE',
                    data_dir=DATA_DIR,
                    template_path=template_file,
                    output_path=output_file,
                    mapping_file=mapping_file,
                    list_file=list_file,
                    date_filter=date_filter if date_filter else None
                )
                
                if summary["success"]:
                    print(ExcelReportGenerator.format_summary_table(summary))
                    print("\nReport Summary:")
                    print(f"Dates processed    : {summary['dates_processed']}")
                    print(f"Targets per date   : {summary['targets']}")
                    print(f"Expected inserts   : {summary['expected']}")
                    print(f"Image inserted     : {summary['image_inserted']}")
                    print(f"OCR OK             : {summary['ocr_ok']}")
                    print(f"OCR Partial        : {summary['ocr_partial']}")
                    print(f"OCR Fail           : {summary['ocr_fail']}")
                    print(f"Missing screenshots: {summary['missing_screenshots']}")
                    print(f"Missing mappings   : {summary['missing_mappings']}")
                    print(f"Failed inserts     : {summary['failed_inserts']}")
                    print(f"Output             : {summary['output_file']}")
                    
                    if summary['review_list']:
                        print("\n[!] TARGETS NEEDING REVIEW (Partial/Fail OCR):")
                        for item in summary['review_list']:
                            print(f" - {item['target_id']} (Tgl: {item['date']}, Sheet: {item['sheet']}) -> {item['status']} (N/A: {item['na_count']})")
                    
                    print("\n[OK] Berhasil membuat report!")
                else:
                    print("[FAIL] Gagal membuat report. Silakan cek error atau log di output/logs/app.log")
            elif report_choice == '1':
                from .report.excel import ExcelReportGenerator
                from .config import Config
                from .shared.paths import CONFIG_DIR, DATA_DIR, TEMPLATES_DIR, REPORTS_DIR
                
                # Hardcoded defaults for Milestone 2 testing
                mapping_file = CONFIG_DIR / "list_mrtg_data_position_img_only.txt"
                list_file = CONFIG_DIR / "list_mrtg_targets.csv"
                
                template_file = TEMPLATES_DIR / "MRTG-Monthly-Report-image-only.xlsx"
                legacy_template = TEMPLATES_DIR / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
                
                if not template_file.exists() and legacy_template.exists():
                    template_file = legacy_template
                    
                output_file = REPORTS_DIR / "MRTG-Monthly-Report-image-only.xlsx"
                
                print(f"Template: {template_file}")
                print(f"Mapping : {mapping_file}")
                print(f"Data Dir: {DATA_DIR}")
                
                cfg = Config()
                generator = ExcelReportGenerator(cfg)
                summary = generator.generate(
                    report_mode='IMAGE_ONLY',
                    data_dir=DATA_DIR,
                    template_path=template_file,
                    output_path=output_file,
                    mapping_file=mapping_file,
                    list_file=list_file
                )
                if summary["success"]:
                    print("\nReport Summary:")
                    print(f"Dates processed    : {summary['dates_processed']}")
                    print(f"Targets per date   : {summary['targets']}")
                    print(f"Expected inserts   : {summary['expected']}")
                    print(f"Success inserts    : {summary['image_inserted']}")
                    print(f"Missing screenshots: {summary['missing_screenshots']}")
                    print(f"Missing mappings   : {summary['missing_mappings']}")
                    print(f"Failed inserts     : {summary['failed_inserts']}")
                    print(f"Output             : {summary['output_file']}")
                    print("\n[OK] Berhasil membuat report!")
                else:
                    print("[FAIL] Gagal membuat report. Silakan cek log di output/logs/app.log")
            else:
                print("[!] Pilihan tidak valid.")
                
        elif choice == '3':
            print("=> Menjalankan Full Pipeline...")
            pass
        elif choice == '4':
            Validator.run_all_checks()
        elif choice == '5':
            print("=> Migrating legacy MRTG_<SID>.png to canonical format...")
            from .shared.migration import migrate_legacy_data
            from .shared.paths import DATA_DIR
            
            print("1. Dry Run (Simulasi)")
            print("2. Execute (Ubah nama file beneran)")
            mig_choice = input("Pilihan (1/2): ").strip()
            
            if mig_choice == '1':
                migrate_legacy_data(DATA_DIR, dry_run=True)
            elif mig_choice == '2':
                confirm = input("Ketik 'y' atau 'yes' untuk melanjutkan proses eksekusi rename: ").strip().lower()
                if confirm in ('y', 'yes'):
                    migrate_legacy_data(DATA_DIR, dry_run=False)
                else:
                    print("Eksekusi dibatalkan karena konfirmasi tidak sesuai.")
            else:
                print("Pilihan tidak valid dibatalkan.")
        elif choice == '6':
            print("Exiting program.")
            break
        else:
            print("[!] Pilihan tidak valid.")

import datetime
from pathlib import Path

def run_scrape_command(date_str: str, targets_filter: str = "image", headless: bool = False) -> int:
    """
    Run scrape-only command for one date.
    """
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        print("[FAIL] Invalid date format. Must be YYYYMMDD")
        return 1

    ensure_directories()
    setup_logging()

    from .shared.paths import CONFIG_DIR
    from .report.mapping import parse_target_list

    target_file = CONFIG_DIR / "list_mrtg_targets.csv"

    if targets_filter == "image":
        items = parse_target_list(target_file, enabled_for="image")
    elif targets_filter == "ocr":
        items = parse_target_list(target_file, enabled_for="ocr")
    elif targets_filter == "all":
        items = parse_target_list(target_file, enabled_for=None)
    else:
        print("[FAIL] --targets must be one of: image, ocr, all")
        return 1

    sid_targets = []
    graphtitle_targets = []

    for _, target_type, target_id in items:
        t = target_type.strip().lower()
        if t == "sid":
            sid_targets.append(target_id)
        elif t in ("graph-title", "graphtitle"):
            graphtitle_targets.append(target_id)
        else:
            print(f"[WARN] Unknown target type skipped: {target_type} {target_id}")

    print("=" * 70)
    print("COMMAND: Scrape")
    print(f"Date: {date_str}")
    print(f"Target filter: {targets_filter}")
    print(f"SID count: {len(sid_targets)}")
    print(f"Graph-title count: {len(graphtitle_targets)}")
    print(f"Total count: {len(items)}")
    print("=" * 70)

    if not items:
        print("[FAIL] No targets selected")
        return 1

    from .scraper.telkomcare import TelkomCareScraper
    scraper = TelkomCareScraper(headless=headless)

    try:
        print("Logging in...")
        if not scraper.login():
            print("[FAIL] Login failed")
            return 1

        results_all = {}

        if sid_targets:
            print(f"\nScraping {len(sid_targets)} SID targets...")
            results_sid = scraper.scrape(targets=sid_targets, dates=[date_obj], mode="sid")
            if results_sid:
                results_all.update(results_sid)

        if graphtitle_targets:
            print(f"\nScraping {len(graphtitle_targets)} Graph-title targets...")
            results_gt = scraper.scrape(targets=graphtitle_targets, dates=[date_obj], mode="graphtitle")
            if results_gt:
                results_all.update(results_gt)

        print("\n" + "-" * 70)
        passed = 0
        na_count = 0
        failed_count = 0

        for _, _, target in items:
            filepath = results_all.get(target, {}).get(date_obj)
            status_info = scraper.last_statuses.get((target, date_obj), {})

            if filepath:
                p = Path(filepath)
                if p.exists() and p.stat().st_size > 0:
                    print(f"[OK] {target} -> {p}")
                    passed += 1
                else:
                    print(f"[FAIL] {target} (file empty or missing at {p})")
                    failed_count += 1
            elif status_info.get("status") == "no_graph":
                print(f"[N/A] {target} (TelkomCare returned No graph)")
                na_count += 1
            else:
                err_msg = status_info.get('error') or "no filepath returned"
                print(f"[FAIL] {target} (status: {status_info.get('status')}, error: {err_msg})")
                failed_count += 1

        print("-" * 70)
        print(f"SUMMARY: {passed} OK, {na_count} N/A, {failed_count} FAIL, {len(items)} total")

        if failed_count == 0:
            return 0
        return 1
    finally:
        scraper.close()

import os

def run_report_command(mode: str, date_str: str = None, no_images: bool = False) -> int:
    ensure_directories()
    setup_logging()

    if date_str:
        if len(date_str) != 8 or not date_str.isdigit():
            print("[FAIL] Date format must be YYYYMMDD")
            return 1

    if no_images:
        os.environ["INSERT_IMAGES"] = "False"

    from .report.excel import ExcelReportGenerator
    from .config import Config
    from .shared.paths import CONFIG_DIR, DATA_DIR, TEMPLATES_DIR, REPORTS_DIR

    if mode == "image":
        report_mode = "IMAGE_ONLY"
        mapping_file = CONFIG_DIR / "list_mrtg_data_position_img_only.txt"
        list_file = CONFIG_DIR / "list_mrtg_targets.csv"
        template_file = TEMPLATES_DIR / "MRTG-Monthly-Report-image-only.xlsx"
        fallback_template = TEMPLATES_DIR / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
        output_file = REPORTS_DIR / "MRTG-Monthly-Report-image-only.xlsx"
    elif mode == "ocr":
        report_mode = "OCR_IMAGE"
        mapping_file = CONFIG_DIR / "list_mrtg_data_position.txt"
        list_file = CONFIG_DIR / "list_mrtg_targets.csv"
        template_file = TEMPLATES_DIR / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
        fallback_template = TEMPLATES_DIR / "MRTG-Monthly-Report.xlsx"
        output_file = REPORTS_DIR / "MRTG-Monthly-Report-ocr.xlsx"
        from .shared.logging import setup_ocr_logger
        setup_ocr_logger()
    else:
        print("[FAIL] Mode must be image or ocr")
        return 1

    if not template_file.exists() and fallback_template.exists():
        template_file = fallback_template

    print("=" * 70)
    print("COMMAND: Report")
    print(f"Mode: {mode}")
    print(f"Template: {template_file}")
    print(f"Mapping: {mapping_file}")
    print(f"Target List: {list_file}")
    print(f"Data Dir: {DATA_DIR}")
    print(f"Output: {output_file}")
    if date_str:
        print(f"Date filter: {date_str}")
    if no_images:
        print("Images disabled via --no-images")
    print("=" * 70)

    cfg = Config()
    generator = ExcelReportGenerator(cfg)
    summary = generator.generate(
        report_mode=report_mode,
        data_dir=DATA_DIR,
        template_path=template_file,
        output_path=output_file,
        mapping_file=mapping_file,
        list_file=list_file,
        date_filter=date_str
    )

    print("\nReport Summary:")
    print(f"Dates processed    : {summary.get('dates_processed', 0)}")
    print(f"Targets per date   : {summary.get('targets', 0)}")
    print(f"Expected inserts   : {summary.get('expected', 0)}")
    print(f"Image inserted     : {summary.get('image_inserted', 0)}")
    if mode == "ocr":
        print(f"OCR OK             : {summary.get('ocr_ok', 0)}")
        print(f"OCR Partial        : {summary.get('ocr_partial', 0)}")
        print(f"OCR Fail           : {summary.get('ocr_fail', 0)}")
    print(f"Missing screenshots: {summary.get('missing_screenshots', 0)}")
    print(f"Missing mappings   : {summary.get('missing_mappings', 0)}")
    print(f"Failed inserts     : {summary.get('failed_inserts', 0)}")
    print(f"Output             : {summary.get('output_file', '')}")

    if summary.get("success"):
        print("\n[OK] Report generated successfully.")
        return 0
    else:
        print("\n[FAIL] Failed to generate report.")
        return 1

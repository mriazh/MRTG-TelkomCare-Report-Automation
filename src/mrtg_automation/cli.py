import sys
import logging
from .shared.paths import ensure_directories
from .shared.logging import setup_logging
from .shared.validators import Validator

def log_run_boundary(label: str, message: str):
    logger = logging.getLogger("mrtg_automation.cli")
    line = "=" * 70
    logger.info(line)
    logger.info(f"{label}: {message}")
    logger.info(line)

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

def parse_cli_dates(date_str=None, start_date_str=None, end_date_str=None) -> list:
    if date_str:
        if len(date_str) != 8 or not date_str.isdigit():
            print(f"[FAIL] Invalid date format. Must be YYYYMMDD, got {date_str}")
            return []
        try:
            return [datetime.datetime.strptime(date_str, "%Y%m%d").date()]
        except ValueError:
            print(f"[FAIL] Invalid date {date_str}")
            return []

    if start_date_str and end_date_str:
        if len(start_date_str) != 8 or not start_date_str.isdigit() or len(end_date_str) != 8 or not end_date_str.isdigit():
            print("[FAIL] Date format must be YYYYMMDD")
            return []
        try:
            from .shared.dates import generate_date_range
            start_date = datetime.datetime.strptime(start_date_str, "%Y%m%d").date()
            end_date = datetime.datetime.strptime(end_date_str, "%Y%m%d").date()
            return generate_date_range(start_date, end_date)
        except ValueError as e:
            print(f"[FAIL] Invalid date range: {e}")
            return []

    print("[FAIL] You must provide either --date OR both --start-date and --end-date")
    return []

def run_scrape_command(date_str: str = None, targets_filter: str = "image", headless: bool = False, start_date_str: str = None, end_date_str: str = None, manual_login_waiter=None, cancel_event=None, resume_state=None, resume_mode: bool = False) -> int:
    """
    Run scrape-only command for one or more dates.
    """
    dates = parse_cli_dates(date_str, start_date_str, end_date_str)
    if not dates:
        return 1

    ensure_directories()
    setup_logging()

    log_run_boundary("RUN START", f"scrape dates={len(dates)} targets={targets_filter}")

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
        log_run_boundary("RUN END", "scrape exit_code=1 invalid targets_filter")
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
    print(f"Date count: {len(dates)}")
    if len(dates) == 1:
        print(f"Date: {dates[0].strftime('%Y%m%d')}")
    else:
        print(f"Date range: {dates[0].strftime('%Y%m%d')} to {dates[-1].strftime('%Y%m%d')}")
    print(f"Target filter: {targets_filter}")
    print(f"SID count: {len(sid_targets)}")
    print(f"Graph-title count: {len(graphtitle_targets)}")
    print(f"Total count: {len(items)}")
    print("=" * 70)

    if not items:
        print("[FAIL] No targets selected")
        log_run_boundary("RUN END", "scrape exit_code=1 no targets selected")
        return 1

    if resume_state is not None:
        resume_state["total_items"] = len(items) * len(dates)
        from .shared.resume_state import save_resume_state
        save_resume_state(resume_state)

    from .scraper.telkomcare import TelkomCareScraper
    scraper = TelkomCareScraper(headless=headless, manual_login_waiter=manual_login_waiter, cancel_event=cancel_event)

    cancelled = False
    try:
        print("Logging in...")
        if not scraper.login():
            if (cancel_event is not None and cancel_event.is_set()) or getattr(scraper, "last_cancelled", False):
                print("[STOP] Scrape stopped during login.")
                log_run_boundary("RUN END", "scrape exit_code=130 stopped_during_login")
                return 130
            print("[FAIL] Login failed")
            log_run_boundary("RUN END", "scrape exit_code=1 login failed")
            return 1

        results_all = {}

        if sid_targets:
            print(f"\nScraping {len(sid_targets)} SID targets across {len(dates)} dates...")
            results_sid = scraper.scrape(targets=sid_targets, dates=dates, mode="sid", cancel_event=cancel_event, resume_state=resume_state, phase="scrape_sid", resume_mode=resume_mode)
            if getattr(scraper, "last_cancelled", False):
                cancelled = True
                log_run_boundary("RUN END", "scrape exit_code=130 stopped_by_user")
                return 130
            if results_sid:
                results_all.update(results_sid)

        if graphtitle_targets:
            if resume_state is not None:
                from .shared.resume_state import save_resume_state
                resume_state["current_phase"] = "scrape_graphtitle"
                save_resume_state(resume_state)

            print(f"\nScraping {len(graphtitle_targets)} Graph-title targets across {len(dates)} dates...")
            results_gt = scraper.scrape(targets=graphtitle_targets, dates=dates, mode="graphtitle", cancel_event=cancel_event, resume_state=resume_state, phase="scrape_graphtitle", resume_mode=resume_mode)
            if getattr(scraper, "last_cancelled", False):
                cancelled = True
                log_run_boundary("RUN END", "scrape exit_code=130 stopped_by_user")
                return 130
            if results_gt:
                results_all.update(results_gt)

        print("\n" + "-" * 70)
        passed = 0
        na_count = 0
        failed_count = 0

        for date_obj in dates:
            for _, _, target in items:
                filepath = results_all.get(target, {}).get(date_obj)
                status_info = scraper.last_statuses.get((target, date_obj), {})

                if filepath:
                    p = Path(filepath)
                    if p.exists() and p.stat().st_size > 0:
                        print(f"[OK] {target} ({date_obj.strftime('%Y%m%d')}) -> {p}")
                        passed += 1
                    else:
                        print(f"[FAIL] {target} ({date_obj.strftime('%Y%m%d')}) (file empty or missing at {p})")
                        failed_count += 1
                elif status_info.get("status") == "no_graph":
                    print(f"[N/A] {target} ({date_obj.strftime('%Y%m%d')}) (TelkomCare returned No graph)")
                    na_count += 1
                else:
                    err_msg = status_info.get('error') or "no filepath returned"
                    print(f"[FAIL] {target} ({date_obj.strftime('%Y%m%d')}) (status: {status_info.get('status')}, error: {err_msg})")
                    failed_count += 1

        print("-" * 70)
        total_expected = len(items) * len(dates)
        print(f"SUMMARY: {passed} OK, {na_count} N/A, {failed_count} FAIL, {total_expected} total")

        if failed_count == 0:
            if resume_state is not None:
                from .shared.resume_state import save_resume_state
                # Only set to done if caller is not full pipeline (which we can infer or let full pipeline override)
                if resume_state.get("operation_mode") == "Scrape":
                    resume_state["current_phase"] = "done"
                resume_state["next_item"] = None
                save_resume_state(resume_state)
            log_run_boundary("RUN END", f"scrape exit_code=0 ok={passed} na={na_count} fail={failed_count}")
            return 0
        log_run_boundary("RUN END", f"scrape exit_code=1 ok={passed} na={na_count} fail={failed_count}")
        return 1
    finally:
        if not cancelled:
            scraper.close()

import os

def run_report_command(mode: str, date_str: str = None, no_images: bool = False, start_date_str: str = None, end_date_str: str = None, cancel_event=None, resume_state=None, resume_mode: bool = False) -> int:
    ensure_directories()
    setup_logging()

    if date_str or (start_date_str and end_date_str):
        dates = parse_cli_dates(date_str, start_date_str, end_date_str)
        if not dates:
            return 1
        date_filter = date_str if len(dates) == 1 else [d.strftime("%Y%m%d") for d in dates]
    else:
        dates = []
        date_filter = None

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

    log_run_boundary("RUN START", f"report mode={mode} date_filter={date_filter}")

    print("=" * 70)
    print("COMMAND: Report")
    print(f"Mode: {mode}")
    print(f"Template: {template_file}")
    print(f"Mapping: {mapping_file}")
    print(f"Target List: {list_file}")
    print(f"Data Dir: {DATA_DIR}")
    print(f"Output: {output_file}")
    if dates:
        print(f"Date count: {len(dates)}")
        if len(dates) == 1:
            print(f"Date filter: {dates[0].strftime('%Y%m%d')}")
        else:
            print(f"Date range: {dates[0].strftime('%Y%m%d')} to {dates[-1].strftime('%Y%m%d')}")
    if no_images:
        print("Images disabled via --no-images")
    print("=" * 70)

    phase = "report_image" if mode == "image" else "report_ocr"
    if resume_state is not None:
        from .shared.resume_state import save_resume_state
        resume_state["current_phase"] = phase
        save_resume_state(resume_state)

    cfg = Config()
    generator = ExcelReportGenerator(cfg)
    summary = generator.generate(
        report_mode=report_mode,
        data_dir=DATA_DIR,
        template_path=template_file,
        output_path=output_file,
        mapping_file=mapping_file,
        list_file=list_file,
        date_filter=date_filter,
        cancel_event=cancel_event,
        resume_state=resume_state,
        resume_mode=resume_mode,
        phase=phase
    )

    if summary.get("cancelled"):
        print("[STOP] Report stopped by user.")
        log_run_boundary("RUN END", "report exit_code=130 stopped_by_user")
        return 130

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
        log_run_boundary("RUN END", "report exit_code=0 success=True")
        return 0
    else:
        print("\n[FAIL] Failed to generate report.")
        log_run_boundary("RUN END", "report exit_code=1 success=False")
        return 1

def run_full_command(
    date_str: str = None,
    targets_filter: str = "image",
    report_mode: str = "image",
    headless: bool = False,
    no_images: bool = False,
    start_date_str: str = None,
    end_date_str: str = None,
    manual_login_waiter=None,
    cancel_event=None,
    resume_state=None,
    resume_mode: bool = False
) -> int:
    ensure_directories()
    setup_logging()

    dates = parse_cli_dates(date_str, start_date_str, end_date_str)
    if not dates:
        return 1

    if targets_filter not in ["image", "ocr", "all"]:
        print("[FAIL] --targets must be one of: image, ocr, all")
        return 1

    if report_mode not in ["image", "ocr"]:
        print("[FAIL] --report-mode must be one of: image, ocr")
        return 1

    print("=" * 70)
    print("COMMAND: Full Pipeline")
    print(f"Date count: {len(dates)}")
    if len(dates) == 1:
        print(f"Date: {dates[0].strftime('%Y%m%d')}")
    else:
        print(f"Date range: {dates[0].strftime('%Y%m%d')} to {dates[-1].strftime('%Y%m%d')}")
    print(f"Target filter: {targets_filter}")
    print(f"Report mode: {report_mode}")
    print("=" * 70)

    log_run_boundary("RUN START", f"full targets={targets_filter} report_mode={report_mode}")

    scrape_exit_code = run_scrape_command(date_str, targets_filter, headless, start_date_str, end_date_str, manual_login_waiter, cancel_event, resume_state, resume_mode)
    if scrape_exit_code == 130:
        print("\n[STOP] Full pipeline stopped during scrape.")
        log_run_boundary("RUN END", "full exit_code=130 stopped_during_scrape")
        return 130
    elif scrape_exit_code != 0:
        print("\n[FAIL] Scrape step failed. Report step skipped.")
        log_run_boundary("RUN END", f"full exit_code={scrape_exit_code} (scrape failed)")
        return scrape_exit_code

    if resume_state is not None:
        from .shared.resume_state import save_resume_state
        resume_state["current_phase"] = "report_image" if report_mode == "image" else "report_ocr"
        save_resume_state(resume_state)

    report_exit_code = run_report_command(report_mode, date_str, no_images, start_date_str, end_date_str, cancel_event, resume_state, resume_mode)
    if report_exit_code == 130:
        print("\n[STOP] Full pipeline stopped during report.")
        log_run_boundary("RUN END", "full exit_code=130 stopped_during_report")
        return 130
    elif report_exit_code != 0:
        print("\n[FAIL] Report step failed.")
        log_run_boundary("RUN END", f"full exit_code={report_exit_code} (report failed)")
        return report_exit_code

    print("\n[OK] Full pipeline completed successfully.")
    log_run_boundary("RUN END", "full exit_code=0")
    return 0

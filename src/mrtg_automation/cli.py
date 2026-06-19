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

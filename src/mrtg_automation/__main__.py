import sys
import os
import argparse

from mrtg_automation.cli import run_cli, run_scrape_command, run_report_command

def main():
    parser = argparse.ArgumentParser(description="MRTG TelkomCare Report Automation")
    parser.add_argument("--no-images", action="store_true", help="Disable inserting images into Excel")
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    scrape_parser = subparsers.add_parser("scrape", help="Scrape MRTG screenshots only")
    scrape_parser.add_argument("--date", required=True, help="Date to scrape, YYYYMMDD")
    scrape_parser.add_argument("--targets", choices=["image", "ocr", "all"], default="image", help="Target filter")
    scrape_parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    
    report_parser = subparsers.add_parser("report", help="Generate Excel report only")
    report_parser.add_argument("--mode", choices=["image", "ocr"], required=True, help="Report mode")
    report_parser.add_argument("--date", help="Date to process, YYYYMMDD (optional, processes all if omitted)")
    report_parser.add_argument("--no-images", action="store_true", help="Disable inserting images into Excel")
    
    full_parser = subparsers.add_parser("full", help="Scrape screenshots and generate report")
    full_parser.add_argument("--date", required=True, help="Date to process, YYYYMMDD")
    full_parser.add_argument("--targets", choices=["image", "ocr", "all"], default="image")
    full_parser.add_argument("--report-mode", choices=["image", "ocr"], default="image")
    full_parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    full_parser.add_argument("--no-images", action="store_true", help="Disable inserting images into Excel")
    
    args = parser.parse_args()
    
    if getattr(args, 'no_images', False):
        os.environ["INSERT_IMAGES"] = "False"
        
    if args.command == "scrape":
        exit_code = run_scrape_command(args.date, args.targets, args.headless)
        sys.exit(exit_code)
    elif args.command == "report":
        exit_code = run_report_command(args.mode, args.date, getattr(args, 'no_images', False))
        sys.exit(exit_code)
    elif args.command == "full":
        from .cli import run_full_command
        exit_code = run_full_command(
            date_str=args.date,
            targets_filter=args.targets,
            report_mode=args.report_mode,
            headless=args.headless,
            no_images=getattr(args, "no_images", False),
        )
        sys.exit(exit_code)
        
    try:
        run_cli()
    except KeyboardInterrupt:
        print("\nExiting program.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL ERROR] Application crashed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()

import sys
import os
import argparse
from .cli import run_cli

def main():
    parser = argparse.ArgumentParser(description="MRTG TelkomCare Report Automation")
    parser.add_argument('--no-images', action='store_true', help="Skip image insertion in Excel output. Default: images included. Use --no-images for smaller file size (~9x reduction)")
    args = parser.parse_args()
    
    if args.no_images:
        os.environ['INSERT_IMAGES'] = 'False'

    try:
        run_cli()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL ERROR] Application crashed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

import sys
import datetime
from pathlib import Path
from mrtg_automation.scraper.telkomcare import TelkomCareScraper

def main():
    print("=" * 70)
    print("TEST: Scrape Graph-title 3784")
    print("=" * 70)
    
    target = "3784"
    test_date = datetime.date.today()
    
    scraper = TelkomCareScraper(headless=False)
    
    try:
        print("Logging in...")
        if not scraper.login():
            print("[FAIL] Login failed")
            return 1
            
        print(f"Scraping {target} for date {test_date}...")
        results = scraper.scrape(targets=[target], dates=[test_date], mode='graphtitle')
        
        if results is None:
            print("[FAIL] Scrape returned None")
            return 1
            
        filepath = results.get(target, {}).get(test_date)
        
        if filepath:
            p = Path(filepath)
            if p.exists() and p.stat().st_size > 0:
                print(f"[OK] Saved to {p}")
                return 0
            else:
                print(f"[FAIL] Could not save graph (file empty or missing at {p})")
                return 1
        else:
            print("[FAIL] Could not save graph (no filepath returned)")
            return 1
            
    finally:
        scraper.close()

if __name__ == "__main__":
    sys.exit(main())

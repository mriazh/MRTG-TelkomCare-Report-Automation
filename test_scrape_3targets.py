import sys
import datetime
from pathlib import Path
from mrtg_automation.scraper.telkomcare import TelkomCareScraper

def main():
    print("=" * 70)
    print("TEST: Scrape 3 Targets (Multi-Target Smoke Test)")
    print("=" * 70)
    
    targets = [
        "4700001-0021497479",
        "4700001-0020265222",
        "4700001-0031020061",
    ]
    test_date = datetime.date.today()
    
    scraper = TelkomCareScraper(headless=False)
    
    try:
        print("Logging in...")
        if not scraper.login():
            print("[FAIL] Login failed")
            return 1
            
        print(f"Scraping 3 targets for date {test_date}...")
        results = scraper.scrape(targets=targets, dates=[test_date], mode='sid')
        
        if results is None:
            print("[FAIL] Scrape returned None")
            return 1
            
        date_str = test_date.strftime("%Y%m%d")
        passed = 0
        
        for target in targets:
            filepath = results.get(target, {}).get(test_date)
            
            if filepath:
                p = Path(filepath)
                if p.exists() and p.stat().st_size > 0:
                    print(f"[OK] {target} -> {p}")
                    passed += 1
                else:
                    print(f"[FAIL] {target} (file empty or missing at {p})")
            else:
                print(f"[FAIL] {target} (no filepath returned)")
                
        print("-" * 70)
        print(f"SUMMARY: {passed}/{len(targets)} passed")
        
        if passed == len(targets):
            return 0
        return 1
            
    finally:
        scraper.close()

if __name__ == "__main__":
    sys.exit(main())

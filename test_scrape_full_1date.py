import sys
import datetime
import re
from pathlib import Path
from mrtg_automation.scraper.telkomcare import TelkomCareScraper

def parse_target_file(path: Path):
    sid_targets = []
    graphtitle_targets = []
    
    if not path.exists():
        print(f"[ERROR] Config file not found: {path}")
        return sid_targets, graphtitle_targets
        
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or ':' not in line:
                continue
                
            parts = line.split(':', 1)
            label = parts[0].strip().lower()
            target_id = parts[1].strip()
            
            if 'sid' in label:
                sid_targets.append(target_id)
            elif 'graph-title' in label or 'graphtitle' in label:
                graphtitle_targets.append(target_id)
                
    return sid_targets, graphtitle_targets

def main():
    print("=" * 70)
    print("TEST: Full 20-Target 1-Date Scrape")
    print("=" * 70)
    
    config_path = Path("config/list_mrtg_data_img_only.txt")
    sid_targets, graphtitle_targets = parse_target_file(config_path)
    
    test_date = datetime.date.today()
    all_targets = sid_targets + graphtitle_targets
    
    print(f"Parsed SID targets: {len(sid_targets)}")
    print(f"Parsed Graph-title targets: {len(graphtitle_targets)}")
    print(f"Total targets: {len(all_targets)}")
    
    if not all_targets:
        print("[FAIL] No targets found to test")
        return 1
        
    scraper = TelkomCareScraper(headless=False)
    
    try:
        print("\nLogging in...")
        if not scraper.login():
            print("[FAIL] Login failed")
            return 1
            
        results_all = {}
        
        if sid_targets:
            print(f"\nScraping {len(sid_targets)} SID targets for date {test_date}...")
            results_sid = scraper.scrape(targets=sid_targets, dates=[test_date], mode='sid')
            if results_sid:
                results_all.update(results_sid)
                
        if graphtitle_targets:
            print(f"\nScraping {len(graphtitle_targets)} Graph-title targets for date {test_date}...")
            results_gt = scraper.scrape(targets=graphtitle_targets, dates=[test_date], mode='graphtitle')
            if results_gt:
                results_all.update(results_gt)
                
        if not results_all:
            print("[FAIL] Scrape returned no results")
            return 1
            
        print("\n" + "-" * 70)
        passed = 0
        failed_targets = []
        
        for target in all_targets:
            filepath = results_all.get(target, {}).get(test_date)
            
            if filepath:
                p = Path(filepath)
                if p.exists() and p.stat().st_size > 0:
                    print(f"[OK] {target} -> {p}")
                    passed += 1
                else:
                    print(f"[FAIL] {target} (file empty or missing at {p})")
                    failed_targets.append(target)
            else:
                print(f"[FAIL] {target} (no filepath returned)")
                failed_targets.append(target)
                
        print("-" * 70)
        print(f"SUMMARY: {passed}/{len(all_targets)} passed")
        
        if failed_targets:
            print("Failed targets:")
            for t in failed_targets:
                print(f"  - {t}")
                
        if passed == len(all_targets):
            return 0
        return 1
            
    finally:
        scraper.close()

if __name__ == "__main__":
    sys.exit(main())

import sys
import datetime
import re
import csv
from pathlib import Path
from mrtg_automation.scraper.telkomcare import TelkomCareScraper

def parse_target_file(path: Path):
    sid_targets = []
    graphtitle_targets = []
    
    if not path.exists():
        print(f"[ERROR] Config file not found: {path}")
        return sid_targets, graphtitle_targets
        
    truthy = {"true", "1", "yes", "y"}
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("image_enabled", "").strip().lower() in truthy:
                target_type = row.get("type", "").strip().lower()
                target_id = row.get("target", "").strip()
                if 'sid' in target_type:
                    sid_targets.append(target_id)
                elif 'graph-title' in target_type or 'graphtitle' in target_type:
                    graphtitle_targets.append(target_id)
                    
    return sid_targets, graphtitle_targets

def main():
    print("=" * 70)
    print("TEST: Mixed Mode Scrape (Smoke Test)")
    print("=" * 70)
    
    config_path = Path("config/list_mrtg_targets.csv")
    sid_targets_all, graphtitle_targets_all = parse_target_file(config_path)
    
    sid_targets = sid_targets_all[:3]
    graphtitle_targets = graphtitle_targets_all[:1]
    test_date = datetime.date.today()
    
    print(f"Parsed SID targets: {len(sid_targets_all)} total, testing {len(sid_targets)}: {sid_targets}")
    print(f"Parsed Graph-title targets: {len(graphtitle_targets_all)} total, testing {len(graphtitle_targets)}: {graphtitle_targets}")
    
    all_targets = sid_targets + graphtitle_targets
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
        
        for target in all_targets:
            filepath = results_all.get(target, {}).get(test_date)
            
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
        print(f"SUMMARY: {passed}/{len(all_targets)} passed")
        
        if passed == len(all_targets):
            return 0
        return 1
            
    finally:
        scraper.close()

if __name__ == "__main__":
    sys.exit(main())

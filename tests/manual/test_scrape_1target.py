import datetime
from mrtg_automation.scraper.telkomcare import TelkomCareScraper

def main():
    print("="*70)
    print("TEST: Scrape 1 Target")
    print("="*70)
    
    target = "4700001-0021497479"
    today = datetime.date.today()
    
    scraper = TelkomCareScraper(headless=False)
    
    try:
        print("Logging in...")
        if not scraper.login():
            print("Login failed!")
            return
            
        print(f"Scraping {target} for date {today}...")
        results = scraper.scrape(targets=[target], dates=[today], mode='sid')
        
        filepath = results.get(target, {}).get(today)
        if filepath:
            print(f"SUCCESS: Saved to {filepath}")
        else:
            print(f"FAILED: Could not save graph for {target}")
            
    finally:
        scraper.close()

if __name__ == "__main__":
    main()

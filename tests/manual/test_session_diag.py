import sys
import time
from pathlib import Path
from mrtg_automation.scraper.telkomcare import TelkomCareScraper
from mrtg_automation.config import Config
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from mrtg_automation.scraper.session import SessionManager

def main():
    print("=" * 70)
    print("DIAGNOSTIC TEST: SESSION PERSISTENCE")
    print("=" * 70)
    
    cfg = Config()
    scraper = TelkomCareScraper(headless=True)
    
    try:
        print("STEP 1: Login via TelkomCareScraper")
        success = scraper.login()
        if not success:
            print("  Login failed, but continuing diagnostics...")
            
        print("\nSTEP 2: Dump ALL cookies after login")
        cookies = scraper.session.driver.get_cookies()
        for c in cookies:
            print(f"  name={c.get('name')}, domain={c.get('domain')}, "
                  f"secure={c.get('secure')}, httpOnly={c.get('httpOnly')}, "
                  f"expiry={c.get('expiry', 'NONE (session cookie)')}, "
                  f"path={c.get('path')}")
        print(f"  Total cookies: {len(cookies)}")
        
        print("\nSTEP 3: Check profile cookie file size (Before Close)")
        profile = Path.home() / '.mrtg-scraper-profile'
        for f in ['Default/Cookies', 'Default/Network/Cookies']:
            p = profile / f
            if p.exists():
                print(f"  {f}: {p.stat().st_size} bytes, mtime={p.stat().st_mtime}")
            else:
                print(f"  {f}: NOT FOUND")
                
        print("\nSTEP 4: Close browser via scraper.close()")
        scraper.close()
        
        print("\nSTEP 5: Wait 5 seconds")
        time.sleep(5)
        
        print("\nSTEP 6: Check profile cookie file size (After Close)")
        for f in ['Default/Cookies', 'Default/Network/Cookies']:
            p = profile / f
            if p.exists():
                print(f"  {f}: {p.stat().st_size} bytes, mtime={p.stat().st_mtime}")
            else:
                print(f"  {f}: NOT FOUND")
                
    except Exception as e:
        print(f"  Exception during Step 1-6: {e}")
    finally:
        try:
            scraper.close()
        except:
            pass

    print("\nSTEP 7: Open new Chrome with SAME profile (headless=True)")
    driver = None
    try:
        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument(f'--user-data-dir={profile}')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        
        print("\nSTEP 8: Navigate to base URL")
        driver.get('http://telkomcare.telkom.co.id/mrtgnetcare2/graph/monitoring')
        time.sleep(3)
        
        print("\nSTEP 9: Dump current state")
        print(f"  URL: {driver.current_url}")
        print(f"  Title: {driver.title}")
        cookies_after = driver.get_cookies()
        print(f"  Cookies after reopen: {len(cookies_after)}")
        for c in cookies_after:
            print(f"    name={c.get('name')}, domain={c.get('domain')}, "
                  f"expiry={c.get('expiry', 'NONE')}")
                  
        print("\nSTEP 10: Check page content for login indicators")
        page = driver.page_source.lower()
        for kw in ['welcome', 'logged in', 'login', 'sign in', 'captcha', 
                   'dashboard', 'logout', 'mrtg', 'graph']:
            if kw in page:
                print(f"  Found keyword: '{kw}'")
                
        print("\nSTEP 11: Try is_logged_in()")
        sm = SessionManager(headless=True)
        sm.driver = driver
        print(f"  is_logged_in(): {sm.is_logged_in()}")
        
    except Exception as e:
        print(f"  Exception during Step 7-11: {e}")
    finally:
        print("\nCleaning up...")
        if driver:
            try:
                driver.quit()
            except:
                pass
                
    print("\n" + "=" * 70)
    print("DIAGNOSTIC TEST COMPLETE")
    print("=" * 70)

if __name__ == '__main__':
    main()

"""
Test real TelkomCare login flow.

Run from repo root:
  .venv312\\Scripts\\python test_login.py

Flow:
  1. Instantiate TelkomCareScraper (headless=True by default)
  2. Call login() - if session valid, done
  3. If not, browser opens (non-headless) for manual login
  4. User solves captcha, enters credentials, enters MFA code
  5. Test waits for user to press Enter at terminal
  6. Verifies login successful
  7. Closes browser

After successful test:
  - Profile at C:/Users/adima/.mrtg-scraper-profile contains cookies
  - Next test_login.py run should detect existing session and skip manual login
"""
import sys
import time
from mrtg_automation.scraper.telkomcare import TelkomCareScraper
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def main():
    print("=" * 70)
    print("TEST: TelkomCare Real Login Flow")
    print("=" * 70)
    print("This test will:")
    print("1. Open Chrome (headless first)")
    print("2. Check if session is valid")
    print("3. If not, switch to non-headless + prompt for manual login")
    print("=" * 70)
    
    # First try headless=True (assumes session already established from prior run)
    # If that fails, the login() method will switch to non-headless automatically
    scraper = TelkomCareScraper(headless=True)
    
    try:
        print("\nAttempting login...")
        start = time.time()
        success = scraper.login()
        elapsed = time.time() - start
        
        if success:
            print(f"\n[OK] LOGIN SUCCESS in {elapsed:.1f}s")
            print(f"     Current URL: {scraper.session.driver.current_url}")
            print(f"     Profile dir: {scraper.session.profile_dir}")
            
            # Optional: take a screenshot of dashboard for verification
            try:
                screenshot_path = scraper.session.profile_dir / 'dashboard_verification.png'
                scraper.session.driver.save_screenshot(str(screenshot_path))
                print(f"     Screenshot saved: {screenshot_path}")
            except Exception as e:
                print(f"     (Screenshot failed: {e})")
            
            print("\nTest #2: Re-opening session to verify cookies persist...")
            scraper.close()
            time.sleep(2)
            
            # Re-open and check if logged in automatically
            scraper2 = TelkomCareScraper(headless=True)
            scraper2.session.start()
            scraper2.session.driver.get(scraper2.base_url)
            # Wait for page to fully load before checking login status
            try:
                WebDriverWait(scraper2.session.driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == 'complete'
                )
                time.sleep(1)
            except Exception:
                pass
            
            if scraper2.session.is_logged_in():
                print("[OK] Session persisted! Cookies work for next run.")
            else:
                print("[WARN] Session did NOT persist. May need to keep browser open during scraper run, or check profile.")
            
            scraper2.close()
        else:
            print("\n[FAIL] LOGIN FAILED")
            print("Check error messages above and verify TelkomCare is accessible.")
            return 1
    except KeyboardInterrupt:
        print("\n\nCancelled by user. Cleaning up...")
        scraper.close()
        return 130
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            scraper.close()
        except:
            pass
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    return 0

if __name__ == '__main__':
    sys.exit(main())

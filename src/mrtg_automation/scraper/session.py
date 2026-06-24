"""
Session manager for persistent Chrome profile.

Used by TelkomCare scraper to maintain login session across runs.
Captcha + MFA cannot be automated; user must solve them manually
on first run after profile is cleared. Subsequent runs reuse cookies.
"""
import os
import logging
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger('mrtg_automation.scraper.session')

# URL patterns for login detection
LOGIN_URL_PATTERNS = ['/login', '/signin', '/auth']
DASHBOARD_URL_PATTERNS = ['/mrtg', '/graph', '/monitoring', '/dashboard']
COOKIE_FILE_NAME = 'cookies.json'


class SessionManager:
    """Manages a persistent Chrome session with TelkomCare.
    
    Profile dir: ~/.mrtg-scraper-profile (or override via profile_dir arg)
    Headless: True by default, but auto-detects login redirect and switches
              to non-headless if user needs to solve captcha + MFA.
    """
    
    def __init__(self, profile_dir: str = None, headless: bool = True, base_url: str = 'http://telkomcare.telkom.co.id', manual_login_waiter=None):
        self.profile_dir = Path(profile_dir) if profile_dir else Path.home() / '.mrtg-scraper-profile'
        self.headless = headless
        self.base_url = base_url
        self.driver = None
        self.manual_login_waiter = manual_login_waiter
    
    def _build_options(self) -> Options:
        opts = Options()
        if self.headless:
            opts.add_argument('--headless=new')
        opts.add_argument(f'--user-data-dir={self.profile_dir}')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        opts.add_experimental_option('excludeSwitches', ['enable-logging'])
        return opts
    
    def start(self) -> None:
        """Launch Chrome with persistent profile. Idempotent (no-op if already started)."""
        if self.driver is not None:
            logger.debug("SessionManager.start() called but already running")
            return
        
        # Ensure profile dir exists
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        opts = self._build_options()
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=opts)
        logger.info(f"Chrome started with profile: {self.profile_dir}")
    
    def is_logged_in(self) -> bool:
        """Check if current page is dashboard (not login).
        
        Uses two-layer detection:
        1. URL pattern (fast, primary)
        2. Page content check (fallback, more reliable)
        
        Returns True if on dashboard, False if on login or driver not started.
        """
        if self.driver is None:
            return False
        current_url = self.driver.current_url.lower()
        
        # Layer 1: URL pattern check
        is_login = any(p in current_url for p in LOGIN_URL_PATTERNS)
        if is_login:
            return False
        is_dashboard = (
            any(p in current_url for p in DASHBOARD_URL_PATTERNS)
            or current_url.rstrip('/') == self.base_url.rstrip('/')
        )
        if is_dashboard:
            return True
        
        # Layer 2: Page content check (fallback)
        # If URL doesn't clearly match, check page content for login indicators
        try:
            page_source = self.driver.page_source.lower()
            has_login_form = any(kw in page_source for kw in ['login', 'sign in', 'captcha', 'username', 'password'])
            has_dashboard = any(kw in page_source for kw in ['welcome', 'logged in', 'dashboard', 'logout', 'sign out'])
            if has_dashboard and not has_login_form:
                return True
        except Exception:
            pass
        
        return False
    
    def save_cookies(self) -> bool:
        """Export all cookies to JSON file for session persistence.
        
        Returns True if saved successfully, False on error.
        """
        if self.driver is None:
            logger.warning("No driver running, cannot save cookies")
            return False
        try:
            cookies = self.driver.get_cookies()
            cookie_path = self.profile_dir / COOKIE_FILE_NAME
            with open(cookie_path, 'w') as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"Saved {len(cookies)} cookies to {cookie_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")
            return False

    def load_cookies(self) -> bool:
        """Import cookies from JSON file. Must navigate to domain first.
        
        Returns True if cookies loaded and applied, False on error or no file.
        """
        cookie_path = self.profile_dir / COOKIE_FILE_NAME
        if not cookie_path.exists():
            logger.info(f"No cookie file found at {cookie_path}")
            return False
        try:
            with open(cookie_path, 'r') as f:
                cookies = json.load(f)
            if not cookies:
                logger.info("Cookie file is empty")
                return False
            
            # Navigate to base domain first (required for add_cookie)
            self.driver.get(self.base_url)
            
            # Clear existing cookies to avoid duplicates
            self.driver.delete_all_cookies()
            
            # Add saved cookies
            loaded = 0
            for cookie in cookies:
                try:
                    # Remove unsupported keys
                    cookie.pop('sameSite', None)
                    cookie.pop('storeId', None)
                    cookie.pop('hostOnly', None)
                    cookie.pop('session', None)
                    # Fix expiry type (float -> int)
                    if isinstance(cookie.get('expiry'), float):
                        cookie['expiry'] = int(cookie['expiry'])
                    self.driver.add_cookie(cookie)
                    loaded += 1
                except Exception as e:
                    logger.debug(f"Skipping cookie {cookie.get('name', '?')}: {e}")
            
            logger.info(f"Loaded {loaded}/{len(cookies)} cookies from {cookie_path}")
            return loaded > 0
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return False

    def wait_for_manual_login(self) -> None:
        """Switch to non-headless mode and pause for user to login.
        
        If currently headless, restart browser in non-headless mode.
        Prints prompt, waits for user to press Enter after solving captcha + MFA.
        """
        if self.driver is not None and self.headless:
            # Need to restart in non-headless mode
            self.close()
        
        # Switch off headless for this session
        original_headless = self.headless
        self.headless = False
        
        try:
            self.start()
            self.driver.get(self.base_url)
            print("\n" + "=" * 70)
            print("MANUAL LOGIN REQUIRED")
            print("=" * 70)
            print("1. Browser is now open (non-headless) for you to see")
            print("2. Navigate to TelkomCare login page if not already there")
            print("3. Solve the captcha (image-based, e.g., 'c8g')")
            print("4. Enter username + password")
            print("5. Open Microsoft Authenticator app on your phone")
            print("6. Enter the 6-digit OTP code shown in app")
            print("7. Wait until you see the MRTG dashboard")
            print("8. Come back here and press Enter to continue")
            print("=" * 70)
            if self.manual_login_waiter is not None:
                self.manual_login_waiter()
            else:
                input("\nPress Enter after login is complete and dashboard is visible...")
            logger.info("User completed manual login")
        finally:
            # Keep headless=False until next start() call, but allow
            # subsequent calls to use original headless setting
            self.headless = original_headless
    
    def close(self) -> None:
        """Quit browser and release resources. Idempotent."""
        if self.driver is not None:
            try:
                # Wait for cookies to flush to disk
                import time
                time.sleep(3)
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error quitting browser: {e}")
            self.driver = None
            logger.debug("Chrome closed")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

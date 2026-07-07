"""
Session manager for persistent browser profile.

Used by TelkomCare scraper to maintain login session across runs.
Supports automatic Gemini CAPTCHA solving + TOTP login with manual fallback.
Subsequent runs reuse cookies for persistence.
"""
import logging
import json
from pathlib import Path
import time
import pyotp
import base64
import urllib.request
import urllib.error
import re
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager, ChromeType
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

logger = logging.getLogger('mrtg_automation.scraper.session')

# URL patterns for login detection
LOGIN_URL_PATTERNS = ['/login', '/signin', '/auth']
DASHBOARD_URL_PATTERNS = ['/mrtg', '/graph', '/monitoring', '/dashboard']
COOKIE_FILE_NAME = 'cookies.json'


class SessionManager:
    """Manages a persistent browser session with TelkomCare.

    Profile dir: ~/.mrtg-scraper-profile (or override via profile_dir arg)
    Supports Chrome, Chromium, Firefox, and Edge via config.
    Supports automatic Gemini CAPTCHA solving + TOTP login with manual fallback.
    """

    def __init__(self, profile_dir: str = None, headless: bool = True, base_url: str = 'http://telkomcare.telkom.co.id', manual_login_waiter=None, cancel_event=None, config=None):
        self.profile_dir = Path(profile_dir) if profile_dir else Path.home() / '.mrtg-scraper-profile'
        self.headless = headless
        self.base_url = base_url
        self.driver = None
        self.manual_login_waiter = manual_login_waiter
        self.cancel_event = cancel_event
        if config is None:
            from mrtg_automation.config import Config
            config = Config()
        self.config = config

    def _is_cancelled(self):
        return self.cancel_event is not None and self.cancel_event.is_set()

    def _build_options(self):
        browser_type = self.config.browser_type
        browser_binary = self.config.browser_binary

        if browser_type == 'firefox':
            opts = FirefoxOptions()
            if self.headless:
                opts.add_argument('--headless')
            if browser_binary:
                opts.binary_location = browser_binary
            return opts
        elif browser_type == 'edge':
            opts = EdgeOptions()
            if self.headless:
                opts.add_argument('--headless=new')
            if browser_binary:
                opts.binary_location = browser_binary
            opts.add_argument('--window-size=1920,1080')
            return opts
        else:
            opts = ChromeOptions()
            if self.headless:
                opts.add_argument('--headless=new')
            opts.add_argument(f'--user-data-dir={self.profile_dir}')
            opts.add_argument('--no-sandbox')
            opts.add_argument('--disable-dev-shm-usage')
            opts.add_argument('--window-size=1920,1080')
            opts.add_experimental_option('excludeSwitches', ['enable-logging'])
            if browser_binary:
                opts.binary_location = browser_binary
            return opts

    def start(self) -> bool:
        """Launch browser with persistent profile. Idempotent (no-op if already started).
        Supports chrome, chromium, firefox, edge via self.config.browser_type."""
        if self._is_cancelled(): return False

        if self.driver is not None:
            logger.debug("SessionManager.start() called but already running")
            return True

        # Ensure profile dir exists
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        opts = self._build_options()
        browser_type = self.config.browser_type

        try:
            if browser_type == 'firefox':
                service = FirefoxService(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service, options=opts)
                logger.info(f"Firefox started with profile: {self.profile_dir}")
            elif browser_type == 'edge':
                service = EdgeService(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=service, options=opts)
                logger.info(f"Edge started with profile: {self.profile_dir}")
            else:
                chrome_type = ChromeType.CHROMIUM if browser_type == 'chromium' else ChromeType.GOOGLE
                driver_path = ChromeDriverManager(chrome_type=chrome_type).install()
                service = ChromeService(driver_path)
                self.driver = webdriver.Chrome(service=service, options=opts)
                browser_name = 'Chromium' if browser_type == 'chromium' else 'Chrome'
                logger.info(f"{browser_name} started with profile: {self.profile_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to start {browser_type} driver: {e}")
            self.driver = None
            return False

    def is_logged_in(self) -> bool:
        """Check if current page is authenticated dashboard (not login/MFA).

        Uses path-aware URL detection:
        1. Return False for /public/login or /public/mfa paths.
        2. Return True only for /mrtgnetcare2 or /mrtgnetcare2/... paths.
        3. Page-content fallback only when URL is not a /public/... route.

        Returns True if on dashboard, False if on login, MFA, or driver not started.
        """
        if self.driver is None:
            return False
        current_url = self.driver.current_url
        parsed = urlparse(current_url)
        path = parsed.path.lower()

        # Layer 1: Explicitly reject known public/login routes
        if path.startswith('/public/login') or path.startswith('/public/mfa'):
            return False

        # Layer 2: Accept only the authenticated dashboard path
        if path == '/mrtgnetcare2' or path.startswith('/mrtgnetcare2/'):
            return True

        # Layer 3: Page-content fallback (only for non-public URLs)
        if not path.startswith('/public/'):
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

    def wait_for_manual_login(self) -> bool:
        """Pause for user to login manually.

        Requires the current session to already be non-headless (visible mode).
        Closes existing driver, opens a new one on the base URL, prompts user
        to solve CAPTCHA + MFA, then saves cookies and restarts the driver
        with the original headless setting.

        Returns True if login completed and session cookies saved.
        Returns False if cancelled or login failed.
        """
        if self._is_cancelled(): return False

        # Save the current headless state to restore afterward.
        original_headless = self.headless

        # Always close existing driver before starting fresh for login
        self.close()

        try:
            if self._is_cancelled(): return False

            if self.headless:
                logger.warning("wait_for_manual_login called in headless mode — browser will stay headless, user will not see the login page.")

            self.start()
            if self._is_cancelled(): return False
            self.driver.get(self.base_url)
            if self._is_cancelled(): return False
            print("\n" + "=" * 70)
            print("MANUAL LOGIN REQUIRED")
            print("=" * 70)
            visible = "visible" if not self.headless else "headless"
            print(f"1. Browser is now open ({visible}) for you to interact")
            print("2. Navigate to TelkomCare login page if not already there")
            print("3. Solve the captcha (image-based, e.g., 'c8g')")
            print("4. Enter username + password")
            print("5. Open Microsoft Authenticator app on your phone")
            print("6. Enter the 6-digit OTP code shown in app")
            print("7. Wait until you see the MRTG dashboard")
            print("8. Come back here and press Enter to continue")
            print("=" * 70)
            if self.manual_login_waiter is not None:
                result = self.manual_login_waiter()
                if result is False or self._is_cancelled():
                    print("[STOP] Manual login cancelled by user.")
                    return False
            else:
                input("\nPress Enter after login is complete and dashboard is visible...")
                if self._is_cancelled(): return False
            logger.info("Manual login detected. Saving cookies and restoring configured session.")
            if not self.save_cookies():
                logger.error("Failed to save cookies after login")
                self.close()
                self.headless = original_headless
                return False

            self.close()
            self.headless = original_headless

            if not self.start():
                logger.error("Failed to restart browser after login")
                return False

            if not self.load_cookies():
                logger.error("Failed to load cookies after manual login")
                self.close()
                return False

            self.driver.refresh()
            return True
        finally:
            # Always restore the configured headless setting
            self.headless = original_headless

    def close(self) -> None:
        """Quit browser and release resources. Idempotent."""
        if self.driver is not None:
            try:
                # Wait for cookies to flush to disk
                time.sleep(3)
                self.driver.quit()
            except BaseException as e:
                logger.debug(f"Silently closed browser: {e}")
            self.driver = None
            logger.debug("Chrome closed")

    def _solve_captcha_with_gemini(self, image_bytes: bytes) -> str:
        if not self.config.gemini_api_key:
            logger.warning("Gemini API key not configured")
            return ""
        
        import json
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Solve this text CAPTCHA. It is a 3-character alphanumeric string and may be case-sensitive. Output only the 3-character string; no explanation, markdown, punctuation, or newline."},
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                ]
            }]
        }
        data = json.dumps(payload).encode('utf-8')
        transient_codes = {429, 500, 502, 503, 504}
        
        for model in self.config.gemini_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.config.gemini_api_key}"
            for attempt in range(2):
                try:
                    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=self.config.LONG_TIMEOUT) as response:
                        res_json = json.loads(response.read().decode('utf-8'))
                        result = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                        if re.fullmatch(r"[A-Za-z0-9]{3}", result):
                            return result
                        logger.warning(f"Model {model} returned invalid output format")
                        break # Skip to next model
                except urllib.error.HTTPError as e:
                    if e.code in transient_codes and attempt < 1:
                        time.sleep(2)
                        continue
                    logger.warning(f"Model {model} failed with HTTP {e.code}")
                    break # Skip to next model
                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    break # Skip to next model
        return ""

    def _wait_for_mrtg_dashboard_ready(self) -> bool:
        """Wait for authenticated dashboard to be fully ready.

        Waits up to LONG_TIMEOUT for both URL prefix and dashboard nav element.
        Does not click anything.
        """
        try:
            WebDriverWait(self.driver, self.config.LONG_TIMEOUT,
                          ignored_exceptions=[StaleElementReferenceException]).until(
                lambda d: d.current_url.startswith("https://telkomcare.telkom.co.id/mrtgnetcare2")
                          and len(d.find_elements(By.XPATH, "//a[@data-id='2']")) > 0
            )
            return True
        except (TimeoutException, StaleElementReferenceException, Exception):
            return False

    def _complete_auto_login(self) -> bool:
        """Finalise auto-login: wait for dashboard, save cookies, keep driver alive."""
        if not self._wait_for_mrtg_dashboard_ready():
            return False
        try:
            self.save_cookies()
        except Exception:
            logger.warning("Cookie save failed but driver is authenticated")
        return True

    def auto_login(self) -> bool:
        """Attempt automated login using Gemini CAPTCHA solving + TOTP.

        Flow:
        1. Fill username (By.ID, "uname"), password (By.ID, "passw").
        2. Screenshot captcha image, solve via Gemini API.
        3. Fill captcha result into #captcha-input.
        4. Click agree checkbox (By.ID, "agree") if not selected.
        5. Click submit button (By.ID, "submit").
        6. On MFA page, fill 6 OTP boxes (input[name='otp[]']) with TOTP code.
        7. Validate login, save cookies, restart configured browser.

        Requires:
        - AUTO_LOGIN_ENABLED=true in config
        - TELKOM_USER and TELKOM_PASSWORD set
        - TOTP_SECRET configured
        - GEMINI_API_KEY configured

        Returns True if login succeeded, False if credentials missing or login failed.
        """
        if self._is_cancelled():
            return False

        if not self.config.auto_login_enabled:
            logger.debug("Auto-login disabled")
            return False

        if not self.config.telkom_user or not self.config.telkom_password:
            logger.warning("Auto-login enabled but TELKOM_USER or TELKOM_PASSWORD not set")
            return False

        if not self.config.totp_secret:
            logger.warning("Auto-login requires TOTP_SECRET to be configured")
            return False

        logger.info("Attempting automated login with Gemini CAPTCHA solving...")
        original_headless = self.headless
        for attempt in range(1, 4):
            if self._is_cancelled():
                return False
            try:
                # Check if already logged in from a previous attempt
                if self.is_logged_in():
                    logger.info("Auto-login: already logged in")
                    return self._complete_auto_login()

                # Navigate and wait for username field to be present
                print("[AUTO LOGIN] Opening TelkomCare login page...")
                self.driver.get(self.base_url)
                username_input = WebDriverWait(self.driver, self.config.WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.ID, "uname"))
                )
                password_input = self.driver.find_element(By.ID, "passw")

                username_input.clear()
                print("[AUTO LOGIN] Filling username and password...")
                username_input.send_keys(self.config.telkom_user)
                password_input.clear()
                password_input.send_keys(self.config.telkom_password)

                # Capture captcha image and solve via Gemini
                print("[AUTO LOGIN] Reading CAPTCHA with Gemini...")
                captcha_image = self.driver.find_element(By.CSS_SELECTOR, '#captcha-element img')
                png_bytes = captcha_image.screenshot_as_png
                captcha_text = self._solve_captcha_with_gemini(png_bytes)
                if not captcha_text:
                    print("[AUTO LOGIN] Gemini did not return a valid CAPTCHA; retrying.")
                    raise Exception("Gemini CAPTCHA solving failed, retrying...")

                captcha_input = self.driver.find_element(By.ID, "captcha-input")
                print("[AUTO LOGIN] Filling CAPTCHA, accepting terms, and submitting...")
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)

                # Click agree checkbox if not already selected
                agree_checkbox = self.driver.find_element(By.ID, "agree")
                if not agree_checkbox.is_selected():
                    self.driver.execute_script("arguments[0].click();", agree_checkbox)
                    logger.debug("Agree checkbox clicked")

                # Click submit button
                submit_btn = self.driver.find_element(By.ID, "submit")
                submit_btn.click()

                # After submit, wait for OTP fields, logged-in state, or CAPTCHA rejection
                print("[AUTO LOGIN] Waiting for MFA form...")
                try:
                    WebDriverWait(self.driver, self.config.WAIT_TIMEOUT,
                                  ignored_exceptions=[StaleElementReferenceException]).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, "input[name='otp[]']")) == 6
                                  or self.is_logged_in()
                                  or "/public/login/msg/" in d.current_url
                    )
                except Exception:
                    pass

                if "/public/login/msg/" in self.driver.current_url:
                    logger.warning("CAPTCHA rejected by TelkomCare; retrying with a fresh image.")
                    print("[AUTO LOGIN] CAPTCHA rejected; retrying with a fresh image.")
                    raise Exception("CAPTCHA rejected")

                if self.is_logged_in():
                    logger.info("Auto-login successful")
                    print("[AUTO LOGIN] Dashboard ready. Starting scrape...")
                    return self._complete_auto_login()

                # OTP page appeared - refetch inputs fresh
                otp_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[name='otp[]']")
                if len(otp_inputs) == 6:
                    print("[AUTO LOGIN] Filling TOTP; TelkomCare will submit automatically...")
                    totp_code = pyotp.TOTP(self.config.totp_secret).now()
                    for idx, char in enumerate(totp_code):
                        el = otp_inputs[idx]
                        self.driver.execute_script("arguments[0].removeAttribute('disabled');", el)
                        el.clear()
                        el.send_keys(char)
                    # Do NOT press Enter or click after OTP fill; wait for dashboard URL
                    print("[AUTO LOGIN] Waiting for MRTG dashboard...")
                    try:
                        WebDriverWait(self.driver, self.config.LONG_TIMEOUT,
                                      ignored_exceptions=[StaleElementReferenceException]).until(
                            lambda d: d.current_url.startswith("https://telkomcare.telkom.co.id/mrtgnetcare2")
                        )
                    except Exception:
                        pass
                    if self.is_logged_in():
                        logger.info("Auto-login successful after OTP")
                        print("[AUTO LOGIN] Dashboard ready. Starting scrape...")
                        return self._complete_auto_login()

                logger.warning(f"Auto-login attempt {attempt}/3 failed, retrying...")
                print("[AUTO LOGIN] MFA or dashboard did not complete; retrying.")
                try:
                    alert = self.driver.switch_to.alert
                    alert.accept()
                    time.sleep(1)
                except Exception:
                    pass

            except StaleElementReferenceException:
                logger.warning(f"Stale element on attempt {attempt}/3, retrying...")
                if attempt < 3:
                    time.sleep(2)
            except Exception as e:
                logger.warning(f"Auto-login attempt {attempt}/3 error: {e}")
                if attempt < 3:
                    time.sleep(2)

        logger.error("Auto-login failed after 3 attempts")
        print("[AUTO LOGIN] Automatic login did not complete; manual login required.")
        return False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

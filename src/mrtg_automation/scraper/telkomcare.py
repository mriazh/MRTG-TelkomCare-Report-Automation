"""
TelkomCare MRTG scraper.

Main entry point for M4 scraping pipeline.
Uses SessionManager for persistent Chrome profile and login handling.
"""
import logging
from datetime import date
from typing import List, Union
from pathlib import Path
from .session import SessionManager

logger = logging.getLogger('mrtg_automation.scraper.telkomcare')


class TelkomCareScraper:
    """Scraper for TelkomCare MRTG portal.
    
    Architecture:
    - SessionManager handles browser mechanics (profile, headless, login detection)
    - TelkomCareScraper handles orchestration (login, target loop, extraction)
    - Actual graph extraction (XPATH navigation + screenshot) is in P4 (next step)
    
    Usage:
        scraper = TelkomCareScraper(headless=True)
        scraper.login()  # User solves captcha + MFA if needed
        # P4: scraper.scrape(...)
    """
    
    def __init__(self, config=None, profile_dir: str = None, headless: bool = True, 
                 base_url: str = 'http://telkomcare.telkom.co.id/mrtgnetcare2/graph/monitoring', manual_login_waiter=None):
        self.config = config
        self.base_url = base_url
        self.headless = headless
        self.session = SessionManager(
            profile_dir=profile_dir,
            headless=headless,
            base_url=base_url,
            manual_login_waiter=manual_login_waiter
        )
        self.last_statuses = {}
        self._logged_in = False
        self.last_cancelled = False
    
    def login(self) -> bool:
        """Establish login session. Tries saved cookies first, then manual login.
        
        Flow:
        1. Start SessionManager (headless=True by default)
        2. Try loading saved cookies from profile
        3. Navigate to base_url
        4. If is_logged_in() returns True: done (cookies worked)
        5. If False: call wait_for_manual_login() for user to solve captcha + MFA
        6. After manual login, save cookies for next run
        
        Returns True if logged in (or login just completed), False on error.
        """
        try:
            logger.info("Starting login flow...")
            self.session.start()
            
            # Navigate to base URL — profile cookies from user-data-dir handle persistence
            self.session.driver.get(self.base_url)
            
            # Give page time to load
            import time
            time.sleep(2)
            
            if self.session.is_logged_in():
                logger.info("Session valid (cookies from Chrome profile)")
                self._logged_in = True
                return True
            
            logger.info("Session expired or first run - manual login required")
            self.session.wait_for_manual_login()
            
            # After manual login, verify it worked
            if self.session.is_logged_in():
                logger.info("Manual login successful")
                self._logged_in = True
                return True
            else:
                logger.error("Login flow did not result in dashboard page")
                return False
        except Exception as e:
            logger.error(f"Login flow failed: {e}")
            return False
    
    def scrape(self, targets: list[str], dates: list, 
               mode: str = 'sid', progress_callback=None, cancel_event=None) -> dict:
        """Scrape all targets for all dates. Browser stays alive for entire session."""
        if not self._logged_in:
            if not self.login():
                return None
        
        from .extractor import GraphExtractor
        extractor = GraphExtractor(self.session.driver, mode)
        
        # Navigate to graph page ONCE before the loop (Opsi A: browser stays alive)
        if not extractor.navigate_to_graph_page():
            logger.error("Failed to navigate to graph page")
            return None
        
        logger.info("Navigated to graph page, starting scrape loop...")
        results = {}
        
        total_items = len(dates) * len(targets)
        current_index = 0

        for date_obj in dates:
            date_str = date_obj.strftime('%Y%m%d')
            output_dir = Path('data/MRTG-Data') / date_str
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for target in targets:
                if cancel_event is not None and cancel_event.is_set():
                    print("[STOP] Scrape stop requested. Stopping before next item.")
                    logger.warning("[STOP] Scrape stop requested. Stopping before next item.")
                    self.last_cancelled = True
                    return results

                current_index += 1
                try:
                    prog_msg = f"[PROGRESS] {mode} {current_index}/{total_items} date={date_str} target={target} starting"
                    print(prog_msg)
                    logger.info(prog_msg)

                    filepath = extractor.capture_graph(target, date_obj)
                    
                    status_info = {
                        "status": getattr(extractor, 'last_status', None) or ("ok" if filepath else "error"),
                        "error": getattr(extractor, 'last_error', None),
                    }
                    self.last_statuses[(target, date_obj)] = status_info
                    
                    if filepath:
                        msg = f"[OK] {mode} {current_index}/{total_items} date={date_str} target={target} saved={filepath}"
                        print(msg)
                        logger.info(msg)
                        if target not in results:
                            results[target] = {}
                        results[target][date_obj] = str(filepath)
                    elif status_info.get("status") == "no_graph":
                        msg = f"[N/A] {mode} {current_index}/{total_items} date={date_str} target={target} no graph"
                        print(msg)
                        logger.info(msg)
                    else:
                        err = status_info.get("error") or "unknown"
                        msg = f"[FAIL] {mode} {current_index}/{total_items} date={date_str} target={target} error={err}"
                        print(msg)
                        logger.error(msg)

                    if progress_callback:
                        progress_callback(target, date_obj, filepath is not None)
                except Exception as e:
                    msg = f"[FAIL] {mode} {current_index}/{total_items} date={date_str} target={target} error={e}"
                    print(msg)
                    logger.error(msg)
                    results.setdefault(target, {})[date_obj] = None
        
        return results
    
    def close(self):
        """Close browser session. Idempotent."""
        self._logged_in = False
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

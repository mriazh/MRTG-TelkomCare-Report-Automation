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
                 base_url: str = 'http://telkomcare.telkom.co.id/mrtgnetcare2/graph/monitoring'):
        self.config = config
        self.session = SessionManager(
            profile_dir=profile_dir,
            headless=headless,
            base_url=base_url
        )
        self.base_url = base_url
        self._logged_in = False
    
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
               mode: str = 'sid', progress_callback=None) -> dict:
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
        
        for date_obj in dates:
            date_str = date_obj.strftime('%Y%m%d')
            output_dir = Path('data/MRTG-Data') / date_str
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for target in targets:
                try:
                    filepath = extractor.capture_graph(target, date_obj)
                    logger.info(f"  [{date_str}] {target}: {'OK' if filepath else 'FAIL'}")
                    results.setdefault(target, {})[date_obj] = filepath
                    status = "OK" if filepath else "FAIL"
                    if progress_callback:
                        progress_callback(target, date_obj, filepath is not None)
                except Exception as e:
                    logger.error(f"Failed {target} {date_str}: {e}")
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

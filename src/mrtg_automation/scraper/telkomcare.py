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
from mrtg_automation.shared.resume_state import get_completed_item_keys, mark_item_completed, save_resume_state, make_item_key, count_completed_items_for_phase
from mrtg_automation.shared.filenames import get_screenshot_path

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

            # Navigate to base URL - profile cookies from user-data-dir handle persistence
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
               mode: str = 'sid', progress_callback=None, cancel_event=None, resume_state=None, phase=None, resume_mode=False) -> dict:
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

        phase = phase or ("scrape_sid" if mode == "sid" else "scrape_graphtitle")
        completed_keys = get_completed_item_keys(resume_state) if resume_state and resume_mode else set()

        def find_completed_item(key):
            if not resume_state:
                return None
            for item in resume_state.get("completed_items", []):
                if item.get("key") == key:
                    return item
            return None

        if resume_state is not None:
            resume_state["status"] = "running"
            resume_state["current_phase"] = phase
            resume_state["phase_total_items"] = total_items
            resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, phase)
            if not resume_state.get("total_items"):
                resume_state["total_items"] = total_items
            save_resume_state(resume_state)

        for date_obj in dates:
            date_str = date_obj.strftime('%Y%m%d')
            output_dir = Path('data/MRTG-Data') / date_str
            output_dir.mkdir(parents=True, exist_ok=True)

            for target in targets:
                key = make_item_key(phase, mode, date_str, target)

                if resume_state is not None:
                    resume_state["next_item"] = {"phase": phase, "mode": mode, "date": date_str, "target": target, "key": key}
                    save_resume_state(resume_state)

                if cancel_event is not None and cancel_event.is_set():
                    print("[STOP] Scrape stop requested. Stopping before next item.")
                    logger.warning("[STOP] Scrape stop requested. Stopping before next item.")
                    self.last_cancelled = True
                    if resume_state is not None:
                        resume_state["status"] = "stopped"
                        save_resume_state(resume_state)
                    return results

                if resume_mode and key in completed_keys:
                    completed_item = find_completed_item(key)
                    status = (completed_item or {}).get("status", "ok")
                    error = (completed_item or {}).get("error")
                    path = (completed_item or {}).get("path")

                    self.last_statuses[(target, date_obj)] = {"status": status, "error": error}

                    if path:
                        if target not in results:
                            results[target] = {}
                        results[target][date_obj] = path
                    else:
                        existing_path = get_screenshot_path(target, date_obj)
                        if existing_path and existing_path.exists() and existing_path.stat().st_size > 0:
                            if target not in results:
                                results[target] = {}
                            results[target][date_obj] = str(existing_path)

                    print(f"[SKIP] {mode} {current_index + 1}/{total_items} date={date_str} target={target} already completed")
                    current_index += 1
                    continue

                if resume_mode:
                    existing_path = get_screenshot_path(target, date_obj)
                    if existing_path and existing_path.exists() and existing_path.stat().st_size > 0:
                        self.last_statuses[(target, date_obj)] = {"status": "ok", "error": None}
                        print(f"[SKIP] {mode} {current_index + 1}/{total_items} date={date_str} target={target} existing screenshot")
                        if resume_state is not None:
                            item = {"phase": phase, "mode": mode, "date": date_str, "target": target, "status": "ok", "key": key, "path": str(existing_path)}
                            mark_item_completed(resume_state, item)
                            resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, phase)
                            save_resume_state(resume_state)
                            completed_keys.add(key)
                        if target not in results:
                            results[target] = {}
                        results[target][date_obj] = str(existing_path)
                        current_index += 1
                        continue

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
                        norm_status = "ok"
                        msg = f"[OK] {mode} {current_index}/{total_items} date={date_str} target={target} saved={filepath}"
                        print(msg)
                        logger.info(msg)
                        if target not in results:
                            results[target] = {}
                        results[target][date_obj] = str(filepath)
                    elif status_info.get("status") == "no_graph":
                        norm_status = "no_graph"
                        msg = f"[N/A] {mode} {current_index}/{total_items} date={date_str} target={target} no graph"
                        print(msg)
                        logger.info(msg)
                    else:
                        norm_status = "error"
                        err = status_info.get("error") or "unknown"
                        msg = f"[FAIL] {mode} {current_index}/{total_items} date={date_str} target={target} error={err}"
                        print(msg)
                        logger.error(msg)

                    if progress_callback:
                        progress_callback(target, date_obj, filepath is not None)

                    if resume_state is not None:
                        item = {
                            "phase": phase,
                            "mode": mode,
                            "date": date_str,
                            "target": target,
                            "status": norm_status,
                            "error": status_info.get("error"),
                            "path": str(filepath) if filepath else None,
                            "key": key
                        }
                        mark_item_completed(resume_state, item)
                        resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, phase)
                        save_resume_state(resume_state)
                        completed_keys.add(key)
                except Exception as e:
                    msg = f"[FAIL] {mode} {current_index}/{total_items} date={date_str} target={target} error={e}"
                    print(msg)
                    logger.error(msg)
                    results.setdefault(target, {})[date_obj] = None

                    if resume_state is not None:
                        item = {
                            "phase": phase,
                            "mode": mode,
                            "date": date_str,
                            "target": target,
                            "status": "error",
                            "error": str(e),
                            "path": None,
                            "key": key
                        }
                        mark_item_completed(resume_state, item)
                        resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, phase)
                        save_resume_state(resume_state)
                        completed_keys.add(key)

        if resume_state is not None:
            resume_state["current_phase"] = phase
            resume_state["next_item"] = None
            save_resume_state(resume_state)

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

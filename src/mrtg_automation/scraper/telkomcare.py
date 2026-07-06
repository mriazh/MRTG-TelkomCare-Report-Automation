"""
TelkomCare MRTG scraper.

Main entry point for M4 scraping pipeline.
Uses SessionManager for persistent Chrome profile and login handling.
"""
import logging
import time
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
                 base_url: str = 'http://telkomcare.telkom.co.id/mrtgnetcare2/graph/monitoring', manual_login_waiter=None, cancel_event=None):
        self.config = config
        self.base_url = base_url
        self.headless = headless
        self.cancel_event = cancel_event
        self.session = SessionManager(
            config=self.config,
            profile_dir=profile_dir,
            headless=headless,
            base_url=base_url,
            manual_login_waiter=manual_login_waiter,
            cancel_event=cancel_event
        )
        self.last_statuses = {}
        self._logged_in = False
        self.last_cancelled = False

    def _is_cancelled(self):
        return self.cancel_event is not None and self.cancel_event.is_set()

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
            self.last_cancelled = False
            if self._is_cancelled():
                self.last_cancelled = True
                logger.warning("[STOP] Login cancelled by user.")
                return False

            logger.info("Starting login flow...")
            self.session.start()
            if self._is_cancelled():
                self.last_cancelled = True
                logger.warning("[STOP] Login cancelled by user.")
                return False

            if not self.session.driver:
                return False

            if self._is_cancelled():
                self.last_cancelled = True
                logger.warning("[STOP] Login cancelled by user.")
                return False

            # Navigate to base URL - profile cookies from user-data-dir handle persistence
            self.session.driver.get(self.base_url)

            # Give page time to load
            import time
            for _ in range(10):
                if self._is_cancelled():
                    self.last_cancelled = True
                    logger.warning("[STOP] Login cancelled by user.")
                    return False
                time.sleep(0.2)

            if self.session.is_logged_in():
                logger.info("Session valid (cookies from Chrome profile)")
                self._logged_in = True
                return True

            if self._is_cancelled():
                self.last_cancelled = True
                logger.warning("[STOP] Login cancelled by user.")
                return False

            # Try auto-login first if configured
            if self.session.auto_login():
                self._logged_in = True
                return True

            logger.info("Session expired or first run - manual login required")
            if self.headless:
                print("[FAIL] Auto-login failed in headless mode. No manual fallback available.")
                logger.error("Auto-login failed in headless mode; manual login not possible.")
                return False

            if not self.session.wait_for_manual_login():
                if self._is_cancelled():
                    self.last_cancelled = True
                    logger.warning("[STOP] Login cancelled by user.")
                return False

            if self._is_cancelled():
                self.last_cancelled = True
                logger.warning("[STOP] Login cancelled by user.")
                return False

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

    def _recreate_extractor(self, mode: str):
        """Recreate GraphExtractor with current driver and navigate to graph page.

        After a re-login (manual or auto), the old extractor holds a stale driver
        reference. This method rebuilds it and navigates back to the graph page.
        """
        from .extractor import GraphExtractor
        extractor = GraphExtractor(self.session.driver, mode)
        if not extractor.navigate_to_graph_page():
            logger.error("Failed to navigate to graph page after re-login")
            return None
        logger.info("Recreated extractor with new driver after re-login")
        return extractor

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

        consecutive_failures = 0
        retry_queue = []  # Targets that failed transiently (DataTables alert) — retried after main loop

        for date_obj in dates:
            date_str = date_obj.strftime('%Y%m%d')

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
                relogin_attempts = 0
                while True:
                    try:
                        prog_msg = f"[PROGRESS] {mode} {current_index}/{total_items} date={date_str} target={target} starting"
                        print(prog_msg)
                        logger.info(prog_msg)

                        filepath = extractor.capture_graph(target, date_obj)

                        status_info = {
                            "status": getattr(extractor, 'last_status', None) or ("ok" if filepath else "error"),
                            "error": getattr(extractor, 'last_error', None),
                        }

                        if not filepath and status_info.get("status") != "no_graph":
                            # Check session on EVERY failure — not just after 3 strikes.
                            still_logged_in = self.session.is_logged_in()

                            if not still_logged_in:
                                # Session expired — immediate re-login, retry SAME item.
                                # Do NOT count toward transient consecutive_failures.
                                relogin_attempts += 1
                                if relogin_attempts > 3:
                                    logger.error(f"Re-login exhausted for {target} after 3 attempts.")
                                    msg = f"session_recovery_exhausted after {relogin_attempts - 1} login attempts"
                                    print(f"[FAIL] Re-login exhausted for target={target} after 3 attempts. Stopping.")
                                    if self.headless:
                                        print("[FAIL] Auto re-login failed in headless mode. No manual fallback available.")
                                    self.last_cancelled = True
                                    status_info["status"] = "error"
                                    status_info["error"] = msg
                                    break

                                logger.warning(f"Session expired for {target}. Attempting re-login ({relogin_attempts}/3)...")
                                print(f"\n[WARNING] TelkomCare session expired for {target}. Re-login attempt {relogin_attempts}/3...")

                                relogin_ok = self.session.auto_login()

                                if not relogin_ok and not self.headless:
                                    print("[INFO] Auto re-login not available or failed. Switching to manual login...")
                                    relogin_ok = self.session.wait_for_manual_login()

                                if relogin_ok:
                                    new_extractor = self._recreate_extractor(mode)
                                    if new_extractor is None:
                                        print("[FAIL] Could not navigate after re-login. Stopping scrape.")
                                        self.last_cancelled = True
                                        break
                                    extractor = new_extractor
                                    print(f"\n[INFO] Session restored. Retrying target {target} (attempt {relogin_attempts}/3)...")
                                    continue
                                else:
                                    if self.headless:
                                        print("[FAIL] Auto re-login failed in headless mode. No manual fallback available. Stopping scrape.")
                                    else:
                                        print("[FAIL] Re-login failed or cancelled. Stopping scrape.")
                                    self.last_cancelled = True
                                    break
                            else:
                                # Session still valid — check if this is a transient render/timeout failure.
                                # Transient failures: Graph did not render, timeout, stale element, DOM errors,
                                # blank/invalid captures. These follow the 3-strike inline retry path
                                # (same as StaleElementReference/DataTables alert), then queue if all 3 fail.
                                error_msg = status_info.get("error", "")
                                error_lower = error_msg.lower()
                                transient_patterns = (
                                    "graph did not render",
                                    "capture failed after 3 stale retries",
                                    "timeout",
                                    "staleelementreference",
                                    "no-graph placeholder",
                                    "no_graph placeholder",
                                    "blank",  # blank validation error = placeholder/no-render
                                    "invalid graph capture after 3 attempts",  # catch-all for validation failures after retries
                                )
                                is_transient = any(p in error_lower for p in transient_patterns)

                                if is_transient:
                                    # 3-strike inline retry path: increment counter, retry via while loop
                                    # (capture_graph already did its 3 internal retries; this is telkomcare-level retry)
                                    consecutive_failures += 1
                                    if consecutive_failures >= 3:
                                        logger.warning(f"3 consecutive transient failures for {target}: {error_msg} — queuing for retry pass.")
                                        print(f"\n[WARNING] 3 transient failures — queuing for retry pass: {target} ({error_msg})")
                                        retry_queue.append((target, date_obj, mode, phase, key))
                                        consecutive_failures = 0
                                        break
                                    else:
                                        # Inline retry: recover page and continue while loop to call capture_graph again
                                        logger.warning(f"Transient failure {consecutive_failures}/3 for {target}: {error_msg} — retrying inline.")
                                        print(f"\n[RETRY] Transient failure {consecutive_failures}/3 for {target} — recovering page and retrying inline.")
                                        extractor.recover_graph_page()
                                        time.sleep(2)
                                        continue
                                else:
                                    # Non-transient error (e.g., input_target failed, set_date_filter failed)
                                    # Fall back to old 3-strike logic for backward compatibility
                                    consecutive_failures += 1
                                    if consecutive_failures >= 3:
                                        logger.warning(f"3 consecutive transient failures (latest: {target}). Adding to retry queue.")
                                        print(f"\n[WARNING] 3 consecutive transient failures (target={target}). Queuing for retry pass...")
                                        retry_queue.append((target, date_obj, mode, phase, key))
                                        consecutive_failures = 0
                                        break
                        else:
                            consecutive_failures = 0
                            relogin_attempts = 0

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
                            if norm_status != "error":
                                mark_item_completed(resume_state, item)
                                completed_keys.add(key)
                            resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, phase)
                            save_resume_state(resume_state)

                        break  # Target completed (success or final failure without relogin)
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
                            resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, phase)
                            save_resume_state(resume_state)

                        break

                        break  # Exit while loop on unexpected exception

                if self.last_cancelled:
                    # Issue 4 — Mark remaining targets as failed when session recovery fails
                    # The loop is currently at date_obj/target. Remaining items can be estimated
                    # from total_items - current_index. Individual items are not explicitly listed,
                    # but resume state is saved so the user can resume from the failure point.
                    if resume_state is not None:
                        resume_state["status"] = "stopped"
                        save_resume_state(resume_state)

                    if self.headless:
                        # In headless mode, auto re-login failed and there is no manual fallback.
                        remaining = total_items - current_index
                        print(f"\n[FAIL] Auto re-login failed in headless mode. {remaining} target(s) not processed.")
                        print("[FAIL] No manual fallback available in headless mode.")
                        print("[INFO] To resume after fixing credentials/connectivity, run with --resume.")
                    return results

        # Retry pass for transient failures (Issue 2)
        if retry_queue:
            print(f"\n[RETRY] Starting retry pass for {len(retry_queue)} transient-failed targets...")
            for retry_target, retry_date, retry_mode, retry_phase, retry_key in retry_queue:
                retry_date_str = retry_date.strftime('%Y%m%d')
                for attempt in range(2):
                    if self.cancel_event is not None and self.cancel_event.is_set():
                        break
                    if attempt > 0:
                        time.sleep(30)  # Cooldown between attempts
                    print(f"[RETRY] {retry_mode} attempt {attempt+1}/2 date={retry_date_str} target={retry_target}")
                    try:
                        retry_filepath = extractor.capture_graph(retry_target, retry_date)
                        if retry_filepath:
                            if retry_target not in results:
                                results[retry_target] = {}
                            results[retry_target][retry_date] = str(retry_filepath)
                            if resume_state is not None:
                                item = {
                                    "phase": retry_phase, "mode": retry_mode,
                                    "date": retry_date_str, "target": retry_target,
                                    "status": "ok", "error": None, "path": str(retry_filepath),
                                    "key": retry_key
                                }
                                mark_item_completed(resume_state, item)
                                resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, retry_phase)
                                save_resume_state(resume_state)
                            print(f"[RETRY OK] {retry_mode} date={retry_date_str} target={retry_target}")
                            break
                        else:
                            logger.warning(f"[RETRY FAIL] {retry_mode} date={retry_date_str} target={retry_target} attempt {attempt+1}/2")
                    except Exception as e:
                        logger.error(f"[RETRY ERROR] {retry_mode} date={retry_date_str} target={retry_target} attempt {attempt+1}/2: {e}")

                    if attempt == 1:  # Final failure after 2 retry attempts
                        if resume_state is not None:
                            item = {
                                "phase": retry_phase, "mode": retry_mode,
                                "date": retry_date_str, "target": retry_target,
                                "status": "error", "error": "transient_failed_after_retry",
                                "path": None, "key": retry_key
                            }
                            mark_item_completed(resume_state, item)
                            resume_state["phase_completed_items_count"] = count_completed_items_for_phase(resume_state, retry_phase)
                            save_resume_state(resume_state)
                        print(f"[RETRY FAIL] {retry_mode} date={retry_date_str} target={retry_target} — final failure after retry pass")

            if resume_state is not None:
                save_resume_state(resume_state)

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

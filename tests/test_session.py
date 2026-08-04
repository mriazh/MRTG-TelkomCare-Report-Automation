import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from mrtg_automation.scraper.session import (
    SessionManager,
    _clear_stale_chrome_wdm_locks,
)


class TestStaleChromeWdmLockRecovery(unittest.TestCase):
    def test_clear_stale_chrome_wdm_locks_removes_only_stale_chrome_locks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            stale_chrome_lock = tmp_path / ".wdm-lock-chromedriver-win64"
            recent_chrome_lock = tmp_path / ".wdm-lock-chromedriver-x64"
            other_driver_lock = tmp_path / ".wdm-lock-geckodriver-win64"

            stale_chrome_lock.write_text("stale")
            recent_chrome_lock.write_text("recent")
            other_driver_lock.write_text("other")

            now = 1000.0
            os.utime(stale_chrome_lock, (now - 90, now - 90))
            os.utime(recent_chrome_lock, (now - 10, now - 10))
            os.utime(other_driver_lock, (now - 90, now - 90))

            removed = _clear_stale_chrome_wdm_locks(
                max_age_seconds=60.0,
                time_func=lambda: now,
                wdm_dir=tmp_path,
            )

            self.assertEqual(removed, 1)
            self.assertFalse(stale_chrome_lock.exists())
            self.assertTrue(recent_chrome_lock.exists())
            self.assertTrue(other_driver_lock.exists())

    def test_clear_stale_chrome_wdm_locks_wdm_local_boolean(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_wdm = Path(tmp_dir) / ".wdm"
            tmp_wdm.mkdir()
            stale_lock = tmp_wdm / ".wdm-lock-chromedriver-win64"
            stale_lock.write_text("stale")
            now = 1000.0
            os.utime(stale_lock, (now - 90, now - 90))

            with patch("pathlib.Path.cwd", return_value=Path(tmp_dir)), \
                 patch.dict(os.environ, {"WDM_LOCAL": "true"}):
                removed = _clear_stale_chrome_wdm_locks(
                    max_age_seconds=60.0,
                    time_func=lambda: now,
                )
                self.assertEqual(removed, 1)
                self.assertFalse(stale_lock.exists())

    def test_session_manager_start_clears_stale_locks_before_install(self):
        call_order = []

        def fake_cleanup(*args, **kwargs):
            call_order.append("cleanup")
            return 1

        def fake_install(*args, **kwargs):
            call_order.append("install")
            return "/fake/chromedriver"

        mock_config = MagicMock()
        mock_config.effective_browser_type = "chrome"
        mock_config.browser_type = "chrome"
        mock_config.browser_binary = None

        sm = SessionManager(config=mock_config)

        with patch("mrtg_automation.scraper.session._clear_stale_chrome_wdm_locks", side_effect=fake_cleanup) as mock_cleanup, \
             patch("mrtg_automation.scraper.session.ChromeDriverManager") as mock_cdm, \
             patch("selenium.webdriver.Chrome"):

            mock_cdm_instance = MagicMock()
            mock_cdm_instance.install.side_effect = fake_install
            mock_cdm.return_value = mock_cdm_instance

            res = sm.start()

            self.assertTrue(res)
            self.assertEqual(call_order, ["cleanup", "install"])
            mock_cleanup.assert_called_once()
            mock_cdm_instance.install.assert_called_once()


class TestSessionPersistenceVerification(unittest.TestCase):
    def test_restore_persisted_session_false_when_cookies_loaded_but_not_logged_in(self):
        mock_config = MagicMock()
        mock_config.WAIT_TIMEOUT = 5
        sm = SessionManager(config=mock_config)
        sm.driver = MagicMock()
        sm.driver.current_url = "https://telkomcare.telkom.co.id/public/login"

        with patch.object(sm, "load_cookies", return_value=True), \
             patch.object(sm, "is_logged_in", return_value=False):
            result = sm.restore_persisted_session()
            self.assertFalse(result)
            sm.driver.get.assert_called_with(sm.base_url)

    def test_restore_persisted_session_true_when_cookies_loaded_and_logged_in(self):
        mock_config = MagicMock()
        mock_config.WAIT_TIMEOUT = 5
        sm = SessionManager(config=mock_config)
        sm.driver = MagicMock()
        sm.driver.current_url = "https://telkomcare.telkom.co.id/mrtgnetcare2"

        with patch.object(sm, "load_cookies", return_value=True), \
             patch.object(sm, "is_logged_in", return_value=True):
            result = sm.restore_persisted_session()
            self.assertTrue(result)

    def test_restore_persisted_session_false_when_no_driver(self):
        mock_config = MagicMock()
        sm = SessionManager(config=mock_config)
        sm.driver = None
        self.assertFalse(sm.restore_persisted_session())

    def test_restore_persisted_session_false_when_load_cookies_fails(self):
        mock_config = MagicMock()
        sm = SessionManager(config=mock_config)
        sm.driver = MagicMock()
        with patch.object(sm, "load_cookies", return_value=False):
            self.assertFalse(sm.restore_persisted_session())


class TestCookiePersistenceHarden(unittest.TestCase):
    def test_save_cookies_creates_profile_dir_and_sets_permissions(self):
        mock_config = MagicMock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_dir = Path(tmp_dir) / "nested_profile"
            mock_config.PROFILE_DIR = profile_dir
            sm = SessionManager(config=mock_config)
            sm.profile_dir = profile_dir
            sm.driver = MagicMock()
            sm.driver.get_cookies.return_value = [{"name": "session", "value": "abc"}]

            res = sm.save_cookies()

            self.assertTrue(res)
            self.assertTrue(profile_dir.exists())
            cookie_path = profile_dir / "cookies.json"
            self.assertTrue(cookie_path.exists())
            if os.name != "nt":
                mode = os.stat(cookie_path).st_mode & 0o777
                self.assertEqual(mode, 0o600)

    def test_load_cookies_does_not_mutate_parsed_cookie_dict(self):
        mock_config = MagicMock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_dir = Path(tmp_dir)
            mock_config.PROFILE_DIR = profile_dir
            sm = SessionManager(config=mock_config)
            sm.profile_dir = profile_dir
            sm.driver = MagicMock()

            cookie_data = [
                {
                    "name": "token",
                    "value": "secret",
                    "sameSite": "Lax",
                    "storeId": "0",
                    "hostOnly": True,
                    "session": False,
                    "expiry": 12345.0,
                }
            ]

            with patch("json.load", return_value=cookie_data), \
                 patch("builtins.open", unittest.mock.mock_open(read_data="[]")), \
                 patch("pathlib.Path.exists", return_value=True):
                res = sm.load_cookies()

            self.assertTrue(res)
            self.assertEqual(cookie_data[0]["sameSite"], "Lax")
            self.assertEqual(cookie_data[0]["storeId"], "0")
            self.assertTrue(cookie_data[0]["hostOnly"])
            self.assertFalse(cookie_data[0]["session"])
            self.assertEqual(cookie_data[0]["expiry"], 12345.0)

    def test_load_cookies_malformed_json_fails_closed(self):
        mock_config = MagicMock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_dir = Path(tmp_dir)
            mock_config.PROFILE_DIR = profile_dir
            sm = SessionManager(config=mock_config)
            sm.profile_dir = profile_dir
            sm.driver = MagicMock()

            cookie_file = profile_dir / "cookies.json"
            cookie_file.write_text("{invalid json", encoding="utf-8")

            res = sm.load_cookies()

            self.assertFalse(res)
            sm.driver.add_cookie.assert_not_called()

    def test_load_cookies_non_list_json_fails_closed(self):
        mock_config = MagicMock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_dir = Path(tmp_dir)
            mock_config.PROFILE_DIR = profile_dir
            sm = SessionManager(config=mock_config)
            sm.profile_dir = profile_dir
            sm.driver = MagicMock()

            cookie_file = profile_dir / "cookies.json"
            cookie_file.write_text('{"name": "single_dict_not_list"}', encoding="utf-8")

            res = sm.load_cookies()

            self.assertFalse(res)
            sm.driver.add_cookie.assert_not_called()

    def test_load_cookies_no_driver_returns_false(self):
        mock_config = MagicMock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_dir = Path(tmp_dir)
            cookie_file = profile_dir / "cookies.json"
            cookie_file.write_text('[{"name": "a", "value": "b"}]', encoding="utf-8")

            sm = SessionManager(config=mock_config)
            sm.profile_dir = profile_dir
            sm.driver = None

            res = sm.load_cookies()

            self.assertFalse(res)


class TestSessionManagerCleanup(unittest.TestCase):
    @patch("mrtg_automation.scraper.session.ChromeDriverManager")
    def test_start_webdriver_exception(self, mock_wdm):
        from selenium.common.exceptions import WebDriverException

        mock_wdm.return_value.install.side_effect = WebDriverException("Driver failed to start")
        sm = SessionManager()
        result = sm.start()
        self.assertFalse(result)
        self.assertIsNone(sm.driver)

    def test_is_logged_in_routes_and_webdriver_exception(self):
        from selenium.common.exceptions import WebDriverException

        sm = SessionManager()
        mock_driver = MagicMock()
        sm.driver = mock_driver

        mock_driver.current_url = "https://example.com/public/login"
        self.assertFalse(sm.is_logged_in())

        mock_driver.current_url = "https://example.com/public/mfa"
        self.assertFalse(sm.is_logged_in())

        mock_driver.current_url = "https://example.com/mrtgnetcare2"
        self.assertTrue(sm.is_logged_in())

        mock_driver.current_url = "https://example.com/mrtgnetcare2/subpath"
        self.assertTrue(sm.is_logged_in())

        mock_driver.current_url = "https://example.com/other"
        type(mock_driver).page_source = PropertyMock(side_effect=WebDriverException("Page source error"))
        self.assertFalse(sm.is_logged_in())


if __name__ == "__main__":
    unittest.main()

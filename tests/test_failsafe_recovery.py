import unittest
from unittest.mock import MagicMock, patch

from mrtg_automation.scraper.session import SessionManager
from mrtg_automation.scraper.telkomcare import TelkomCareScraper


class TestFailsafeRecovery(unittest.TestCase):
    def test_session_sets_page_load_timeout(self):
        mock_config = MagicMock()
        mock_config.effective_browser_type = "chrome"
        mock_config.browser_type = "chrome"
        mock_config.browser_binary = None

        sm = SessionManager(config=mock_config)
        with (
            patch("mrtg_automation.scraper.session._clear_stale_chrome_wdm_locks"),
            patch("mrtg_automation.scraper.session.ChromeDriverManager"),
            patch("selenium.webdriver.Chrome") as mock_chrome_cls,
        ):
            mock_driver = MagicMock()
            mock_chrome_cls.return_value = mock_driver

            res = sm.start()
            self.assertTrue(res)
            mock_driver.set_page_load_timeout.assert_called_once_with(45)

    def test_telkomcare_login_retry_and_diagnostic_screenshot(self):
        mock_config = MagicMock()
        scraper = TelkomCareScraper(config=mock_config, headless=True)

        # Mock session to simulate failure on start/login across 3 attempts
        scraper.session = MagicMock()
        scraper.session.start.side_effect = Exception("Connection timeout")
        scraper.session.driver = MagicMock()

        with patch("time.sleep", return_value=None):
            success = scraper.login()

        self.assertFalse(success)
        self.assertEqual(scraper.session.start.call_count, 3)
        scraper.session.driver.save_screenshot.assert_called_once()
        saved_path = scraper.session.driver.save_screenshot.call_args[0][0]
        self.assertIn("login_failed_", saved_path)


if __name__ == "__main__":
    unittest.main()

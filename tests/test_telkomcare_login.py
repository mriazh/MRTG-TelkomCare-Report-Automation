import unittest
from unittest.mock import MagicMock

from mrtg_automation.scraper.telkomcare import TelkomCareScraper


class TestTelkomCareLogin(unittest.TestCase):
    def test_login_call_order_start_restore_auto_login(self):
        scraper = TelkomCareScraper()
        mock_session = MagicMock()
        mock_driver = MagicMock()
        mock_driver.current_url = scraper.base_url
        mock_session.driver = mock_driver
        mock_session.restore_persisted_session.return_value = False
        mock_session.is_logged_in.return_value = False
        mock_session.auto_login.return_value = True
        scraper.session = mock_session

        result = scraper.login()

        self.assertTrue(result)
        calls = [
            c[0]
            for c in mock_session.mock_calls
            if c[0] in ("start", "restore_persisted_session", "auto_login")
        ]
        self.assertEqual(calls, ["start", "restore_persisted_session", "auto_login"])

    def test_login_attempts_restore_persisted_session_before_auto_login(self):
        scraper = TelkomCareScraper()
        mock_session = MagicMock()
        mock_driver = MagicMock()
        mock_driver.current_url = scraper.base_url
        mock_session.driver = mock_driver
        mock_session.restore_persisted_session.return_value = True
        scraper.session = mock_session

        result = scraper.login()

        mock_session.start.assert_called_once()
        mock_session.restore_persisted_session.assert_called_once()
        mock_session.auto_login.assert_not_called()
        self.assertTrue(result)
        self.assertTrue(scraper._logged_in)

    def test_login_handles_no_driver_safely(self):
        scraper = TelkomCareScraper()
        mock_session = MagicMock()
        mock_session.driver = None
        scraper.session = mock_session

        result = scraper.login()

        mock_session.start.assert_called_once()
        mock_session.restore_persisted_session.assert_not_called()
        self.assertFalse(result)

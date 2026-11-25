import unittest
from unittest.mock import MagicMock, patch

from mrtg_automation.scraper.session import SessionManager


class TestSessionDriverFallback(unittest.TestCase):
    def _chrome_config(self):
        mock_config = MagicMock()
        mock_config.effective_browser_type = "chrome"
        mock_config.browser_type = "chrome"
        mock_config.browser_binary = None
        return mock_config

    def test_chrome_fallback_uses_system_chromedriver_path(self):
        mock_config = self._chrome_config()
        sm = SessionManager(config=mock_config)
        with (
            patch("mrtg_automation.scraper.session._clear_stale_chrome_wdm_locks"),
            patch("mrtg_automation.scraper.session.ChromeDriverManager") as mock_cdm,
            patch(
                "mrtg_automation.scraper.session.shutil.which", return_value="/usr/bin/chromedriver"
            ) as mock_which,
            patch("selenium.webdriver.Chrome") as mock_chrome,
            patch("mrtg_automation.scraper.session.logger") as mock_logger,
        ):
            mock_cdm_instance = MagicMock()
            mock_cdm_instance.install.side_effect = Exception("offline")
            mock_cdm.return_value = mock_cdm_instance

            result = sm.start()

            self.assertTrue(result)
            mock_which.assert_called_once_with("chromedriver")
            mock_logger.warning.assert_called()
            service = mock_chrome.call_args.kwargs["service"]
            self.assertEqual(service.path, "/usr/bin/chromedriver")

    def test_chrome_fallback_uses_default_service_when_no_system_driver(self):
        mock_config = self._chrome_config()
        sm = SessionManager(config=mock_config)
        with (
            patch("mrtg_automation.scraper.session._clear_stale_chrome_wdm_locks"),
            patch("mrtg_automation.scraper.session.ChromeDriverManager") as mock_cdm,
            patch("mrtg_automation.scraper.session.shutil.which", return_value=None) as mock_which,
            patch("selenium.webdriver.Chrome") as mock_chrome,
            patch("mrtg_automation.scraper.session.logger") as mock_logger,
        ):
            mock_cdm_instance = MagicMock()
            mock_cdm_instance.install.side_effect = Exception("dns failure")
            mock_cdm.return_value = mock_cdm_instance

            result = sm.start()

            self.assertTrue(result)
            mock_which.assert_called_once_with("chromedriver")
            mock_logger.warning.assert_called()
            service = mock_chrome.call_args.kwargs["service"]
            self.assertEqual(service.path, "")

    def test_firefox_fallback_uses_default_service(self):
        mock_config = MagicMock()
        mock_config.effective_browser_type = "firefox"
        mock_config.browser_type = "firefox"
        mock_config.browser_binary = None
        sm = SessionManager(config=mock_config)
        with (
            patch("mrtg_automation.scraper.session.GeckoDriverManager") as mock_gdm,
            patch("selenium.webdriver.Firefox") as mock_firefox,
            patch("mrtg_automation.scraper.session.logger") as mock_logger,
        ):
            mock_gdm_instance = MagicMock()
            mock_gdm_instance.install.side_effect = Exception("offline")
            mock_gdm.return_value = mock_gdm_instance

            result = sm.start()

            self.assertTrue(result)
            mock_logger.warning.assert_called()
            service = mock_firefox.call_args.kwargs["service"]
            self.assertEqual(service.path, "")

    def test_edge_fallback_uses_default_service(self):
        mock_config = MagicMock()
        mock_config.effective_browser_type = "edge"
        mock_config.browser_type = "edge"
        mock_config.browser_binary = None
        sm = SessionManager(config=mock_config)
        with (
            patch("mrtg_automation.scraper.session.EdgeChromiumDriverManager") as mock_edm,
            patch("selenium.webdriver.Edge") as mock_edge,
            patch("mrtg_automation.scraper.session.logger") as mock_logger,
        ):
            mock_edm_instance = MagicMock()
            mock_edm_instance.install.side_effect = Exception("offline")
            mock_edm.return_value = mock_edm_instance

            result = sm.start()

            self.assertTrue(result)
            mock_logger.warning.assert_called()
            service = mock_edge.call_args.kwargs["service"]
            self.assertEqual(service.path, "")

    def test_chrome_manager_success_still_uses_installed_path(self):
        mock_config = self._chrome_config()
        sm = SessionManager(config=mock_config)
        with (
            patch("mrtg_automation.scraper.session._clear_stale_chrome_wdm_locks"),
            patch("mrtg_automation.scraper.session.ChromeDriverManager") as mock_cdm,
            patch("mrtg_automation.scraper.session.shutil.which") as mock_which,
            patch("selenium.webdriver.Chrome") as mock_chrome,
        ):
            mock_cdm_instance = MagicMock()
            mock_cdm_instance.install.return_value = "/fake/chromedriver"
            mock_cdm.return_value = mock_cdm_instance

            result = sm.start()

            self.assertTrue(result)
            mock_which.assert_not_called()
            service = mock_chrome.call_args.kwargs["service"]
            self.assertEqual(service.path, "/fake/chromedriver")


if __name__ == "__main__":
    unittest.main()

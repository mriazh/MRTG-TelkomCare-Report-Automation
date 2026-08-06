"""
Unit tests for browser auto-detection and GUI browser configuration.
"""

import os
import unittest
from unittest.mock import patch

from mrtg_automation.config import Config
from mrtg_automation.shared.browser_detection import (
    SUPPORTED_BROWSERS,
    detect_default_browser,
    detect_installed_browsers,
    find_browser_binary,
    get_browser_display_name,
)


class TestBrowserDetection(unittest.TestCase):
    def test_find_browser_binary_invalid(self):
        self.assertIsNone(find_browser_binary("invalid_browser_name"))

    def test_find_browser_binary_supported(self):
        for b_type in SUPPORTED_BROWSERS:
            res = find_browser_binary(b_type)
            if res is not None:
                self.assertIsInstance(res, str)
                self.assertTrue(len(res) > 0)

    def test_detect_installed_browsers(self):
        installed = detect_installed_browsers()
        self.assertIsInstance(installed, dict)
        for key, val in installed.items():
            self.assertIn(key, SUPPORTED_BROWSERS)
            self.assertIsInstance(val, str)

    def test_detect_default_browser(self):
        b_type, binary = detect_default_browser()
        self.assertIn(b_type, SUPPORTED_BROWSERS)
        if binary is not None:
            self.assertIsInstance(binary, str)

    @patch.dict(os.environ, {"BROWSER_TYPE": "auto"})
    def test_config_auto_resolution(self):
        cfg = Config()
        self.assertEqual(cfg.browser_type, "auto")
        self.assertIn(cfg.effective_browser_type, SUPPORTED_BROWSERS)

    @patch.dict(os.environ, {"BROWSER_TYPE": "edge"})
    def test_config_explicit_resolution(self):
        cfg = Config()
        self.assertEqual(cfg.browser_type, "edge")
        self.assertEqual(cfg.effective_browser_type, "edge")

    @patch.dict(os.environ, {"BROWSER_TYPE": "invalid_value"})
    def test_config_invalid_fallback(self):
        cfg = Config()
        self.assertEqual(cfg.browser_type, "auto")
        self.assertIn(cfg.effective_browser_type, SUPPORTED_BROWSERS)

    def test_get_browser_display_name_unsupported(self):
        self.assertEqual(get_browser_display_name("opera"), "opera")
        self.assertEqual(get_browser_display_name(""), "")

    @patch("mrtg_automation.shared.browser_detection.find_browser_binary")
    def test_get_browser_display_name_not_installed(self, mock_find):
        mock_find.return_value = None
        for b_type in SUPPORTED_BROWSERS:
            expected = f"{b_type.capitalize()} (Not Installed)"
            self.assertEqual(get_browser_display_name(b_type), expected)

    @patch("mrtg_automation.shared.browser_detection.find_browser_binary")
    def test_get_browser_display_name_installed(self, mock_find):
        mock_find.return_value = "/usr/bin/chrome"
        for b_type in SUPPORTED_BROWSERS:
            expected = f"{b_type.capitalize()} (Installed)"
            self.assertEqual(get_browser_display_name(b_type), expected)

    def test_get_browser_display_name_case_insensitive(self):
        self.assertIn("Chrome", get_browser_display_name("CHROME"))
        self.assertIn("Edge", get_browser_display_name("EDGE"))


class TestGUIBrowserSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_gui_browser_combo(self):
        from mrtg_automation.gui.app import MainWindow

        window = MainWindow()

        # Verify dropdown lists installed status and disables uninstalled items
        for i in range(window.browser_cb.count()):
            text = window.browser_cb.itemText(i)
            item = window.browser_cb.model().item(i)
            self.assertTrue("(Installed)" in text or "(Not Installed)" in text)
            if "(Not Installed)" in text:
                self.assertFalse(item.isEnabled())
            elif "(Installed)" in text:
                self.assertTrue(item.isEnabled())

        # First installed browser should be selected by default
        first_installed_data = None
        for i in range(window.browser_cb.count()):
            if "(Installed)" in window.browser_cb.itemText(i):
                first_installed_data = window.browser_cb.itemData(i)
                break
        if first_installed_data:
            self.assertEqual(window.get_selected_browser_type(), first_installed_data)
        else:
            self.assertEqual(window.browser_cb.currentIndex(), 0)

        # Change to Edge
        for i in range(window.browser_cb.count()):
            if "Edge" in window.browser_cb.itemText(i):
                window.browser_cb.setCurrentIndex(i)
                self.assertEqual(window.get_selected_browser_type(), "edge")
                break

        # Change to Firefox
        for i in range(window.browser_cb.count()):
            if "Firefox" in window.browser_cb.itemText(i):
                window.browser_cb.setCurrentIndex(i)
                self.assertEqual(window.get_selected_browser_type(), "firefox")
                break

        # Change to Chrome
        for i in range(window.browser_cb.count()):
            if "Chrome" in window.browser_cb.itemText(i):
                window.browser_cb.setCurrentIndex(i)
                self.assertEqual(window.get_selected_browser_type(), "chrome")
                break


if __name__ == "__main__":
    unittest.main()

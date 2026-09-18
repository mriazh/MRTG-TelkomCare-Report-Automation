"""Regression tests for Task 23: Stage 3 Reliability & Concurrency Hardening."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from mrtg_automation.report.excel import ExcelReportGenerator
from mrtg_automation.scraper.session import _is_expected_host
from mrtg_automation.shared.resume_state import save_resume_state


class TestCollisionFreeTempFilenames(unittest.TestCase):
    def test_excel_atomic_save_uses_pid_token_suffix(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out = Path(tmp_dir) / "report.xlsx"
            mock_wb = MagicMock()

            with (
                patch("mrtg_automation.report.excel.os.replace"),
                patch("mrtg_automation.report.excel.os.getpid", return_value=12345),
                patch(
                    "mrtg_automation.report.excel.uuid.uuid4",
                    return_value=MagicMock(hex="abcdef123456"),
                ),
            ):
                ExcelReportGenerator._save_workbook_atomically(mock_wb, out)

            mock_wb.save.assert_called_once()
            saved_tmp = mock_wb.save.call_args[0][0]
            self.assertIn("12345", saved_tmp.name)
            self.assertIn("abcdef", saved_tmp.name)
            self.assertTrue(saved_tmp.name.endswith(".tmp"))
            self.assertTrue(saved_tmp.name.startswith(".report."))

    def test_resume_state_save_uses_pid_token_suffix(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state = {"status": "running"}
            with (
                patch("mrtg_automation.shared.resume_state.os.getpid", return_value=999),
                patch(
                    "mrtg_automation.shared.resume_state.uuid.uuid4",
                    return_value=MagicMock(hex="42abc0123456"),
                ),
            ):
                result = save_resume_state(state, state_dir=tmp_dir)
            self.assertTrue(result)
            target = Path(tmp_dir) / "resume_state.json"
            self.assertTrue(target.exists())
            loaded = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(loaded["status"], "running")


class TestSaveResumeStateBoolReturn(unittest.TestCase):
    def test_save_resume_state_returns_true_on_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = save_resume_state({"status": "running"}, state_dir=tmp_dir)
            self.assertTrue(result)

    def test_save_resume_state_returns_false_on_os_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch(
                "mrtg_automation.shared.resume_state.open",
                side_effect=OSError("disk full"),
            ):
                result = save_resume_state({"status": "running"}, state_dir=tmp_dir)
            self.assertFalse(result)


class TestGuiSummaryRegexAlignment(unittest.TestCase):
    def test_ocr_summary_line_triggers_incomplete(self):
        from mrtg_automation.gui.app import MainWindow

        window = MagicMock(spec=MainWindow)
        window.has_incomplete_data = False
        window._warned_incomplete_item = False
        window.log_text = MagicMock()

        msg = "  OCR Summary: OK=10 | Partial=2 | Fail=1"
        MainWindow._check_for_incompleteness(window, msg)
        self.assertTrue(window.has_incomplete_data)

    def test_image_missing_line_triggers_incomplete(self):
        from mrtg_automation.gui.app import MainWindow

        window = MagicMock(spec=MainWindow)
        window.has_incomplete_data = False
        window._warned_incomplete_item = False
        window.log_text = MagicMock()

        msg = "  Image inserted: 5 | Missing: 3"
        MainWindow._check_for_incompleteness(window, msg)
        self.assertTrue(window.has_incomplete_data)

    def test_clean_summary_does_not_trigger_incomplete(self):
        from mrtg_automation.gui.app import MainWindow

        window = MagicMock(spec=MainWindow)
        window.has_incomplete_data = False
        window._warned_incomplete_item = False
        window.log_text = MagicMock()

        msg = "  OCR Summary: OK=10 | Partial=0 | Fail=0"
        MainWindow._check_for_incompleteness(window, msg)
        self.assertFalse(window.has_incomplete_data)


class TestDeferredWindowClose(unittest.TestCase):
    def test_close_event_ignored_when_worker_still_running(self):
        from mrtg_automation.gui.app import MainWindow

        window = MagicMock(spec=MainWindow)
        window.worker = MagicMock()
        window.worker.request_stop.return_value = None
        thread = MagicMock()
        thread.isRunning.return_value = True
        thread.quit.return_value = None
        thread.wait.return_value = False
        thread.finished = MagicMock()
        window.worker_thread = thread
        window.log_text = MagicMock()

        event = MagicMock()
        MainWindow.closeEvent(window, event)

        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        thread.finished.connect.assert_called_once_with(window.close)

    def test_close_event_accepted_when_worker_stops_in_time(self):
        from mrtg_automation.gui.app import MainWindow

        window = MagicMock(spec=MainWindow)
        window.worker = MagicMock()
        window.worker.request_stop.return_value = None
        thread = MagicMock()
        thread.isRunning.return_value = True
        thread.quit.return_value = None
        thread.wait.return_value = True
        thread.finished = MagicMock()
        window.worker_thread = thread
        window.log_text = MagicMock()

        event = MagicMock()
        MainWindow.closeEvent(window, event)

        event.accept.assert_called_once()
        event.ignore.assert_not_called()


class TestStrictHttpsExactHostValidation(unittest.TestCase):
    def test_https_exact_host_accepted(self):
        self.assertTrue(
            _is_expected_host(
                "https://telkomcare.telkom.co.id/mrtgnetcare2", "https://telkomcare.telkom.co.id"
            )
        )

    def test_http_scheme_rejected(self):
        self.assertFalse(
            _is_expected_host(
                "http://telkomcare.telkom.co.id/mrtgnetcare2", "https://telkomcare.telkom.co.id"
            )
        )

    def test_lookalike_subdomain_rejected(self):
        self.assertFalse(
            _is_expected_host(
                "https://evil.telkomcare.telkom.co.id/mrtgnetcare2",
                "https://telkomcare.telkom.co.id",
            )
        )

    def test_foreign_host_rejected(self):
        self.assertFalse(
            _is_expected_host("https://example.com/mrtgnetcare2", "https://telkomcare.telkom.co.id")
        )

    def test_custom_base_url_host_accepted(self):
        base = "https://myinternal.example.com"
        self.assertTrue(_is_expected_host("https://myinternal.example.com/mrtgnetcare2", base))

    def test_custom_base_url_http_rejected(self):
        base = "https://myinternal.example.com"
        self.assertFalse(_is_expected_host("http://myinternal.example.com/mrtgnetcare2", base))


if __name__ == "__main__":
    unittest.main()

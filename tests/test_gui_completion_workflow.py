import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

from mrtg_automation.gui.app import MainWindow


class TestGuiCompletionWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def test_completion_dialog_success(self):
        self.window.has_incomplete_data = False
        dialog = self.window.create_completion_dialog(exit_code=0)

        self.assertEqual(dialog.windowTitle(), "Task Completed")
        self.assertIn("Task finished successfully", dialog.text())
        self.assertIn("Would you like to open the output folder?", dialog.text())
        self.assertEqual(dialog.icon(), QMessageBox.Icon.Information)

        button_texts = [btn.text() for btn in dialog.buttons()]
        self.assertIn("Open Output Folder", button_texts)
        self.assertIn("Close", button_texts)

    def test_completion_dialog_success_with_incomplete_data(self):
        self.window.has_incomplete_data = True
        dialog = self.window.create_completion_dialog(exit_code=0)

        self.assertEqual(dialog.windowTitle(), "Task Finished with Warnings")
        self.assertIn("Task finished with warnings", dialog.text())
        self.assertIn("Some items may be incomplete or failed", dialog.text())
        self.assertEqual(dialog.icon(), QMessageBox.Icon.Warning)

        button_texts = [btn.text() for btn in dialog.buttons()]
        self.assertIn("Open Output Folder", button_texts)
        self.assertIn("Close", button_texts)

    def test_completion_dialog_error_exit_code(self):
        dialog = self.window.create_completion_dialog(exit_code=1)

        self.assertEqual(dialog.windowTitle(), "Task Finished with Warnings / Errors")
        self.assertIn("Task finished with exit code 1", dialog.text())
        self.assertIn("Some items may be incomplete or failed", dialog.text())
        self.assertEqual(dialog.icon(), QMessageBox.Icon.Warning)

    def test_get_completion_target_folder_modes(self):
        # Report mode
        self.window.mode_cb.setCurrentText("Report")
        folder_report = self.window.get_completion_target_folder()
        expected_report = (
            self.window.paths.reports_dir
            if self.window.paths.reports_dir.exists()
            else self.window.output_root
        )
        self.assertEqual(folder_report, expected_report)

        # Full Pipeline mode
        self.window.mode_cb.setCurrentText("Full Pipeline")
        folder_full = self.window.get_completion_target_folder()
        self.assertEqual(folder_full, expected_report)

        # Scrape mode
        self.window.mode_cb.setCurrentText("Scrape")
        folder_scrape = self.window.get_completion_target_folder()
        expected_scrape = (
            self.window.paths.data_dir
            if self.window.paths.data_dir.exists()
            else self.window.output_root
        )
        self.assertEqual(folder_scrape, expected_scrape)

    def test_incompleteness_detection_scrape_summary_na(self):
        self.window.has_incomplete_data = False
        self.window.log_message("SUMMARY: 10 OK, 2 N/A, 0 FAIL, 12 total")

        self.assertTrue(self.window.has_incomplete_data)
        log_content = self.window.log_text.toPlainText()
        self.assertIn(
            "[WARNING] Some data or screenshots are missing or incomplete in scrape (N/A: 2, FAIL: 0).",
            log_content,
        )

    def test_incompleteness_detection_scrape_summary_fail(self):
        self.window.has_incomplete_data = False
        self.window.log_message("SUMMARY: 9 OK, 0 N/A, 1 FAIL, 10 total")

        self.assertTrue(self.window.has_incomplete_data)
        log_content = self.window.log_text.toPlainText()
        self.assertIn(
            "[WARNING] Some data or screenshots are missing or incomplete in scrape (N/A: 0, FAIL: 1).",
            log_content,
        )

    def test_incompleteness_detection_report_missing_screenshots(self):
        self.window.has_incomplete_data = False
        self.window.log_message("Missing screenshots: 3")

        self.assertTrue(self.window.has_incomplete_data)
        log_content = self.window.log_text.toPlainText()
        self.assertIn(
            "[WARNING] Some data or screenshots are missing in report (3 missing screenshot(s)).",
            log_content,
        )

    def test_incompleteness_detection_report_missing_mappings(self):
        self.window.has_incomplete_data = False
        self.window.log_message("Missing mappings   : 1")

        self.assertTrue(self.window.has_incomplete_data)
        log_content = self.window.log_text.toPlainText()
        self.assertIn(
            "[WARNING] Some data or screenshots are missing in report (1 missing mapping(s)).",
            log_content,
        )

    def test_incompleteness_detection_individual_error(self):
        self.window.has_incomplete_data = False
        self.window._warned_incomplete_item = False
        self.window.log_message(
            "[FAIL] report 1/10 mode=OCR_IMAGE date=20260901 target=123 error=missing_screenshot"
        )

        self.assertTrue(self.window.has_incomplete_data)
        log_content = self.window.log_text.toPlainText()
        self.assertIn("[WARNING] Some data or screenshots are missing or incomplete.", log_content)

    @patch("mrtg_automation.gui.app.QDesktopServices.openUrl")
    def test_on_worker_finished_opens_folder_when_clicked(self, mock_open_url):
        mock_dialog = MagicMock()
        mock_open_btn = MagicMock()
        mock_open_btn.text.return_value = "Open Output Folder"
        mock_dialog.clickedButton.return_value = mock_open_btn

        with patch.object(self.window, "create_completion_dialog", return_value=mock_dialog):
            self.window.on_worker_finished(0)

        mock_dialog.exec.assert_called_once()
        mock_open_url.assert_called_once()

    def test_validate_config_files_all_valid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "list_mrtg_targets.csv").write_text(
                "ID,Name\n1,Target1\n", encoding="utf-8"
            )
            (
                temp_path / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
            ).touch()
            (
                temp_path
                / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
            ).touch()
            (temp_path / "list_mrtg_data_position.txt").write_text("data", encoding="utf-8")
            (temp_path / "list_mrtg_data_position_img_only.txt").write_text(
                "data", encoding="utf-8"
            )
            (temp_path / ".env").write_text("AUTO_LOGIN_ENABLED=false\n", encoding="utf-8")

            self.window.config_dir = temp_path

            # Scrape
            self.window.mode_cb.setCurrentText("Scrape")
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

            # Report (ocr)
            self.window.mode_cb.setCurrentText("Report")
            self.window.report_mode_cb.setCurrentText("ocr")
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

            # Report (image)
            self.window.mode_cb.setCurrentText("Report")
            self.window.report_mode_cb.setCurrentText("image")
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

            # Full Pipeline (ocr)
            self.window.mode_cb.setCurrentText("Full Pipeline")
            self.window.report_mode_cb.setCurrentText("ocr")
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

            # Full Pipeline (image)
            self.window.mode_cb.setCurrentText("Full Pipeline")
            self.window.report_mode_cb.setCurrentText("image")
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

    def test_validate_config_files_missing_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self.window.config_dir = temp_path

            # Scrape mode
            self.window.mode_cb.setCurrentText("Scrape")
            valid, missing = self.window.validate_config_files()
            self.assertFalse(valid)
            self.assertIn("list_mrtg_targets.csv", missing)
            self.assertIn(".env", missing)

            # Report mode (ocr)
            self.window.mode_cb.setCurrentText("Report")
            self.window.report_mode_cb.setCurrentText("ocr")
            valid, missing = self.window.validate_config_files()
            self.assertFalse(valid)
            self.assertIn("list_mrtg_targets.csv", missing)
            self.assertIn(
                "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx", missing
            )
            self.assertIn("list_mrtg_data_position.txt", missing)
            self.assertNotIn(".env", missing)

            # Report mode (image)
            self.window.mode_cb.setCurrentText("Report")
            self.window.report_mode_cb.setCurrentText("image")
            valid, missing = self.window.validate_config_files()
            self.assertFalse(valid)
            self.assertIn("list_mrtg_targets.csv", missing)
            self.assertIn(
                "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
                missing,
            )
            self.assertIn("list_mrtg_data_position_img_only.txt", missing)
            self.assertNotIn(".env", missing)

            # Full Pipeline mode (image)
            self.window.mode_cb.setCurrentText("Full Pipeline")
            self.window.report_mode_cb.setCurrentText("image")
            valid, missing = self.window.validate_config_files()
            self.assertFalse(valid)
            self.assertIn("list_mrtg_targets.csv", missing)
            self.assertIn(
                "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
                missing,
            )
            self.assertIn("list_mrtg_data_position_img_only.txt", missing)
            self.assertIn(".env", missing)

    def test_validate_config_files_position_example_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "list_mrtg_targets.csv").touch()
            (
                temp_path / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
            ).touch()
            (
                temp_path
                / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
            ).touch()
            (temp_path / "list_mrtg_data_position.example.txt").touch()
            (temp_path / "list_mrtg_data_position_img_only.example.txt").touch()

            self.window.config_dir = temp_path

            # Report (ocr) - has example fallback
            self.window.mode_cb.setCurrentText("Report")
            self.window.report_mode_cb.setCurrentText("ocr")
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

            # Report (image) - has example fallback
            self.window.mode_cb.setCurrentText("Report")
            self.window.report_mode_cb.setCurrentText("image")
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

    def test_validate_config_files_auto_login_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "list_mrtg_targets.csv").touch()
            env_file = temp_path / ".env"
            env_file.write_text(
                "AUTO_LOGIN_ENABLED=true\nTELKOM_USER=\nTELKOM_PASSWORD=\n", encoding="utf-8"
            )

            self.window.config_dir = temp_path
            self.window.mode_cb.setCurrentText("Scrape")

            valid, missing = self.window.validate_config_files()
            self.assertFalse(valid)
            self.assertTrue(
                any("TELKOM_USER or TELKOM_PASSWORD missing" in item for item in missing)
            )

            # Auto-login enabled via .env but keys omitted entirely, environment clean
            env_file.write_text("AUTO_LOGIN_ENABLED=true\n", encoding="utf-8")
            with patch.dict("os.environ", {"TELKOM_USER": "", "TELKOM_PASSWORD": ""}):
                valid, missing = self.window.validate_config_files()
                self.assertFalse(valid)
                self.assertTrue(
                    any("TELKOM_USER or TELKOM_PASSWORD missing" in item for item in missing)
                )

            # Provide credentials via .env
            env_file.write_text(
                "AUTO_LOGIN_ENABLED=true\nTELKOM_USER=admin\nTELKOM_PASSWORD=secret\n",
                encoding="utf-8",
            )
            valid, missing = self.window.validate_config_files()
            self.assertTrue(valid)
            self.assertEqual(missing, [])

            # Credentials provided via environment when omitted in .env
            env_file.write_text("AUTO_LOGIN_ENABLED=true\n", encoding="utf-8")
            with patch.dict(
                "os.environ", {"TELKOM_USER": "env_user", "TELKOM_PASSWORD": "env_pwd"}
            ):
                valid, missing = self.window.validate_config_files()
                self.assertTrue(valid)
                self.assertEqual(missing, [])

            # Auto-login disabled in .env: valid even without credentials
            env_file.write_text("AUTO_LOGIN_ENABLED=false\n", encoding="utf-8")
            with patch.dict("os.environ", {"TELKOM_USER": "", "TELKOM_PASSWORD": ""}):
                valid, missing = self.window.validate_config_files()
                self.assertTrue(valid)
                self.assertEqual(missing, [])

    @patch("mrtg_automation.gui.app.QMessageBox.warning")
    def test_start_task_aborts_when_config_files_missing(self, mock_warning):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self.window.config_dir = temp_path
            self.window.worker = None

            self.window.start_task()

            mock_warning.assert_called_once()
            args, _ = mock_warning.call_args
            self.assertEqual(args[1], "Missing Configuration Files")
            self.assertIn("The following configuration files are missing", args[2])
            self.assertIn("list_mrtg_targets.csv", args[2])

            log_content = self.window.log_text.toPlainText()
            self.assertIn(
                "[WARNING] Config file missing or incomplete: list_mrtg_targets.csv", log_content
            )
            self.assertIsNone(self.window.worker)

    @patch("mrtg_automation.gui.app.QFileDialog.getExistingDirectory")
    def test_choose_config_dir_logs_warnings_when_missing(self, mock_dialog):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mock_dialog.return_value = str(temp_path)

            self.window.choose_config_dir()

            self.assertEqual(self.window.config_dir, temp_path.resolve())
            log_content = self.window.log_text.toPlainText()
            self.assertIn("[WARNING] Config file missing or incomplete:", log_content)


if __name__ == "__main__":
    unittest.main()

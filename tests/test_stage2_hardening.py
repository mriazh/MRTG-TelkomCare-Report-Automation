import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from openpyxl import Workbook

from mrtg_automation.config import Config
from mrtg_automation.report.excel import ExcelReportGenerator
from mrtg_automation.scraper.session import (
    SessionManager,
    _enforce_profile_dir_permissions,
    _is_expected_host,
    _should_use_no_sandbox,
)


class TestConditionalNoSandbox(unittest.TestCase):
    """REQ-25: --no-sandbox only applied in container/root or when CHROME_NO_SANDBOX=true."""

    def test_no_sandbox_true_when_env_set(self):
        with patch.dict("os.environ", {"CHROME_NO_SANDBOX": "true"}):
            self.assertTrue(_should_use_no_sandbox())

    def test_no_sandbox_false_when_env_unset_and_non_root(self):
        import os

        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("CHROME_NO_SANDBOX", None)
            with patch("os.geteuid", create=True, return_value=1000):
                self.assertFalse(_should_use_no_sandbox())

    def test_no_sandbox_true_when_root_posix(self):
        import os

        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("CHROME_NO_SANDBOX", None)
            with patch("os.geteuid", create=True, return_value=0):
                self.assertTrue(_should_use_no_sandbox())

    def test_build_options_omits_no_sandbox_for_regular_user(self):
        cfg = MagicMock()
        cfg.browser_type = "chrome"
        cfg.browser_binary = None
        with patch("os.geteuid", create=True, return_value=1000):
            with patch.dict("os.environ", {}, clear=False):
                import os

                os.environ.pop("CHROME_NO_SANDBOX", None)
                mgr = SessionManager(
                    profile_dir="/tmp/test-profile",
                    headless=False,
                    base_url="https://telkomcare.telkom.co.id",
                    config=cfg,
                )
                opts = mgr._build_options()
                args = opts.arguments if hasattr(opts, "arguments") else []
                self.assertNotIn("--no-sandbox", args)

    def test_build_options_includes_no_sandbox_when_env_set(self):
        cfg = MagicMock()
        cfg.browser_type = "chrome"
        cfg.browser_binary = None
        with patch.dict("os.environ", {"CHROME_NO_SANDBOX": "true"}):
            mgr = SessionManager(
                profile_dir="/tmp/test-profile",
                headless=False,
                base_url="https://telkomcare.telkom.co.id",
                config=cfg,
            )
            opts = mgr._build_options()
            args = opts.arguments if hasattr(opts, "arguments") else []
            self.assertIn("--no-sandbox", args)


class TestProfileDirPermissions(unittest.TestCase):
    """REQ-28: 0o700 permissions enforced on persistent browser profile directory."""

    @unittest.skipIf(__import__("os").name == "nt", "POSIX-only test")
    def test_enforce_profile_dir_permissions_sets_0o700(self):
        import os
        import stat

        with TemporaryDirectory() as tmp:
            d = Path(tmp) / "profile"
            d.mkdir()
            _enforce_profile_dir_permissions(d)
            mode = stat.S_IMODE(os.stat(d).st_mode)
            self.assertEqual(mode, 0o700)


class TestHostValidation(unittest.TestCase):
    """REQ-29: is_logged_in() rejects foreign origins that mimic dashboard subpaths."""

    def test_is_expected_host_accepts_telkomcare(self):
        self.assertTrue(
            _is_expected_host(
                "https://telkomcare.telkom.co.id/mrtgnetcare2", "https://telkomcare.telkom.co.id"
            )
        )

    def test_is_expected_host_accepts_subdomain(self):
        self.assertTrue(
            _is_expected_host(
                "https://sub.telkomcare.telkom.co.id/mrtgnetcare2",
                "https://telkomcare.telkom.co.id",
            )
        )

    def test_is_expected_host_rejects_fake_domain(self):
        self.assertFalse(
            _is_expected_host(
                "https://evil.example.com/mrtgnetcare2", "https://telkomcare.telkom.co.id"
            )
        )

    def test_is_expected_host_rejects_empty_hostname(self):
        self.assertFalse(_is_expected_host("about:blank", "https://telkomcare.telkom.co.id"))

    def test_is_logged_in_rejects_foreign_host(self):
        cfg = MagicMock()
        mgr = SessionManager(
            profile_dir="/tmp/test-profile", base_url="https://telkomcare.telkom.co.id", config=cfg
        )
        mock_driver = MagicMock()
        mock_driver.current_url = "https://evil.example.com/mrtgnetcare2"
        mgr.driver = mock_driver
        self.assertFalse(mgr.is_logged_in())

    def test_is_logged_in_accepts_expected_host(self):
        cfg = MagicMock()
        mgr = SessionManager(
            profile_dir="/tmp/test-profile", base_url="https://telkomcare.telkom.co.id", config=cfg
        )
        mock_driver = MagicMock()
        mock_driver.current_url = "https://telkomcare.telkom.co.id/mrtgnetcare2"
        mock_driver.page_source = ""
        mgr.driver = mock_driver
        self.assertTrue(mgr.is_logged_in())


class TestStrictConfigValidation(unittest.TestCase):
    """REQ-27: malformed config values raise RuntimeError instead of silent fallback."""

    def test_invalid_timeout_raises(self):
        with patch.dict("os.environ", {"WAIT_TIMEOUT": "abc"}):
            with self.assertRaises(RuntimeError):
                Config()

    def test_invalid_ocr_max_retries_raises(self):
        with patch.dict("os.environ", {"OCR_MAX_RETRIES": "0"}):
            # 0 is below the minimum of 1; should raise RuntimeError
            with self.assertRaises(RuntimeError):
                Config()

    def test_invalid_ocr_confidence_threshold_raises(self):
        with patch.dict("os.environ", {"OCR_CONFIDENCE_THRESHOLD": "2.5"}):
            # 2.5 exceeds the 1.0 upper bound; should raise RuntimeError
            with self.assertRaises(RuntimeError):
                Config()

    def test_valid_config_succeeds(self):
        cfg = Config()
        self.assertIsNotNone(cfg.settings)


class TestInsertImagesExplicit(unittest.TestCase):
    """REQ-30: insert_images passed explicitly, no os.environ mutation."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir()
        self.template_path = self.root / "template.xlsx"
        wb = Workbook()
        wb.active.title = "01"
        wb.save(self.template_path)
        self.output_path = self.root / "out.xlsx"
        self.mapping_path = self.root / "mapping.txt"
        self.mapping_path.write_text("SID : T-001\n-> B1-C1\n\n", encoding="utf-8")
        self.list_path = self.root / "targets.csv"
        self.list_path.write_text(
            "type,target,ocr_enabled,image_enabled\nSID,T-001,false,true\n", encoding="utf-8"
        )
        # Minimal image file
        date_folder = self.data_dir / "20260801"
        date_folder.mkdir()
        from mrtg_automation.shared.filenames import build_canonical_filename
        from datetime import datetime

        img_path = date_folder / build_canonical_filename("T-001", datetime(2026, 8, 1))
        img_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self.config = Config()
        self.generator = ExcelReportGenerator(self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_insert_images_true_inserts_image(self):
        with patch(
            "mrtg_automation.report.excel.insert_image_to_area", return_value=True
        ) as mock_insert:
            summary = self.generator.generate(
                report_mode="IMAGE_ONLY",
                data_dir=self.data_dir,
                template_path=self.template_path,
                output_path=self.output_path,
                mapping_file=self.mapping_path,
                list_file=self.list_path,
                date_filter="20260801",
                insert_images=True,
            )
        self.assertTrue(summary["report_created"])
        self.assertEqual(summary["image_inserted"], 1)
        mock_insert.assert_called_once()

    def test_insert_images_false_skips_image(self):
        with patch(
            "mrtg_automation.report.excel.insert_image_to_area", return_value=True
        ) as mock_insert:
            summary = self.generator.generate(
                report_mode="IMAGE_ONLY",
                data_dir=self.data_dir,
                template_path=self.template_path,
                output_path=self.output_path,
                mapping_file=self.mapping_path,
                list_file=self.list_path,
                date_filter="20260801",
                insert_images=False,
            )
        self.assertTrue(summary["report_created"])
        self.assertEqual(summary["image_inserted"], 0)
        mock_insert.assert_not_called()

    def test_no_os_environ_mutation_in_cli_source(self):
        """Verify cli.py source does not contain os.environ INSERT_IMAGES mutation."""
        cli_path = Path(__file__).parent.parent / "src" / "mrtg_automation" / "cli.py"
        content = cli_path.read_text(encoding="utf-8")
        self.assertNotIn('os.environ["INSERT_IMAGES"]', content)
        self.assertNotIn("os.environ['INSERT_IMAGES']", content)

    def test_no_os_environ_mutation_in_main_source(self):
        """Verify __main__.py source does not contain os.environ INSERT_IMAGES mutation."""
        main_path = Path(__file__).parent.parent / "src" / "mrtg_automation" / "__main__.py"
        content = main_path.read_text(encoding="utf-8")
        self.assertNotIn('os.environ["INSERT_IMAGES"]', content)
        self.assertNotIn("os.environ['INSERT_IMAGES']", content)


class TestGuiCloseEventNoTerminate(unittest.TestCase):
    """REQ-26: closeEvent does not call thread.terminate()."""

    def test_no_terminate_in_source(self):
        app_path = Path(__file__).parent.parent / "src" / "mrtg_automation" / "gui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        self.assertNotIn(".terminate()", content, "thread.terminate() should not be in gui/app.py")


if __name__ == "__main__":
    unittest.main()

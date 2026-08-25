import unittest
from pathlib import Path
import tempfile
import shutil

from PySide6.QtWidgets import QApplication
from mrtg_automation.shared.paths import get_output_paths, get_config_files, ensure_directories
from mrtg_automation.gui.app import MainWindow

app = QApplication.instance() or QApplication([])


class TestPathLayout(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_output_paths_derivation(self):
        output_root = self.temp_dir / "custom_output"
        paths = get_output_paths(output_root)

        self.assertEqual(paths["output_root"], output_root.resolve())
        self.assertEqual(paths["logs"], (output_root / "logs").resolve())
        self.assertEqual(paths["reports"], (output_root / "reports").resolve())
        self.assertEqual(paths["data"], (output_root / "data" / "MRTG-Data").resolve())
        self.assertEqual(paths["state"], (output_root / "state").resolve())
        self.assertEqual(paths["screenshots"], (output_root / "screenshots").resolve())

        # Test attribute access
        self.assertEqual(paths.output_root, output_root.resolve())
        self.assertEqual(paths.logs_dir, (output_root / "logs").resolve())
        self.assertEqual(paths.reports_dir, (output_root / "reports").resolve())
        self.assertEqual(paths.data_dir, (output_root / "data" / "MRTG-Data").resolve())
        self.assertEqual(paths.state_dir, (output_root / "state").resolve())

    def test_config_files_derivation(self):
        config_root = self.temp_dir / "custom_config"
        cfg = get_config_files(config_root)

        self.assertEqual(cfg["config_root"], config_root.resolve())
        self.assertEqual(cfg["env"], (config_root / ".env").resolve())
        self.assertEqual(
            cfg["position_ocr"], (config_root / "list_mrtg_data_position.txt").resolve()
        )
        self.assertEqual(
            cfg["position_img_only"],
            (config_root / "list_mrtg_data_position_img_only.txt").resolve(),
        )
        self.assertEqual(cfg["targets"], (config_root / "list_mrtg_targets.csv").resolve())
        self.assertEqual(
            cfg["template_ocr"],
            (
                config_root / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
            ).resolve(),
        )
        self.assertEqual(
            cfg["template_img_only"],
            (
                config_root
                / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
            ).resolve(),
        )

        # Test attribute access
        self.assertEqual(cfg.env, (config_root / ".env").resolve())
        self.assertEqual(cfg.targets, (config_root / "list_mrtg_targets.csv").resolve())
        self.assertEqual(cfg.position_ocr, (config_root / "list_mrtg_data_position.txt").resolve())
        self.assertEqual(
            cfg.position_img_only, (config_root / "list_mrtg_data_position_img_only.txt").resolve()
        )
        self.assertEqual(
            cfg.template_ocr,
            (
                config_root / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
            ).resolve(),
        )
        self.assertEqual(
            cfg.template_img_only,
            (
                config_root
                / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
            ).resolve(),
        )

    def test_ensure_directories_creates_all_subdirs(self):
        output_root = self.temp_dir / "out"
        config_root = self.temp_dir / "cfg"

        ensure_directories(output_root=output_root, config_dir=config_root)

        self.assertTrue(output_root.exists())
        self.assertTrue(config_root.exists())
        self.assertTrue((output_root / "logs").exists())
        self.assertTrue((output_root / "reports").exists())
        self.assertTrue((output_root / "data" / "MRTG-Data").exists())
        self.assertTrue((output_root / "state").exists())
        self.assertTrue((output_root / "screenshots").exists())

    def test_gui_streamlined_layout_and_mode_switching(self):
        window = MainWindow()

        # Check clean config and output folder inputs exist
        self.assertTrue(hasattr(window, "config_dir_input"))
        self.assertTrue(hasattr(window, "output_root_input"))

        # Verify all 8 redundant location controls and summary label are removed
        self.assertFalse(hasattr(window, "env_file_input"))
        self.assertFalse(hasattr(window, "targets_file_input"))
        self.assertFalse(hasattr(window, "pos_ocr_input"))
        self.assertFalse(hasattr(window, "pos_img_input"))
        self.assertFalse(hasattr(window, "tpl_ocr_input"))
        self.assertFalse(hasattr(window, "tpl_img_input"))
        self.assertFalse(hasattr(window, "out_data_input"))
        self.assertFalse(hasattr(window, "out_report_input"))
        self.assertFalse(hasattr(window, "path_summary_label"))

        # Test mode switching functions cleanly without dead references
        window.mode_cb.setCurrentText("Report")
        window.report_mode_cb.setCurrentText("ocr")
        window.on_mode_changed()
        self.assertFalse(window.targets_cb.isEnabled())
        self.assertTrue(window.report_mode_cb.isEnabled())

        window.mode_cb.setCurrentText("Scrape")
        window.on_mode_changed()
        self.assertTrue(window.targets_cb.isEnabled())
        self.assertFalse(window.report_mode_cb.isEnabled())


if __name__ == "__main__":
    unittest.main()

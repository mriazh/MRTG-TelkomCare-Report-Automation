import json
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from openpyxl import Workbook

from mrtg_automation.config import Config
from mrtg_automation.report.excel import ExcelReportGenerator
from mrtg_automation.report.gemini_ocr import GeminiLegendExtractor
from mrtg_automation.scraper.telkomcare import TelkomCareScraper
from mrtg_automation.shared.filenames import build_canonical_filename
from mrtg_automation.shared.resume_state import load_resume_state, make_item_key, save_resume_state


class TestStage1Hardening(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = Config()
        self.config.gemini_api_key = "test_gemini_key"
        self.config.gemini_models = ["gemini-1.5-flash"]
        self.generator = ExcelReportGenerator(self.config)

        self.template_path = self.root / "template.xlsx"
        self.output_path = self.root / "output.xlsx"
        self.mapping_path = self.root / "mapping.txt"
        self.target_list_path = self.root / "targets.csv"
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        wb.active.title = "01"
        wb.save(self.template_path)

        self.target_id = "TARGET-001"
        self.mapping_path.write_text(
            f"SID : {self.target_id}\n-> B1-C1\n\n",
            encoding="utf-8",
        )
        self.target_list_path.write_text(
            f"type,target,ocr_enabled,image_enabled\nSID,{self.target_id},false,true\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_report_completion_semantics_success(self):
        # Create valid image matching canonical filename
        date_folder = self.data_dir / "20260801"
        date_folder.mkdir(parents=True, exist_ok=True)
        img_name = build_canonical_filename(self.target_id, datetime(2026, 8, 1))
        img_path = date_folder / img_name
        # 1x1 png bytes
        img_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        with patch("mrtg_automation.report.excel.insert_image_to_area"):
            summary = self.generator.generate(
                report_mode="IMAGE_ONLY",
                data_dir=self.data_dir,
                template_path=self.template_path,
                output_path=self.output_path,
                mapping_file=self.mapping_path,
                list_file=self.target_list_path,
                date_filter="20260801",
            )

        self.assertTrue(summary["report_created"])
        self.assertTrue(summary["complete"])
        self.assertTrue(summary["success"])
        self.assertEqual(summary["missing_screenshots"], 0)
        self.assertEqual(summary["missing_mappings"], 0)
        self.assertEqual(summary["failed_inserts"], 0)

    def test_report_completion_semantics_missing_data(self):
        # Date folder without image
        date_folder = self.data_dir / "20260801"
        date_folder.mkdir(parents=True, exist_ok=True)

        summary = self.generator.generate(
            report_mode="IMAGE_ONLY",
            data_dir=self.data_dir,
            template_path=self.template_path,
            output_path=self.output_path,
            mapping_file=self.mapping_path,
            list_file=self.target_list_path,
            date_filter="20260801",
        )

        self.assertTrue(summary["report_created"])
        self.assertFalse(summary["complete"])
        self.assertFalse(summary["success"])
        self.assertEqual(summary["missing_screenshots"], 1)

    def test_canonical_resume_screenshot_check(self):
        date_folder = self.data_dir / "20260801"
        date_folder.mkdir(parents=True, exist_ok=True)

        canonical_name = build_canonical_filename(self.target_id, datetime(2026, 8, 1))
        canonical_path = date_folder / canonical_name
        valid_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            + b"\x00" * 2000
        )
        canonical_path.write_bytes(valid_png)

        # Legacy non-canonical name should NOT be checked
        legacy_path = date_folder / f"{self.target_id}.png"
        if legacy_path.exists():
            legacy_path.unlink()

        item_key = make_item_key("report_image", "IMAGE_ONLY", "20260801", self.target_id)
        resume_state = {
            "current_phase": "report_image",
            "completed_items": [
                {
                    "phase": "report_image",
                    "mode": "IMAGE_ONLY",
                    "date": "20260801",
                    "target": self.target_id,
                    "status": "ok",
                    "key": item_key,
                }
            ],
        }

        with patch("mrtg_automation.report.excel.insert_image_to_area") as mock_insert:
            summary = self.generator.generate(
                report_mode="IMAGE_ONLY",
                data_dir=self.data_dir,
                template_path=self.template_path,
                output_path=self.output_path,
                mapping_file=self.mapping_path,
                list_file=self.target_list_path,
                date_filter="20260801",
                resume_state=resume_state,
                resume_mode=True,
                phase="report_image",
            )
            # Item was already completed and canonical file exists -> skipped
            mock_insert.assert_not_called()
            self.assertTrue(summary["report_created"])

    def test_cpu_safe_pause_yielding(self):
        date_folder = self.data_dir / "20260801"
        date_folder.mkdir(parents=True, exist_ok=True)
        pause_event = threading.Event()
        cancel_event = threading.Event()
        pause_event.set()

        # In a separate thread, cancel after 0.05s
        def delayed_cancel():
            time.sleep(0.05)
            cancel_event.set()

        t = threading.Thread(target=delayed_cancel)
        t.start()

        start_time = time.monotonic()
        summary = self.generator.generate(
            report_mode="IMAGE_ONLY",
            data_dir=self.data_dir,
            template_path=self.template_path,
            output_path=self.output_path,
            mapping_file=self.mapping_path,
            list_file=self.target_list_path,
            date_filter="20260801",
            pause_event=pause_event,
            cancel_event=cancel_event,
        )
        t.join()
        elapsed = time.monotonic() - start_time

        self.assertTrue(summary.get("cancelled"))
        self.assertGreaterEqual(elapsed, 0.04)

    def test_scraper_cpu_safe_pause_yielding(self):
        pause_event = threading.Event()
        cancel_event = threading.Event()
        pause_event.set()

        scraper = TelkomCareScraper(self.config)
        scraper._logged_in = True

        def delayed_cancel():
            time.sleep(0.05)
            cancel_event.set()

        t = threading.Thread(target=delayed_cancel)
        t.start()

        targets = [("SID", self.target_id)]
        start_time = time.monotonic()
        with patch("mrtg_automation.scraper.extractor.GraphExtractor") as mock_ext_cls:
            mock_ext = mock_ext_cls.return_value
            mock_ext.navigate_to_graph_page.return_value = True

            res = scraper.scrape(
                targets=targets,
                dates=[datetime(2026, 8, 1)],
                pause_event=pause_event,
                cancel_event=cancel_event,
            )
        t.join()
        elapsed = time.monotonic() - start_time

        self.assertTrue(scraper.last_cancelled)
        self.assertGreaterEqual(elapsed, 0.04)
        self.assertEqual(res, {})

    def test_atomic_save_workbook(self):
        wb = Workbook()
        out = self.root / "test_atomic.xlsx"
        ExcelReportGenerator._save_workbook_atomically(wb, out)
        self.assertTrue(out.exists())
        tmp = out.with_name(f".{out.name}.tmp")
        self.assertFalse(tmp.exists())

    def test_atomic_save_workbook_failure_cleanup(self):
        wb = MagicMock()
        wb.save.side_effect = RuntimeError("Disk full simulation")
        out = self.root / "test_atomic_fail.xlsx"
        with self.assertRaises(RuntimeError):
            ExcelReportGenerator._save_workbook_atomically(wb, out)
        self.assertFalse(out.exists())
        tmp = out.with_name(f".{out.name}.tmp")
        self.assertFalse(tmp.exists())

    def test_atomic_save_resume_state(self):
        state_dir = self.root / "state"
        state = {"status": "running", "current_phase": "scrape"}
        save_resume_state(state, state_dir=state_dir)

        loaded = load_resume_state(state_dir=state_dir)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["status"], "running")

        state_path = state_dir / "resume_state.json"
        tmp_path = state_path.with_name(f".{state_path.name}.tmp")
        self.assertFalse(tmp_path.exists())

    def test_gemini_ocr_header_authentication(self):
        extractor = GeminiLegendExtractor(self.config)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": "Inbound_Current: 10\nInbound_Average: 20\nInbound_Maximum: 30\nOutbound_Current: 40\nOutbound_Average: 50\nOutbound_Maximum: 60"
                                    }
                                ]
                            }
                        }
                    ]
                }
            ).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            dummy_img = self.root / "dummy.png"
            dummy_img.write_bytes(b"dummy_bytes")
            res = extractor.extract_legend(dummy_img)

            self.assertTrue(res["complete"])
            sent_req = mock_urlopen.call_args[0][0]
            self.assertNotIn("?key=", sent_req.full_url)
            self.assertEqual(sent_req.get_header("X-goog-api-key"), "test_gemini_key")


if __name__ == "__main__":
    unittest.main()

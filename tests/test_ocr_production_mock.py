import json
import os
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from mrtg_automation.cli import (
    _discover_data_dates,
    _group_dates_by_month,
    _monthly_output_path,
    run_report_command,
)
from mrtg_automation.config import Config
from mrtg_automation.report.excel import (
    _classify_ocr_values,
    _prepare_audit_path,
    _record_ocr_metadata,
)
from mrtg_automation.report.ocr import OCRExtractor

EXPECTED_PADDLE_VALUES = {
    "Inbound_Current": "6.65 k",
    "Inbound_Average": "99.52 k",
    "Inbound_Maximum": "671.70 k",
    "Outbound_Current": "3.32 k",
    "Outbound_Average": "153.29 k",
    "Outbound_Maximum": "1.82 M",
}

GEMINI_VALUES = {
    "Inbound_Current": "1 k",
    "Inbound_Average": "2 k",
    "Inbound_Maximum": "3 k",
    "Outbound_Current": "4 k",
    "Outbound_Average": "5 k",
    "Outbound_Maximum": "6 k",
}


class LegacyEngine:
    """Legacy PaddleOCR engine that only has .ocr() method (no .predict())."""
    def __init__(self, result):
        self.result = result

    def ocr(self, _path):
        return self.result


class TestOCRProduction(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.image_path = Path("unused-test-image.png")

    @staticmethod
    def _texts():
        return [
            "Inbound",
            "Current",
            "6.65",
            "k",
            "Average",
            "99.52",
            "k",
            "Maximum",
            "671.70",
            "k",
            "Outbound",
            "Current",
            "3.32",
            "k",
            "Average",
            "153.29",
            "k",
            "Maximum",
            "1.82",
            "M",
        ]

    @classmethod
    def _v3_engine(cls, confidence):
        texts = cls._texts()
        engine = MagicMock()
        engine.predict.return_value = [
            {"res": {"rec_texts": texts, "rec_scores": [confidence] * len(texts)}}
        ]
        # Ensure no ocr method to force predict path
        delattr(engine, "ocr")
        return engine

    @staticmethod
    def _gemini_result(values=None, complete=True, model="gemini-test"):
        return {
            "values": values if values is not None else GEMINI_VALUES,
            "model": model,
            "complete": complete,
            "error_reason": None if complete else "ALL_MODELS_FAILED",
        }

    @patch("mrtg_automation.report.ocr.GeminiLegendExtractor")
    @patch("mrtg_automation.report.ocr.OCRExtractor._get_engine")
    def test_confident_complete_paddle_skips_gemini(self, mock_get_engine, mock_gemini):
        mock_get_engine.return_value = self._v3_engine(0.99)

        result = OCRExtractor.extract_mrtg_values_with_metadata(
            self.image_path, self.config
        )

        self.assertEqual(EXPECTED_PADDLE_VALUES, result["values"])
        self.assertEqual("Paddle", result["engine_used"])
        self.assertEqual("paddle_confident", result["decision_reason"])
        self.assertFalse(result["gemini_called"])
        mock_gemini.assert_not_called()

    @patch("mrtg_automation.report.ocr.GeminiLegendExtractor")
    @patch("mrtg_automation.report.ocr.OCRExtractor._get_engine")
    def test_incomplete_paddle_calls_gemini(self, mock_get_engine, mock_gemini):
        engine = MagicMock()
        engine.predict.return_value = [
            {"res": {"rec_texts": ["Inbound", "Current"], "rec_scores": [0.99, 0.99]}}
        ]
        delattr(engine, "ocr")
        mock_get_engine.return_value = engine
        mock_gemini.return_value.extract_legend.return_value = self._gemini_result()

        result = OCRExtractor.extract_mrtg_values_with_metadata(
            self.image_path, self.config
        )

        self.assertEqual(GEMINI_VALUES, result["values"])
        self.assertEqual("Gemini", result["engine_used"])
        self.assertEqual("paddle_incomplete", result["decision_reason"])
        self.assertTrue(result["gemini_called"])
        mock_gemini.assert_called_once_with(self.config)
        mock_gemini.return_value.extract_legend.assert_called_once_with(self.image_path)

    @patch("mrtg_automation.report.ocr.GeminiLegendExtractor")
    @patch("mrtg_automation.report.ocr.OCRExtractor._get_engine")
    def test_low_confidence_complete_paddle_calls_gemini(self, mock_get_engine, mock_gemini):
        mock_get_engine.return_value = self._v3_engine(0.5)
        mock_gemini.return_value.extract_legend.return_value = self._gemini_result()

        result = OCRExtractor.extract_mrtg_values_with_metadata(
            self.image_path, self.config
        )

        self.assertEqual(GEMINI_VALUES, result["values"])
        self.assertEqual("Gemini", result["engine_used"])
        self.assertEqual("low_confidence", result["decision_reason"])
        self.assertTrue(result["gemini_called"])
        mock_gemini.assert_called_once_with(self.config)

    @patch("mrtg_automation.report.ocr.GeminiLegendExtractor")
    @patch("mrtg_automation.report.ocr.OCRExtractor._get_engine")
    def test_gemini_unavailable_preserves_complete_paddle(self, mock_get_engine, mock_gemini):
        mock_get_engine.return_value = self._v3_engine(0.5)
        mock_gemini.return_value.extract_legend.return_value = {
            "values": {},
            "complete": False,
            "error_reason": "ALL_MODELS_FAILED",
        }

        result = OCRExtractor.extract_mrtg_values_with_metadata(
            self.image_path, self.config
        )

        self.assertEqual(EXPECTED_PADDLE_VALUES, result["values"])
        self.assertEqual("Paddle", result["engine_used"])
        self.assertEqual("gemini_unavailable", result["decision_reason"])
        self.assertEqual("", result["gemini_model"])
        self.assertTrue(result["gemini_called"])

    @patch("mrtg_automation.report.ocr.GeminiLegendExtractor")
    @patch("mrtg_automation.report.ocr.OCRExtractor._get_engine")
    def test_legacy_list_support(self, mock_get_engine, mock_gemini):
        box = [[0, 0], [1, 0], [1, 1], [0, 1]]
        lines = [[box, (text, 0.99)] for text in self._texts()]
        legacy_result = [lines]
        mock_get_engine.return_value = LegacyEngine(legacy_result)

        result = OCRExtractor.extract_mrtg_values_with_metadata(
            self.image_path, self.config
        )

        self.assertEqual(EXPECTED_PADDLE_VALUES, result["values"])
        self.assertEqual("Paddle", result["engine_used"])
        self.assertEqual("paddle_confident", result["decision_reason"])
        mock_gemini.assert_not_called()

    def test_threshold_validation_config(self):
        expected = {
            "abc": 0.85,
            "-0.1": 0.85,
            "1.1": 0.85,
            "0.90": 0.90,
        }
        for raw_value, expected_value in expected.items():
            with self.subTest(raw_value=raw_value):
                with patch.dict(
                    os.environ,
                    {"OCR_CONFIDENCE_THRESHOLD": raw_value},
                    clear=False,
                ):
                    config = Config()
                    self.assertEqual(expected_value, config.ocr_confidence_threshold)

    def test_gemini_observe_flag_config(self):
        # Default false
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            self.assertFalse(config.ocr_gemini_observe)

        # True values
        for val in ("true", "1", "yes", "TRUE"):
            with self.subTest(val=val):
                with patch.dict(os.environ, {"OCR_GEMINI_OBSERVE": val}, clear=False):
                    config = Config()
                    self.assertTrue(config.ocr_gemini_observe)

        # False values
        for val in ("false", "0", "no", "FALSE"):
            with self.subTest(val=val):
                with patch.dict(os.environ, {"OCR_GEMINI_OBSERVE": val}, clear=False):
                    config = Config()
                    self.assertFalse(config.ocr_gemini_observe)


class TestOCRReportHelpers(unittest.TestCase):
    @staticmethod
    def _summary():
        return {
            "ocr_paddle_final": 0,
            "ocr_gemini_final": 0,
            "ocr_paddle_confident": 0,
            "ocr_paddle_error": 0,
            "ocr_paddle_incomplete": 0,
            "ocr_low_confidence": 0,
            "ocr_gemini_unavailable": 0,
            "ocr_both_unknown": 0,
            "ocr_mismatch": 0,
        }

    def test_classifies_complete_values(self):
        self.assertEqual(("ok", 6, 0), _classify_ocr_values(EXPECTED_PADDLE_VALUES))

    def test_classifies_partial_values(self):
        values = {
            **EXPECTED_PADDLE_VALUES,
            "Inbound_Average": "N/A",
            "Outbound_Maximum": " ",
            "Outbound_Current": None,
        }
        self.assertEqual(("partial", 3, 3), _classify_ocr_values(values))

    def test_classifies_empty_values(self):
        self.assertEqual(("fail", 0, 6), _classify_ocr_values({}))
        self.assertEqual(("fail", 0, 6), _classify_ocr_values(None))

    def test_records_metadata_once_paddle(self):
        paddle_summary = self._summary()
        _record_ocr_metadata(
            paddle_summary,
            {"engine_used": "Paddle", "decision_reason": "paddle_confident"},
        )
        self.assertEqual(1, paddle_summary["ocr_paddle_final"])
        self.assertEqual(1, paddle_summary["ocr_paddle_confident"])
        self.assertEqual(2, sum(paddle_summary.values()))

    def test_records_metadata_once_gemini(self):
        gemini_summary = self._summary()
        _record_ocr_metadata(
            gemini_summary,
            {"engine_used": "Gemini", "decision_reason": "low_confidence"},
        )
        self.assertEqual(1, gemini_summary["ocr_gemini_final"])
        self.assertEqual(1, gemini_summary["ocr_low_confidence"])
        self.assertEqual(2, sum(gemini_summary.values()))

    def test_audit_path_lifecycle(self):
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.xlsx"
            audit_path = output_path.with_suffix(".ocr-audit.jsonl")
            audit_path.write_text("old\n", encoding="utf-8")

            # Fresh run (resume_mode=False) should truncate
            fresh_audit = _prepare_audit_path(output_path, "OCR_IMAGE", resume_mode=False)
            self.assertEqual(fresh_audit, audit_path)
            self.assertEqual("", audit_path.read_text(encoding="utf-8"))

            # Write an entry
            with open(audit_path, "a", encoding="utf-8") as f:
                f.write('{"test": 1}\n')

            # Resume run (resume_mode=True) should preserve
            resume_audit = _prepare_audit_path(output_path, "OCR_IMAGE", resume_mode=True)
            self.assertEqual(resume_audit, audit_path)
            self.assertEqual('{"test": 1}\n', audit_path.read_text(encoding="utf-8"))

            # Image only mode should return None
            none_audit = _prepare_audit_path(output_path, "IMAGE_ONLY", resume_mode=False)
            self.assertIsNone(none_audit)

    def test_audit_append_utf8(self):
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.xlsx"
            audit_path = _prepare_audit_path(output_path, "OCR_IMAGE", resume_mode=False)

            entry = {
                "date": "20260713",
                "target_id": "TEST",
                "engine_used": "Paddle",
                "paddle_confidence": 0.99,
                "final_values": {"Inbound_Current": "6.65 k"},
            }
            with open(audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            content = audit_path.read_text(encoding="utf-8")
            self.assertIn("6.65 k", content)


class TestMonthlyGrouping(unittest.TestCase):
    def test_discovers_and_groups_valid_date_folders(self):
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            for folder_name in (
                "20260713",
                "20260714",
                "20260801",
                "20270102",
                "20261301",
                "not-a-date",
            ):
                (data_dir / folder_name).mkdir()

            dates = _discover_data_dates(data_dir)
            groups = _group_dates_by_month(dates)

            self.assertEqual(
                [date(2026, 7, 13), date(2026, 7, 14), date(2026, 8, 1), date(2027, 1, 2)],
                dates,
            )
            self.assertEqual(["2026-07", "2026-08", "2027-01"], list(groups))
            self.assertEqual(2, len(groups["2026-07"]))

    def test_monthly_output_paths(self):
        output_path = Path("output/reports/MRTG-Monthly-Report-ocr.xlsx")
        self.assertEqual(
            Path("output/reports/MRTG-Monthly-Report-ocr-2026-07.xlsx"),
            _monthly_output_path(output_path, "2026-07"),
        )
        self.assertEqual(
            Path("output/reports/MRTG-Monthly-Report-ocr-2026-08.xlsx"),
            _monthly_output_path(output_path, "2026-08"),
        )
        self.assertEqual(
            Path("output/reports/MRTG-Monthly-Report-ocr-2027-01.xlsx"),
            _monthly_output_path(output_path, "2027-01"),
        )


if __name__ == "__main__":
    unittest.main()
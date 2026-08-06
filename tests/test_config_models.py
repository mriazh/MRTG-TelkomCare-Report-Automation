import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import SecretStr, ValidationError

from mrtg_automation.config import Config, GEMINI_MODELS_DEFAULT
from mrtg_automation.report.mapping import parse_target_list
from mrtg_automation.shared.config_models import (
    ApplicationSettings,
    BrowserType,
    TargetRow,
)


class TestConfigModels(unittest.TestCase):
    def test_settings_validate_bounds_and_keep_secrets_non_printing(self):
        settings = ApplicationSettings(
            browser_type=BrowserType.CHROME,
            wait_timeout=10,
            gemini_models=[" model-a ", "model-b"],
            gemini_api_key=SecretStr("synthetic-secret"),
        )

        self.assertEqual(settings.gemini_models, ["model-a", "model-b"])
        self.assertEqual(str(settings.gemini_api_key), "**********")
        self.assertNotIn("synthetic-secret", repr(settings))

    def test_settings_reject_out_of_bounds_values_without_secret(self):
        with self.assertRaises(ValidationError) as raised:
            ApplicationSettings(
                wait_timeout=0,
                ocr_confidence_threshold=2,
                gemini_models=["model-a"],
                gemini_api_key=SecretStr("synthetic-secret"),
            )

        text = str(raised.exception)
        self.assertNotIn("synthetic-secret", text)
        self.assertIn("wait_timeout", text)
        self.assertIn("ocr_confidence_threshold", text)

    def test_target_row_validates_and_adapts_to_legacy_tuple(self):
        row = TargetRow(
            type="Graph-title",
            target="EXAMPLE-GRAPH",
            ocr_enabled="true",
            image_enabled="false",
        )
        self.assertEqual(row.as_legacy_tuple(4), ("4", "Graph-title", "EXAMPLE-GRAPH"))

    def test_target_row_rejects_unknown_type_and_control_characters(self):
        with self.assertRaises(ValidationError):
            TargetRow(type="other", target="safe")
        with self.assertRaises(ValidationError):
            TargetRow(type="SID", target="safe\nprivate")

    def test_legacy_config_exposes_validated_settings_model(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "GEMINI_MODELS": "model-a,model-b",
                    "GEMINI_MODEL": "",
                    "GEMINI_API_KEY": "synthetic-secret",
                },
                clear=False,
            ),
        ):
            config = Config(config_dir=Path(directory))
        self.assertIsInstance(config.settings, ApplicationSettings)
        self.assertEqual(config.settings.gemini_models, ["model-a", "model-b"])
        self.assertEqual(str(config.settings.gemini_api_key), "**********")

    def test_legacy_config_has_exact_prd_model_order(self):
        # Avoid the repository's private config/.env and verify the no-secret
        # default in an isolated temporary config directory.
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"GEMINI_MODELS": "", "GEMINI_MODEL": ""},
                clear=False,
            ),
        ):
            config = Config(config_dir=Path(directory))
        self.assertEqual(config.gemini_models, GEMINI_MODELS_DEFAULT)

    def test_csv_parser_uses_typed_boundary_and_skips_invalid_rows(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "targets.csv"
            path.write_text(
                "type,target,ocr_enabled,image_enabled\n"
                "SID,EXAMPLE-SID,true,true\n"
                "other,bad,true,true\n",
                encoding="utf-8",
            )
            self.assertEqual(parse_target_list(path), [("1", "SID", "EXAMPLE-SID")])


if __name__ == "__main__":
    unittest.main()

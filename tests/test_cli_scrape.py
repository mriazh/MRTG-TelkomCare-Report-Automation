import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mrtg_automation.cli import parse_cli_dates, run_scrape_command
from mrtg_automation.config import Config


class TestParseCliDates(unittest.TestCase):
    def test_parse_cli_dates_valid_single_date(self):
        result = parse_cli_dates(date_str="20260801")
        self.assertEqual(result, [date(2026, 8, 1)])

    def test_parse_cli_dates_valid_date_range(self):
        result = parse_cli_dates(start_date_str="20260801", end_date_str="20260803")
        self.assertEqual(result, [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)])


class TestScrapeCommand(unittest.TestCase):
    @patch("mrtg_automation.cli.ensure_directories")
    @patch("mrtg_automation.cli.setup_logging")
    @patch("mrtg_automation.scraper.telkomcare.TelkomCareScraper")
    @patch(
        "mrtg_automation.report.mapping.parse_target_list",
        return_value=[("Example", "sid", "EXAMPLE-SID")],
    )
    def test_scrape_command_builds_config_before_scraper(
        self,
        parse_target_list,
        scraper_class,
        setup_logging,
        ensure_directories,
    ):
        scraper_class.return_value.login.return_value = False
        scraper_class.return_value.last_cancelled = False

        with TemporaryDirectory() as temp_dir:
            result = run_scrape_command(
                date_str="20260801",
                targets_filter="ocr",
                config_dir=Path(temp_dir) / "config",
                output_dir=Path(temp_dir) / "output",
            )

        self.assertEqual(result, 1)
        parse_target_list.assert_called_once()
        scraper_class.assert_called_once()
        self.assertIsInstance(scraper_class.call_args.kwargs["config"], Config)
        setup_logging.assert_called_once()
        ensure_directories.assert_called_once()


if __name__ == "__main__":
    unittest.main()

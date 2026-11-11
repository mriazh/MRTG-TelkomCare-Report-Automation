"""Unit tests for the circuit breaker in TelkomCareScraper.scrape.

The circuit breaker fast-fails a scrape when 3 consecutive targets fail
completely with transient portal errors (DOM failure, graph did not render,
timeout), aborting immediately instead of running the full target list
(2-3 minutes instead of ~2.5 hours). When tripped, the failing target is
marked with error='portal_unresponsive_circuit_breaker'.
"""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from mrtg_automation.scraper.telkomcare import TelkomCareScraper

TRANSIENT_ERROR = "Graph did not render"
NON_TRANSIENT_ERROR = "input_target failed"


class _CaptureResults:
    """Replays canned (filepath, status, error) outcomes for capture_graph."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, target, date_obj):
        outcome = self.outcomes[self.calls % len(self.outcomes)]
        self.calls += 1
        return outcome


class TestCircuitBreaker(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.scraper = TelkomCareScraper(config=self.config, headless=True)
        self.scraper._logged_in = True  # skip login
        self.scraper.session = MagicMock()
        self.scraper.session.is_logged_in.return_value = True  # session stays valid
        self.targets = ["target-1", "target-2", "target-3", "target-4"]
        self.date = datetime.date(2026, 8, 1)

    def _run_scrape(self, outcomes):
        extractor = MagicMock()
        extractor.navigate_to_graph_page.return_value = True
        extractor.recover_graph_page.return_value = True
        capture = _CaptureResults(outcomes)

        def capture_graph(target, date_obj):
            filepath, status, error = capture(target, date_obj)
            extractor.last_status = status
            extractor.last_error = error
            return filepath

        extractor.capture_graph.side_effect = capture_graph

        with (
            patch("mrtg_automation.scraper.extractor.GraphExtractor", return_value=extractor),
            patch("mrtg_automation.scraper.telkomcare.time.sleep", return_value=None),
        ):
            results = self.scraper.scrape(
                targets=self.targets,
                dates=[self.date],
                mode="sid",
            )
        return results, extractor, capture

    def test_circuit_breaker_trips_after_three_consecutive_transient_failures(self):
        # Every target fails transiently. The 3rd consecutive queued target trips
        # the breaker and aborts the scrape before target-4 is reached.
        transient = (None, "error", TRANSIENT_ERROR)
        outcomes = [transient] * 9  # 3 targets x 3 inline attempts each

        results, extractor, capture = self._run_scrape(outcomes)

        # Breaker tripped on target-3: scrape aborted early, target-4 never processed.
        self.assertEqual(capture.calls, 9)
        self.assertEqual(list(results.keys()), [self.targets[2]])
        self.assertIsNone(results[self.targets[2]][self.date])

        # The tripping target is marked with the circuit breaker error.
        status_info = self.scraper.last_statuses[(self.targets[2], self.date)]
        self.assertEqual(status_info["status"], "error")
        self.assertEqual(status_info["error"], "portal_unresponsive_circuit_breaker")

    def test_circuit_breaker_resets_on_success(self):
        # Failure, success, failure, success: a success resets the consecutive
        # counter so the breaker never trips even though targets fail.
        transient = (None, "error", TRANSIENT_ERROR)
        success = ("/output/data/MRTG-Data/20260801/MRTG_target-2_20260801.png", "ok", None)
        outcomes = [
            transient,
            transient,
            transient,  # target-1 queued, breaker=1
            success,  # target-2 success, breaker reset to 0
            transient,
            transient,
            transient,  # target-3 queued, breaker=1
            success,  # target-4 success, breaker reset to 0
        ]

        results, _extractor, capture = self._run_scrape(outcomes)

        # Breaker never tripped: no target carries the circuit breaker error,
        # and a success reset the counter between the two failure runs.
        errors = [info.get("error") for info in self.scraper.last_statuses.values()]
        self.assertNotIn("portal_unresponsive_circuit_breaker", errors)
        # All 4 targets were reached in the main loop (scrape did not abort early).
        self.assertGreaterEqual(capture.calls, 4)

    def test_non_transient_failures_do_not_trip_circuit_breaker(self):
        # Non-transient errors (e.g. input_target failed) are queued for retry
        # but do not count toward the circuit breaker, so it never trips.
        non_transient = (None, "error", NON_TRANSIENT_ERROR)
        outcomes = [non_transient] * 4  # one attempt per target in the main loop

        results, _extractor, capture = self._run_scrape(outcomes)

        # Breaker never tripped.
        errors = [info.get("error") for info in self.scraper.last_statuses.values()]
        self.assertNotIn("portal_unresponsive_circuit_breaker", errors)
        # All 4 targets were processed (scrape did not abort early).
        self.assertGreaterEqual(capture.calls, 4)


if __name__ == "__main__":
    unittest.main()

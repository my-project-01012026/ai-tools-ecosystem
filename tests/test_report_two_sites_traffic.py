"""Offline unit tests for two-provider aggregate traffic report."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from report_two_sites_traffic import report

class DualReportTests(unittest.TestCase):
    def test_both_sources_and_no_cross_platform_guess(self):
        here = {
            "totals": {"rangeViews": 10, "rangeVisitors": 8},
            "topCountries": [{"country":"KZ","views":7},{"country":"US","views":3}],
            "topReferrers": [{"referrer":"Direct","views":10}],
        }
        sites = {"period":"7d","page_views":13,"unique_visitors":9}
        out = report(here, sites, "example-123", "7d")
        self.assertIn("Казахстан (KZ): 7 — 70.0%", out)
        self.assertIn("Просмотры: 13", out)
        self.assertIn("Страны: не предоставляются", out)
        self.assertIn("суммы нельзя трактовать", out)

    def test_missing_both_does_not_invent_traffic(self):
        out = report(None, None, "unknown", "30d")
        self.assertIn("числа неизвестны", out)
        self.assertNotIn("Просмотры: 0", out)

    def test_inconsistent_period_rejected(self):
        with self.assertRaises(ValueError):
            report(None, {"period":"30d", "page_views":10}, "test", "7d")

    def test_invalid_numbers_not_converted_into_visits(self):
        out = report(None, {"period":"7d","page_views":-1, "unique_visitors":"secret"}, "x", "7d")
        self.assertIn("Просмотры: не указано", out)

if __name__ == "__main__":
    unittest.main()

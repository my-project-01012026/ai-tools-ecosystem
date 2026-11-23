"""Unit tests: no network, no credentials, no real visitor data."""
import json
import unittest
from scripts.report_herenow_traffic import AnalyticsError, build_report, read_analytics


class FakeResponse:
    def __init__(self, obj):
        self.value = json.dumps(obj).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, max_bytes):
        return self.value[:max_bytes]


class ReportTests(unittest.TestCase):
    def test_ranking_and_privacy(self):
        payload = {
            "totals": {"rangeViews": 25, "rangeVisitors": 14, "allTimeViews": 45},
            "topCountries": [{"country": "US", "views": 13}, {"country": "KZ", "views": 12}],
            "topReferrers": [{"referrer": "google.com", "views": 17},
                             {"referrer": "Direct", "views": 8}],
            "topPaths": [{"path": "/", "views": 25}],
            "topCrawlers": [{"crawler": "GPTBot", "hits": 7}],
        }
        output = build_report(payload, "example-123", "30d")
        self.assertIn("США (US): 13 — 52.0%", output)
        self.assertIn("Казахстан (KZ): 12 — 48.0%", output)
        self.assertLess(output.index("США"), output.index("Казахстан"))
        self.assertIn("google.com: 17", output)
        self.assertIn("Посетители (приблизительно): 14", output)
        self.assertIn("роботов: 7", output)

    def test_no_data_and_bad_input(self):
        output = build_report({"totals": {}}, "example", "7d")
        self.assertIn("Нет данных", output)
        with self.assertRaises(AnalyticsError):
            read_analytics("../secrets", "30d", "key")
        with self.assertRaises(AnalyticsError):
            read_analytics("example", "100d", "key")
        with self.assertRaises(AnalyticsError):
            read_analytics("example", "7d", "")

    def test_request_uses_get_and_does_not_print_key(self):
        def local_transport(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            self.assertIn("/publishes/example-123/analytics?range=7d", request.full_url)
            self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
            self.assertEqual(timeout, 20)
            return FakeResponse({"totals": {"rangeViews": 2}})
        data = read_analytics("example-123", "7d", "test-key", opener=local_transport)
        self.assertEqual(data["totals"]["rangeViews"], 2)


if __name__ == "__main__":
    unittest.main()

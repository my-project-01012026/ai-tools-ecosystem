"""Offline tests: no network, credentials, deployment or external domains."""
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import Mock, patch

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("retired_routes_audit", SCRIPTS / "check_retired_routes.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def good(path):
    if path in module.RETIRED:
        return 404, b"<h1>Page not found</h1>"
    if path in module.ACTIVE:
        markers = module.ACTIVE[path]
        return 200, ('<meta name="robots" content="noindex,nofollow"/>'
                     + " ".join(markers)).encode("utf-8")
    raise AssertionError("Unexpected route " + path)


class RetiredRouteChecks(unittest.TestCase):
    def test_only_known_slug(self):
        for value in ("other-slug", "https://quiet-flint-6kde.here.now", "../private", ""):
            with self.subTest(value=value):
                fn = Mock()
                with self.assertRaises(module.AuditFailure):
                    module.verify(value, fn)
                fn.assert_not_called()

    def test_complete_positive_sample(self):
        self.assertEqual(len(module.verify(module.SLUG, good)),
                         len(module.RETIRED) + len(module.ACTIVE))

    def test_old_token_url_still_live_is_blocked(self):
        def stale(path):
            if path == "/token/":
                return 200, b"old Solana tokenomics"
            return good(path)
        with self.assertRaisesRegex(module.AuditFailure, "Retired page"):
            module.verify(module.SLUG, stale)

    def test_wrong_404_body_is_blocked(self):
        def fallback(path):
            if path == "/ru/token/":
                return 404, b"access denied"
            return good(path)
        with self.assertRaisesRegex(module.AuditFailure, "custom 404"):
            module.verify(module.SLUG, fallback)

    def test_active_route_missing_is_blocked(self):
        def missing(path):
            if path == "/cvlm/":
                return 404, b"<h1>Page not found</h1>"
            return good(path)
        with self.assertRaisesRegex(module.AuditFailure, "Active page missing"):
            module.verify(module.SLUG, missing)

    def test_crypto_claim_on_home_is_blocked(self):
        def altered(path):
            status, body = good(path)
            if path == "/":
                return status, body + b"solana"
            return status, body
        with self.assertRaisesRegex(module.AuditFailure, "Retired crypto"):
            module.verify(module.SLUG, altered)

    def test_no_redirect_or_mutating_requests(self):
        self.assertIsNone(module.NoRedirect().redirect_request(
            None, None, 301, "moved", {"Location": "https://other.invalid/"}, "https://other.invalid/"))
        src = (SCRIPTS / "check_retired_routes.py").read_text(encoding="utf-8")
        self.assertNotIn("HERENOW_API_KEY", src)
        self.assertNotIn('method="POST"', src)
        self.assertNotIn('method="PUT"', src)

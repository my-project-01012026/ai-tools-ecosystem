"""Offline unit tests for read-only live audit; no HTTP requests are made."""
import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("portfolio_live_audit", SCRIPT_DIR / "audit_live_site.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

HOME = (b'<meta name="robots" content="noindex,nofollow">'
        b'Local Media AI CVLM Platform LocalAIDevManager '
        + audit.PRODUCT_URL.encode("ascii"))
CVLM = b'<meta name="robots" content="noindex,nofollow">CVLM Platform'
ROBOTS = b'User-agent: *\nDisallow: /\n'


class OfflineLiveSiteTests(unittest.TestCase):
    def rows(self):
        return [
            {"path": name, "size": len(data), "hash": hashlib.sha256(data).hexdigest(),
             "contentType": ctype}
            for name, data, ctype in [
                ("index.html", HOME, "text/html; charset=utf-8"),
                ("cvlm/index.html", CVLM, "text/html; charset=utf-8"),
                ("robots.txt", ROBOTS, "text/plain; charset=utf-8"),
            ]
        ]

    def fake_fetch(self, url, size, label, opener=None):
        if url == audit.PRODUCT_URL:
            return b"Product information", {"Content-Type": "text/html"}
        if not url.startswith("https://qa-safe.here.now/"):
            raise AssertionError("Unexpected destination")
        name = url.removeprefix("https://qa-safe.here.now/")
        raw = {"": HOME, "index.html": HOME, "cvlm/index.html": CVLM,
               "robots.txt": ROBOTS}.get(name)
        if raw is None:
            raise AssertionError("Unexpected path")
        return raw, {
            "Content-Type": "text/plain" if name == "robots.txt" else "text/html",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        }

    def test_valid_post_deploy_content_passes(self):
        with patch.object(audit, "fetch", side_effect=self.fake_fetch):
            result = audit.audit("qa-safe", rows=self.rows())
        self.assertEqual(result["files"], 3)
        self.assertEqual(result["warnings"], [])

    def test_invalid_slug_rejected_before_network(self):
        for slug in ("http://evil.invalid", "../evil", "example.com", "-bad", "BAD", ""):
            with self.subTest(slug=slug), patch.object(audit, "fetch") as fetch:
                with self.assertRaises(audit.AuditFailure):
                    audit.audit(slug, rows=self.rows())
                fetch.assert_not_called()

    def test_changed_remote_file_fails(self):
        def altered(url, size, label, opener=None):
            data, headers = self.fake_fetch(url, size, label, opener)
            if label == "cvlm/index.html":
                data = data + b"changed"
            return data, headers
        with patch.object(audit, "fetch", side_effect=altered):
            with self.assertRaisesRegex(audit.AuditFailure, "differs"):
                audit.audit("qa-safe", rows=self.rows())

    def test_missing_robots_disallow_fails(self):
        rows = self.rows()
        def broken(url, size, label, opener=None):
            data, headers = self.fake_fetch(url, size, label, opener)
            if label == "robots.txt":
                data = b"User-agent: *\nAllow: /\n"
            return data, headers
        with patch.object(audit, "fetch", side_effect=broken):
            with self.assertRaises(audit.AuditFailure):
                audit.audit("qa-safe", rows=rows)

    def test_external_site_failure_is_warning(self):
        def unavailable(url, size, label, opener=None):
            if url == audit.PRODUCT_URL:
                raise audit.AuditFailure("test unavailable")
            return self.fake_fetch(url, size, label, opener)
        with patch.object(audit, "fetch", side_effect=unavailable):
            result = audit.audit("qa-safe", rows=self.rows())
        self.assertTrue(any("NOT VERIFIED" in w for w in result["warnings"]))

    def test_missing_response_security_headers_warns(self):
        def headers_missing(url, size, label, opener=None):
            data, headers = self.fake_fetch(url, size, label, opener)
            return data, {"Content-Type": headers["Content-Type"]}
        with patch.object(audit, "fetch", side_effect=headers_missing):
            result = audit.audit("qa-safe", rows=self.rows())
        self.assertEqual(len(result["warnings"]), 3)

    def test_redirects_cannot_be_followed(self):
        self.assertIsNone(audit.NoRedirect().redirect_request(None, None, 302, "Moved",
                                                                  {"Location": "https://evil.invalid"},
                                                                  "https://evil.invalid"))

    def test_script_has_no_write_or_credentials(self):
        text = (SCRIPT_DIR / "audit_live_site.py").read_text(encoding="utf-8")
        self.assertNotIn("HERENOW_API_KEY", text)
        self.assertNotIn("request_json(", text)
        self.assertNotIn("method=\"PUT\"", text)
        self.assertNotIn("method=\"POST\"", text)


if __name__ == "__main__":
    unittest.main()

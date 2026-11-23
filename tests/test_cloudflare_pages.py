"""Offline, no-network security tests of the Cloudflare Pages static bundle."""
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_cloudflare_pages as pack
import audit_cloudflare_pages as live


class CloudflareStagingTests(unittest.TestCase):
    def test_build_exact_audited_bundle(self):
        count = pack.build()
        self.assertEqual(count, 33)
        actual = {p.relative_to(pack.BUILD_DIR).as_posix()
                  for p in pack.BUILD_DIR.rglob("*") if p.is_file()}
        self.assertEqual(len(actual), 34)
        self.assertIn("_headers", actual)
        for excluded in ("README.md", ".github/workflows/site-ci.yml",
                         "scripts/publish_herenow.py", "token/index.html",
                         "ru/token/index.html", "data/tokenomics.json",
                         "assets/app.js"):
            self.assertNotIn(excluded, actual)

    def test_invalid_manifest_fails(self):
        with patch.object(pack, "inventory", side_effect=ValueError("SHA mismatch")):
            with self.assertRaises(ValueError):
                pack.build()

    def test_weak_headers_rejected(self):
        good = pack.HEADERS.read_text(encoding="utf-8")
        pack.verify_headers(good)
        for altered in (good.replace("script-src 'none'", "script-src *"),
                        good.replace("frame-ancestors 'none'", "frame-ancestors *"),
                        good.replace("Strict-Transport-Security:", "HSTS-Removed:")):
            with self.assertRaises(pack.UnsafeBundle):
                pack.verify_headers(altered)

    def test_reject_untrusted_destination(self):
        for host in ("https://test.pages.dev", "evil.com", "test.pages.dev.evil.org",
                     "a/b.pages.dev", "localhost", ""):
            with self.subTest(host=host):
                with self.assertRaises(live.AuditError):
                    live.audit(host, request=lambda *_: self.fail("Unexpected network call"))

    def test_mocked_healthy_staging(self):
        pages = [
            ("index.html", b'<meta name="robots" content="noindex,nofollow">Local Media AI CVLM Platform LocalAIDevManager'),
            ("cvlm/index.html", b'<meta name="robots" content="noindex,nofollow">CVLM Platform'),
            ("404.html", b'<meta name="robots" content="noindex,nofollow">Page not found'),
            ("robots.txt", b"User-agent: *\nDisallow: /\n"),
        ]
        entries = [{"path": path, "size": len(content),
                    "hash": hashlib.sha256(content).hexdigest()} for path, content in pages]
        blobs = {"/" + (path[:-len("index.html")] if path.endswith("index.html") else path): content
                 for path, content in pages}
        headers = {"Strict-Transport-Security": "max-age=31536000",
                   "Content-Security-Policy": "default-src 'none'; script-src 'none'; frame-ancestors 'none'; style-src 'self'",
                   "X-Content-Type-Options": "nosniff",
                   "X-Robots-Tag": "noindex,nofollow"}
        def fetch(host, path, max_bytes):
            if path in live.RETIRED:
                return 404, b"<h1>Page not found</h1>", headers
            return 200, blobs[path], headers
        self.assertEqual(live.audit("test.pages.dev", request=fetch, rows=entries), (4, len(live.RETIRED)))

    def test_missing_hsts_is_hold(self):
        with self.assertRaisesRegex(live.AuditError, "HSTS"):
            live.check_headers({"Content-Security-Policy": "default-src 'none'; script-src 'none'; frame-ancestors 'none'; style-src 'self'",
                                "X-Content-Type-Options": "nosniff",
                                "X-Robots-Tag": "noindex"})

    def test_readonly_auditor(self):
        code = (ROOT / "scripts" / "audit_cloudflare_pages.py").read_text(encoding="utf-8")
        for forbidden in ("HERENOW_API_KEY", "CLOUDFLARE_API_TOKEN", 'method="POST"', 'method="PUT"'):
            self.assertNotIn(forbidden, code)
        self.assertIsNone(live.NoRedirect().redirect_request(
            None, None, 302, "moved", {}, "https://unknown.example"))
if __name__ == "__main__":
    unittest.main()

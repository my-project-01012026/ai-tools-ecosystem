#!/usr/bin/env python3
"""Read-only Pages acceptance test for approved *.pages.dev URLs, with no credentials."""
from __future__ import annotations
import argparse
import hashlib
import re
import sys
import urllib.error
import urllib.request
from publish_herenow import inventory

HOST = re.compile(r"(?:[a-z0-9][a-z0-9-]{0,62}\.)?[a-z0-9][a-z0-9-]{0,62}\.pages\.dev\Z")
RETIRED = ("/token/", "/ru/token/", "/data/tokenomics.json", "/assets/app.js")
class AuditError(Exception):
    pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
OPENER = urllib.request.build_opener(NoRedirect())

def fetch(host, path, limit):
    if not isinstance(host, str) or not HOST.fullmatch(host):
        raise AuditError("Invalid Pages host")
    if not path.startswith("/") or "//" in path or ".." in path:
        raise AuditError("Unexpected path")
    req = urllib.request.Request("https://" + host + path,
        method="GET", headers={"User-Agent": "AI-Tools-Cloudflare-Pages-QA/1.0",
                               "Accept-Encoding": "identity"})
    try:
        with OPENER.open(req, timeout=15) as res:
            data = res.read(limit + 1)
            if len(data) > limit:
                raise AuditError("Remote file exceeds size: " + path)
            return res.status, data, res.headers
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise AuditError("Unexpected status on: " + path) from None
        data = e.read(min(limit, 100000) + 1)
        if len(data) > min(limit, 100000):
            raise AuditError("Oversized 404: " + path)
        return 404, data, e.headers
    except (OSError, urllib.error.URLError, TimeoutError):
        raise AuditError("Request unavailable or redirected: " + path) from None

def check_headers(headers):
    hsts = headers.get("Strict-Transport-Security", "")
    age = re.search(r"(?:^|;)\s*max-age=(\d+)(?:;|$)", hsts, re.I)
    if not age or int(age.group(1)) < 31536000:
        raise AuditError("HSTS response header missing")
    csp = headers.get("Content-Security-Policy", "")
    if not all(x in csp for x in ("default-src 'none'", "script-src 'none'",
                                  "frame-ancestors 'none'", "style-src 'self'")):
        raise AuditError("CSP response header missing or weakened")
    if headers.get("X-Content-Type-Options", "").lower() != "nosniff":
        raise AuditError("X-Content-Type-Options missing")
    if "noindex" not in headers.get("X-Robots-Tag", "").lower():
        raise AuditError("Staging noindex header missing")

def audit(host, request=fetch, rows=None):
    if not isinstance(host, str) or not HOST.fullmatch(host):
        raise AuditError("Only Cloudflare pages.dev site allowed")
    rows = inventory() if rows is None else rows
    seen = set()
    for row in rows:
        name = row["path"]
        # Cloudflare redirects /folder/index.html to the actual public /folder/ URL.
        if name == "404.html":
            route = "/404"  # Pages canonicalizes .html to extensionless URL.
        else:
            route = "/" + (name[:-len("index.html")] if name.endswith("index.html") else name)
        if route in seen:
            raise AuditError("Duplicate public route")
        seen.add(route)
        status, data, headers = request(host, route, row["size"])
        if status != 200 or len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["hash"]:
            raise AuditError("Published file differs from SHA-256 manifest: " + route)
        if name.endswith(".html"):
            if b"noindex,nofollow" not in data:
                raise AuditError("HTML prelaunch noindex absent: " + route)
            check_headers(headers)
        if route == "/" and not all(x in data for x in (b"Local Media AI", b"CVLM Platform", b"LocalAIDevManager")):
            raise AuditError("Product not present on homepage")
    for route in RETIRED:
        status, data, headers = request(host, route, 100000)
        if status != 404 or b"Page not found" not in data:
            raise AuditError("Retired token path accessible: " + route)
    return len(rows), len(RETIRED)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True, help="Actual project.pages.dev URL hostname, no scheme")
    a = p.parse_args()
    try:
        count, removed = audit(a.host)
        print("CLOUDFLARE LIVE PASS:", count, "site resources;", removed, "retired routes")
        return 0
    except (OSError, ValueError, AuditError) as e:
        print("CLOUDFLARE LIVE HOLD:", str(e) if isinstance(e, AuditError) else type(e).__name__, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())

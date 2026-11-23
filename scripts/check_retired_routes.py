#!/usr/bin/env python3
"""Read-only post-deploy proof that retired site URLs serve our custom 404 page.

Intentionally scoped to the existing owned site. No credentials, redirects,
arbitrary destinations, write requests, or third-party HTTP calls.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request

SLUG = "quiet-flint-6kde"
ORIGIN = "https://" + SLUG + ".here.now"
BODY_LIMIT = 256_000
RETIRED = (
    "/token/", "/token/index.html",
    "/ru/token/", "/ru/token/index.html",
    "/data/tokenomics.json", "/assets/app.js", "/assets/og-cover.png",
)
ACTIVE = {
    "/": ("AI Tools Ecosystem", "Local Media AI", "CVLM Platform", "LocalAIDevManager"),
    "/ru/": ("AI Tools Ecosystem", "Local Media AI", "CVLM Platform", "LocalAIDevManager"),
    "/cvlm/": ("CVLM Platform", "CONCEPT"),
    "/ru/cvlm/": ("CVLM Platform",),
    "/localaidevmanager/": ("LocalAIDevManager", "CONCEPT"),
    "/ru/localaidevmanager/": ("LocalAIDevManager",),
}


class AuditFailure(Exception):
    """Safe, public-only audit failure with no remote error-body disclosure."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect())


def request_path(path, opener=None):
    if path not in RETIRED and path not in ACTIVE:
        raise AuditFailure("Unapproved audit path")
    opener = OPENER if opener is None else opener
    req = urllib.request.Request(
        ORIGIN + path,
        headers={"Accept": "text/html", "User-Agent": "AI-Tools-Live-Route-Check/1.0"},
        method="GET",
    )
    try:
        with opener.open(req, timeout=12) as response:
            raw = response.read(BODY_LIMIT + 1)
            if len(raw) > BODY_LIMIT:
                raise AuditFailure("Oversized response: " + path)
            return response.status, raw
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raw = err.read(BODY_LIMIT + 1)
            if len(raw) > BODY_LIMIT:
                raise AuditFailure("Oversized custom 404: " + path)
            return 404, raw
        raise AuditFailure("Unexpected HTTP status: " + path) from None
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        raise AuditFailure("HTTPS verification unavailable: " + path) from None


def verify(slug, request_fn=request_path):
    if slug != SLUG:
        raise AuditFailure("Only the existing owned site may be checked")
    result = []
    for path in RETIRED:
        status, data = request_fn(path)
        if status != 404 or b"Page not found" not in data:
            raise AuditFailure("Retired page is still accessible or custom 404 missing: " + path)
        result.append(path)
    for path, markers in ACTIVE.items():
        status, data = request_fn(path)
        if status != 200 or b"noindex,nofollow" not in data:
            raise AuditFailure("Active page missing or prelaunch indexing enabled: " + path)
        for marker in markers:
            if marker.encode("utf-8") not in data:
                raise AuditFailure("Expected product/stage missing: " + path)
        lowered = data.lower()
        if b"solana" in lowered or b"tokenomics" in lowered or "токен".encode() in lowered:
            raise AuditFailure("Retired crypto content still on active route: " + path)
        result.append(path)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only verification of removed public URLs")
    parser.add_argument("--slug", required=True, help="Must be the existing published site slug")
    args = parser.parse_args(argv)
    try:
        found = verify(args.slug)
        print("LIVE RETIRED ROUTES: PASS; checked", len(RETIRED), "retired and", len(ACTIVE), "active URLs")
        print("PUBLIC SITE:", ORIGIN + "/")
        return 0
    except AuditFailure as exc:
        print("LIVE RETIRED ROUTES: FAIL:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

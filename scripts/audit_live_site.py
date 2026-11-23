#!/usr/bin/env python3
"""Read-only post-publication integrity and HTTPS audit for the frozen static site.

Never takes a full URL from a caller, follows redirects, uses production secrets,
or uploads/modifies data. The slug is the only variable network destination.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.error
import urllib.request

from publish_herenow import inventory

SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,100}\\Z")
PATH_RE = re.compile(r"[A-Za-z0-9._/-]+\\Z")
PRODUCT_URL = "https://local-media-ai-community.cheekysloth259.chatgpt.site/en/"
PRODUCTS = ("Local Media AI", "CVLM Platform", "LocalAIDevManager")
MAX_EXTERNAL_BYTES = 1_000_000


class AuditFailure(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect())


def fetch(url, limit, label, opener=None):
    """Return content and headers; block every redirect and truncate oversized responses."""
    opener = opener if opener is not None else OPENER
    request = urllib.request.Request(
        url, headers={"User-Agent": "AI-Tools-Ecosystem-live-QA/1.0", "Accept": "*/*"}
    )
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise AuditFailure("HTTP status not 200: " + label)
            content = response.read(limit + 1)
            if len(content) > limit:
                raise AuditFailure("Oversized response: " + label)
            return content, response.headers
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AuditFailure("HTTPS request failed (or redirect blocked): " + label) from None


def audit(slug, rows=None, opener=None):
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise AuditFailure("Invalid here.now slug")
    rows = inventory() if rows is None else rows
    names = set()
    for row in rows:
        name = row["path"]
        if (
            not isinstance(name, str)
            or not PATH_RE.fullmatch(name)
            or name.startswith("/")
            or any(part in ("", ".", "..") or part.startswith(".") for part in name.split("/"))
            or name in names
        ):
            raise AuditFailure("Unsafe or duplicate manifest path")
        names.add(name)
    if "index.html" not in names or "robots.txt" not in names:
        raise AuditFailure("Required site files are missing from manifest")

    origin = "https://" + slug + ".here.now/"
    warnings = []
    checked = {}
    root_headers = {}
    for row in rows:
        name = row["path"]
        data, headers = fetch(origin + name, row["size"], name, opener)
        if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["hash"]:
            raise AuditFailure("Deployed file differs from the approved manifest: " + name)
        reported_type = (headers.get("Content-Type") or "").lower().split(";", 1)[0].strip()
        expected_type = row["contentType"].lower().split(";", 1)[0].strip()
        if reported_type != expected_type:
            warnings.append("Unexpected Content-Type for " + name)
        if name.endswith(".html") and b"noindex" not in data.lower():
            raise AuditFailure("Prelaunch noindex missing in " + name)
        if name == "index.html":
            root_headers = headers
            for product in PRODUCTS:
                if product.encode("utf-8") not in data:
                    raise AuditFailure("Missing product on homepage: " + product)
            if PRODUCT_URL.encode("ascii") not in data:
                raise AuditFailure("Local Media AI outbound link changed")
        checked[name] = data

    # The public root must resolve to the same approved homepage.
    root, root_headers = fetch(origin, len(checked["index.html"]), "homepage /", opener)
    if root != checked["index.html"]:
        raise AuditFailure("Public homepage / differs from approved index.html")
    robots = checked["robots.txt"].decode("utf-8", "replace")
    if not re.search(r"(?m)^Disallow:\\s*/\\s*$", robots):
        raise AuditFailure("Prelaunch robots.txt unexpectedly allows indexing")

    for header in ("Strict-Transport-Security", "Content-Security-Policy", "X-Content-Type-Options"):
        if not root_headers.get(header):
            warnings.append("Missing live HTTP header: " + header)

    # External information site is owned/served separately: inability to fetch
    # must be reported, not silently treated as verified.
    try:
        fetch(PRODUCT_URL, MAX_EXTERNAL_BYTES, "Local Media AI external information site", opener)
    except AuditFailure:
        warnings.append("Local Media AI external link live response NOT VERIFIED")

    return {"url": origin, "files": len(rows), "warnings": warnings}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit live here.now static portfolio without credentials")
    parser.add_argument("--slug", required=True, help="Existing site slug, not a URL")
    args = parser.parse_args(argv)
    try:
        result = audit(args.slug)
    except (AuditFailure, ValueError, KeyError) as exc:
        # Do not print arbitrary remote errors, response bodies or credentials.
        print("LIVE AUDIT FAILED:", str(exc) if isinstance(exc, AuditFailure) else type(exc).__name__, file=sys.stderr)
        return 2
    print("LIVE AUDIT FILES VERIFIED:", result["files"])
    print("LIVE AUDIT URL:", result["url"])
    for warning in result["warnings"]:
        print("WARNING:", warning)
    print("LIVE AUDIT:", "PASS WITH WARNINGS" if result["warnings"] else "PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

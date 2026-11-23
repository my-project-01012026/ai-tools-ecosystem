#!/usr/bin/env python3
"""Stage only audited site files on Cloudflare Pages; never deploy or use keys."""
from __future__ import annotations
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "dist-cloudflare"
HEADERS = ROOT / "cloudflare" / "_headers"
sys.path.insert(0, str(ROOT / "scripts"))
from publish_herenow import inventory

class UnsafeBundle(ValueError):
    pass

def verify_headers(content):
    required = (
        "/*\n", "Strict-Transport-Security: max-age=31536000",
        "Content-Security-Policy:", "default-src 'none'",
        "script-src 'none'", "frame-ancestors 'none'",
        "X-Content-Type-Options: nosniff", "X-Robots-Tag: noindex",
    )
    if (not content.lstrip("\n").startswith("# Cloudflare Pages:") or "\r" in content
            or any(x not in content for x in required)
            or "unsafe-inline" in content or "unsafe-eval" in content
            or any(len(x) > 2000 for x in content.splitlines())):
        raise UnsafeBundle("Cloudflare security-header policy invalid or weakened")
    other = [x for x in content.splitlines() if x and not x.startswith("#")]
    if any(not x.startswith("  ") for x in other[1:]):
        raise UnsafeBundle("Unexpected _headers rule")

def build():
    rows = inventory()  # SHA-256, symlinks, exact 33-file inventory, validated before deletion
    verify_headers(HEADERS.read_text(encoding="utf-8"))
    expected = {r["path"] for r in rows}
    if len(rows) != 33 or any(
        bad in expected for bad in
        ("token/index.html", "ru/token/index.html", "data/tokenomics.json", "assets/app.js")
    ):
        raise UnsafeBundle("Old or unapproved content present")
    for essential in ("index.html", "404.html", "robots.txt", "product/index.html",
                      "cvlm/index.html", "localaidevmanager/index.html",
                      "ru/cvlm/index.html", "ru/localaidevmanager/index.html"):
        if essential not in expected:
            raise UnsafeBundle("Required product page missing: " + essential)
    if BUILD_DIR.name != "dist-cloudflare" or BUILD_DIR.parent.resolve() != ROOT.resolve() or BUILD_DIR.is_symlink():
        raise UnsafeBundle("Unapproved output directory")
    if BUILD_DIR.exists():
        if not BUILD_DIR.is_dir():
            raise UnsafeBundle("Unapproved output type")
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()
    for row in rows:
        source = ROOT / row["path"]
        target = BUILD_DIR / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        raw = target.read_bytes()
        if len(raw) != row["size"] or hashlib.sha256(raw).hexdigest() != row["hash"]:
            raise UnsafeBundle("File changed during staging: " + row["path"])
    shutil.copyfile(HEADERS, BUILD_DIR / "_headers")
    verify_headers((BUILD_DIR / "_headers").read_text(encoding="utf-8"))
    actual = {p.relative_to(BUILD_DIR).as_posix() for p in BUILD_DIR.rglob("*") if p.is_file()}
    if actual != expected | {"_headers"}:
        raise UnsafeBundle("Unexpected generated file")
    return len(rows)

if __name__ == "__main__":
    try:
        count = build()
        print("CLOUDFLARE BUNDLE PASS:", count, "verified site files + _headers")
        print("NO DEPLOYMENT OR NETWORK ACTION PERFORMED")
    except (OSError, ValueError) as exc:
        print("CLOUDFLARE BUNDLE BLOCKED:", type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)

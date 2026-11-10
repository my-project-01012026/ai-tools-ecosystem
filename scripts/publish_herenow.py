#!/usr/bin/env python3
"""Verify and explicitly publish the frozen public static site to here.now.

Credentials must come from HERENOW_API_KEY in the process environment.
Neither credentials nor signed upload URLs are written to disk or logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name('SITE_SHA256SUMS.txt')
BASE_URL = 'https://here.now'
ALLOWED_API_HOSTS = frozenset({'here.now', 'api.here.now'})
STORAGE_SUFFIX = '.r2.cloudflarestorage.com'
CLIENT = 'github-actions/ai-tools-ecosystem'
SLUG_PATTERN = re.compile(r'[a-z0-9][a-z0-9-]{1,100}\Z')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse HTTP 3xx; never forward authorization or signed URLs elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Honor the configured system proxy and TLS trust store; block redirects.
_OPENER = urllib.request.build_opener(_NoRedirect())


def _parse_https(url: str):
    if not isinstance(url, str):
        raise ValueError('Invalid destination URL')
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.port is not None or parsed.fragment):
        raise ValueError('Unsafe HTTPS destination')
    return parsed


def _api_origin(url: str):
    parsed = _parse_https(url)
    if parsed.hostname not in ALLOWED_API_HOSTS or parsed.path not in ('', '/') or parsed.query:
        raise ValueError('Unapproved here.now API origin')
    return f'https://{parsed.hostname}'


def _api_url(url: str, method: str):
    parsed = _parse_https(url)
    if parsed.hostname not in ALLOWED_API_HOSTS or parsed.query:
        raise ValueError('Unapproved here.now API URL')
    valid_create = method == 'POST' and parsed.path == '/api/v1/publish'
    valid_lookup = method == 'GET' and bool(re.fullmatch(r'/api/v1/publish/[a-z0-9][a-z0-9-]{1,100}', parsed.path))
    valid_update = method == 'PUT' and bool(re.fullmatch(r'/api/v1/publish/[a-z0-9][a-z0-9-]{1,100}', parsed.path))
    valid_final = method == 'POST' and bool(re.fullmatch(r'/api/v1/publish/[a-z0-9][a-z0-9-]{1,100}/finalize', parsed.path))
    if not (valid_create or valid_lookup or valid_update or valid_final):
        raise ValueError('Unapproved here.now API operation')
    return parsed


def inventory(root=ROOT, manifest=MANIFEST):
    rows = []
    seen = set()
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Invalid site root')
    for line in Path(manifest).read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9._/-]+)', line)
        if not match:
            raise ValueError('Invalid SHA-256 manifest entry')
        digest, name = match.groups()
        parts = name.split('/')
        if (name.startswith('/') or name in seen or any(p in ('', '.', '..') or p.startswith('.') for p in parts)):
            raise ValueError('Unsafe or duplicate filename in manifest')
        seen.add(name)
        path = root / name
        if (any(p.is_symlink() for p in (root / '/'.join(parts[:j]) for j in range(1, len(parts)+1)))
                or not path.is_file() or not path.resolve().is_relative_to(root.resolve())):
            raise ValueError('File missing, symlinked, or escaped root: '+name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('SHA-256 mismatch for '+name)
        ctype = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                 '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
                 '.svg': 'image/svg+xml', '.png': 'image/png',
                 '.txt': 'text/plain; charset=utf-8'}.get(path.suffix.lower())
        if not ctype:
            raise ValueError('Unknown file type: '+name)
        rows.append({'path': name, 'size': len(data), 'contentType': ctype, 'hash': digest})
    if len(rows) != 32 or not any(x['path'] == 'index.html' for x in rows):
        raise ValueError('Expected exactly 32 website files including index.html')
    return rows


def request_json(method, url, value, key):
    _api_url(url, method)
    if not isinstance(key, str) or not key.startswith('hnk_') or len(key) < 20:
        raise ValueError('Missing/invalid here.now API key')
    body = None if method == 'GET' else json.dumps(value, separators=(',', ':')).encode('utf-8')
    req = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': 'Bearer '+key, 'X-HereNow-Client': CLIENT,
        'Content-Type': 'application/json', 'Accept': 'application/json'})
    with _OPENER.open(req, timeout=35) as rsp:
        data = rsp.read(1_000_001)
        if len(data) > 1_000_000:
            raise RuntimeError('Oversized API response')
        return json.loads(data.decode('utf-8'))


def _prepare_uploads(response, rows, site_slug, api_origin):
    if not isinstance(response, dict):
        raise ValueError('Invalid publish response')
    upload = response.get('upload')
    if not isinstance(upload, dict) or not upload.get('versionId'):
        raise ValueError('Missing upload preparation')
    slug = site_slug or response.get('slug')
    if not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug):
        raise ValueError('Missing or invalid site slug')
    if response.get('slug') is not None and response['slug'] != slug:
        raise ValueError('Site slug mismatch')

    final_url = upload.get('finalizeUrl')
    final = _api_url(final_url, 'POST')
    if final_url != api_origin+'/api/v1/publish/'+slug+'/finalize':
        raise ValueError('Unexpected finalize URL')

    entries = upload.get('uploads')
    skipped = upload.get('skipped', [])
    if not isinstance(entries, list) or not isinstance(skipped, list):
        raise ValueError('Invalid upload manifest')
    expected = {row['path']: row for row in rows}
    supplied = set()
    checked = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Invalid upload entry')
        name = entry.get('path')
        if not isinstance(name, str) or name not in expected or name in supplied:
            raise ValueError('Duplicate or unexpected remote upload file')
        if entry.get('method', 'PUT') != 'PUT':
            raise ValueError('Unsupported upload method')
        url = entry.get('url')
        parsed = _parse_https(url)
        if (not parsed.hostname.endswith(STORAGE_SUFFIX)
                or len(parsed.hostname) <= len(STORAGE_SUFFIX)
                or not parsed.path.startswith('/')):
            raise ValueError('Unexpected upload destination')
        headers = entry.get('headers') or {}
        if not isinstance(headers, dict) or set(headers) - {'Content-Type'}:
            raise ValueError('Unexpected upload headers')
        ctype = headers.get('Content-Type', expected[name]['contentType'])
        if ctype != expected[name]['contentType']:
            raise ValueError('Unexpected upload content type')
        supplied.add(name)
        checked.append((name, url, ctype))
    for name in skipped:
        if not isinstance(name, str) or name not in expected or name in supplied:
            raise ValueError('Unexpected or duplicate skipped file')
        supplied.add(name)
    if supplied != set(expected):
        raise ValueError('Incomplete remote file inventory')
    return slug, upload['versionId'], final_url, checked


def publish(rows, key, site_slug=None, root=ROOT, base_url=BASE_URL):
    if not isinstance(key, str) or not key.startswith('hnk_') or len(key) < 20:
        raise ValueError('Missing/invalid here.now API key; publishing refused')
    if site_slug is not None and (not isinstance(site_slug, str) or not SLUG_PATTERN.fullmatch(site_slug)):
        raise ValueError('Invalid site slug')
    origin = _api_origin(base_url)
    api = origin+'/api/v1/publish'+('/'+site_slug if site_slug else '')
    method = 'PUT' if site_slug else 'POST'
    payload = {
        'files': rows, 'displayName': 'AI Tools Ecosystem',
        'displayDescription': 'AI programs, community and proposed Solana token — PRELAUNCH'
    }
    if site_slug:
        # Optimistic concurrency: fail if the live version changed after inspection.
        existing = request_json('GET', api, None, key)
        base_version = existing.get('currentVersionId') if isinstance(existing, dict) else None
        if not isinstance(base_version, str) or not base_version:
            raise RuntimeError('Unable to verify existing site version')
        payload['baseVersionId'] = base_version
    result = request_json(method, api, payload, key)
    slug, version, final_url, uploads = _prepare_uploads(result, rows, site_slug, origin)
    # Validate the entire returned upload list before sending any website file bytes.
    expected = {x['path']: x for x in rows}
    for name, url, ctype in uploads:
        path = Path(root) / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Site file changed')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected[name]['hash']:
            raise RuntimeError('Site file changed during upload')
        request = urllib.request.Request(url, data=raw, method='PUT', headers={'Content-Type': ctype})
        with _OPENER.open(request, timeout=90) as rsp:
            if rsp.status not in (200, 201, 204):
                raise RuntimeError('Upload failed')

    done = request_json('POST', final_url, {'versionId': version}, key)
    if not isinstance(done, dict):
        raise RuntimeError('Invalid finalization response')
    status = done.get('publishStatus')
    target = done.get('siteUrl') or result.get('siteUrl')
    if (done.get('success') is not True or not isinstance(status, dict)
            or status.get('persistence') != 'permanent' or status.get('state') != 'live'
            or status.get('ownership') != 'personal' or status.get('requestAuth') != 'api_key'):
        raise RuntimeError('Publishing did not confirm an owned permanent live site')
    u = _parse_https(target)
    if u.hostname != slug+'.here.now' or u.path not in ('', '/') or u.query:
        raise RuntimeError('Unexpected published site URL')
    return target


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--publish', action='store_true', help='Publish only with owner API credentials')
    p.add_argument('--slug', default=None, help='Existing here.now slug; omit for a new site')
    args = p.parse_args(argv)
    try:
        rows = inventory()
        print('Verified frozen manifest:', len(rows), 'files')
        if not args.publish:
            print('DRY RUN: no network request, no website deployed')
            return 0
        key = os.environ.get('HERENOW_API_KEY', '')
        if not key:
            raise RuntimeError('Missing HERE.NOW credentials; no deployment attempted')
        url = publish(rows, key, args.slug)
        print('PUBLISHED:', url)
        print('LIVE SECURITY AUDIT: still required (HTTP headers, HTTPS, 404, privacy)')
        return 0
    except Exception as exc:
        # Print the exception class only: exception details can contain signed URLs.
        print('BLOCKED:', type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

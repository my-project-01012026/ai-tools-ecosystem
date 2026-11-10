"""Offline security and contract tests: never contact here.now or storage."""
import contextlib
import hashlib
import importlib.util
import io
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'publish_herenow.py'
spec = importlib.util.spec_from_file_location('site_deploy', SCRIPT)
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)
DUMMY_KEY = 'hnk_' + '0' * 32
SLUG = 'sample-owned-site'
FINAL = f'https://here.now/api/v1/publish/{SLUG}/finalize'
STORE = 'https://account.r2.cloudflarestorage.com/bucket/object?X-Amz-Signature=dummy'


class FakeResponse:
    def __init__(self, body=b'{}', status=200):
        self.body = io.BytesIO(body)
        self.status = status

    def read(self, n):
        return self.body.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class DeploymentChecks(unittest.TestCase):
    def fake_rows(self):
        return [{'path': 'index.html', 'hash': hashlib.sha256(b'content').hexdigest(),
                 'size': 7, 'contentType': 'text/html; charset=utf-8'}]

    def reply(self, rows=None, entries=None, skipped=None, **override):
        rows = self.fake_rows() if rows is None else rows
        if entries is None:
            entries = [{'path': x['path'], 'method': 'PUT', 'url': STORE,
                        'headers': {'Content-Type': x['contentType']}} for x in rows]
        reply = {'slug': SLUG, 'upload': {'versionId': 'v1', 'finalizeUrl': FINAL,
                                        'uploads': entries, 'skipped': skipped if skipped is not None else []}}
        reply.update(override)
        return reply

    def test_frozen_site_inventory(self):
        rows = deploy.inventory()
        self.assertEqual(len(rows), 32)
        self.assertIn('index.html', {x['path'] for x in rows})

    def test_reject_manifest_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'manifest').write_text('a'*64+'  ../secret.txt\n')
            with self.assertRaises(ValueError):
                deploy.inventory(root, root/'manifest')

    def test_reject_changed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'index.html').write_text('modified')
            (root/'manifest').write_text('a'*64+'  index.html\n')
            with self.assertRaises(ValueError):
                deploy.inventory(root, root/'manifest')

    def test_reject_symlink_inside_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'real').mkdir()
            (root/'real'/'index.html').write_bytes(b'site')
            (root/'alias').symlink_to(root/'real', target_is_directory=True)
            digest = hashlib.sha256(b'site').hexdigest()
            (root/'manifest').write_text(digest+'  alias/index.html\n')
            with self.assertRaises(ValueError):
                deploy.inventory(root, root/'manifest')

    def test_reject_wrong_key_without_network(self):
        with patch.object(deploy._OPENER, 'open') as opener:
            with self.assertRaises(ValueError):
                deploy.publish([], 'not-an-api-key')
            opener.assert_not_called()

    def test_reject_invalid_slug_without_network(self):
        with patch.object(deploy._OPENER, 'open') as opener:
            with self.assertRaises(ValueError):
                deploy.publish([], DUMMY_KEY, site_slug='../broken')
            opener.assert_not_called()

    def test_block_arbitrary_base_url_before_credentials(self):
        with patch.object(deploy._OPENER, 'open') as opener:
            with self.assertRaises(ValueError):
                deploy.publish([], DUMMY_KEY, base_url='https://attacker.invalid')
            opener.assert_not_called()

    def test_api_key_never_sent_to_other_host(self):
        for url in ('https://attacker.invalid/api/v1/publish',
                    'https://here.now.attacker.invalid/api/v1/publish',
                    'http://here.now/api/v1/publish',
                    'https://user@here.now/api/v1/publish',
                    'https://here.now:443/api/v1/publish',
                    'https://here.now/api/v1/publish?to=attacker.invalid'):
            with self.subTest(url=url), patch.object(deploy._OPENER, 'open') as opener:
                with self.assertRaises(ValueError):
                    deploy.request_json('POST', url, {}, DUMMY_KEY)
                opener.assert_not_called()

    def test_api_only_allows_publish_and_finalize(self):
        with patch.object(deploy._OPENER, 'open') as opener:
            with self.assertRaises(ValueError):
                deploy.request_json('POST', 'https://here.now/api/v1/steal', {}, DUMMY_KEY)
            opener.assert_not_called()

    def test_redirects_never_followed(self):
        req = Mock()
        self.assertIsNone(deploy._NoRedirect().redirect_request(
            req, None, 302, 'Found', {'Location': 'https://attacker.invalid'}, 'https://attacker.invalid'))

    def test_uploads_require_complete_file_set(self):
        with self.assertRaises(ValueError):
            deploy._prepare_uploads(self.reply(entries=[]), self.fake_rows(), None, 'https://here.now')
        with self.assertRaises(ValueError):
            deploy._prepare_uploads(self.reply(entries=[] , skipped=['index.html', 'index.html']),
                                    self.fake_rows(), None, 'https://here.now')

    def test_reject_duplicated_upload_entries(self):
        response = self.reply()
        response['upload']['uploads'].append(dict(response['upload']['uploads'][0]))
        with self.assertRaises(ValueError):
            deploy._prepare_uploads(response, self.fake_rows(), None, 'https://here.now')

    def test_reject_attacker_storage_url(self):
        response = self.reply(entries=[{'path': 'index.html', 'url': 'https://r2.cloudflarestorage.com.attacker.invalid/file'}])
        with self.assertRaises(ValueError):
            deploy._prepare_uploads(response, self.fake_rows(), None, 'https://here.now')

    def test_reject_mismatched_storage_content_type(self):
        response = self.reply(entries=[{'path': 'index.html', 'url': STORE,
                                        'headers': {'Content-Type': 'application/octet-stream'}}])
        with self.assertRaises(ValueError):
            deploy._prepare_uploads(response, self.fake_rows(), None, 'https://here.now')

    def test_reject_unrelated_finalize_path_and_host(self):
        for endpoint in ('https://here.now/api/v1/publish/other-site/finalize',
                         'https://api.here.now/api/v1/publish/sample-owned-site/finalize',
                         'https://here.now/secret-grabber'):
            response = self.reply()
            response['upload']['finalizeUrl'] = endpoint
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                deploy._prepare_uploads(response, self.fake_rows(), None, 'https://here.now')

    def test_skip_mode_never_reads_key_or_makes_request(self):
        with patch.object(deploy._OPENER, 'open') as opener, patch.dict(os.environ, {'HERENOW_API_KEY': DUMMY_KEY}):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(deploy.main([]), 0)
            self.assertNotIn(DUMMY_KEY, output.getvalue())
            opener.assert_not_called()

    def test_errors_do_not_log_credentials_or_signed_urls(self):
        error = RuntimeError('SECRET: '+DUMMY_KEY+' '+STORE)
        with patch.object(deploy, 'publish', side_effect=error), patch.dict(os.environ, {'HERENOW_API_KEY': DUMMY_KEY}):
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(deploy.main(['--publish']), 2)
            logs = stdout.getvalue() + stderr.getvalue()
            self.assertNotIn(DUMMY_KEY, logs)
            self.assertNotIn('X-Amz-Signature', logs)
            self.assertIn('BLOCKED: RuntimeError', stderr.getvalue())

    def test_existing_site_update_requires_verified_version(self):
        with patch.object(deploy, 'request_json', return_value={'slug': SLUG} ) as api:
            with self.assertRaises(RuntimeError):
                deploy.publish(self.fake_rows(), DUMMY_KEY, site_slug=SLUG)
            api.assert_called_once_with('GET', 'https://here.now/api/v1/publish/'+SLUG, None, DUMMY_KEY)

    def test_existing_site_update_uses_optimistic_concurrency(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'index.html').write_bytes(b'content')
            calls = []
            def fake_api(method, url, value, key):
                calls.append((method, url, value))
                if method == 'GET':
                    return {'currentVersionId': 'previous-version'}
                if method == 'PUT':
                    return self.reply(entries=[], skipped=['index.html'])
                if url == FINAL:
                    return {'success': True, 'siteUrl': f'https://{SLUG}.here.now/',
                            'publishStatus': {'persistence': 'permanent', 'state': 'live',
                                              'ownership': 'personal', 'requestAuth': 'api_key'}}
                raise AssertionError('Unexpected API call')
            with patch.object(deploy, 'request_json', side_effect=fake_api), patch.object(deploy._OPENER, 'open') as opener:
                result = deploy.publish(self.fake_rows(), DUMMY_KEY, site_slug=SLUG, root=Path(folder))
            self.assertEqual(result, f'https://{SLUG}.here.now/')
            self.assertEqual([c[0] for c in calls], ['GET', 'PUT', 'POST'])
            self.assertEqual(calls[1][2].get('baseVersionId'), 'previous-version')
            opener.assert_not_called()

    def test_storage_put_does_not_send_bearer(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'index.html').write_bytes(b'content')
            rows = self.fake_rows()
            seen = []
            def fake_api(method, url, value, key):
                seen.append(('api', method, url, key))
                if url == FINAL:
                    return {'success': True, 'siteUrl': f'https://{SLUG}.here.now/',
                            'publishStatus': {'persistence': 'permanent', 'state': 'live',
                                              'ownership': 'personal', 'requestAuth': 'api_key'}}
                return self.reply()
            def fake_storage(req, timeout):
                seen.append(('storage', req.full_url, dict(req.header_items())))
                return FakeResponse(status=200)
            with patch.object(deploy, 'request_json', side_effect=fake_api), patch.object(deploy._OPENER, 'open', side_effect=fake_storage):
                result = deploy.publish(rows, DUMMY_KEY, root=Path(folder))
            self.assertEqual(result, f'https://{SLUG}.here.now/')
            self.assertEqual(len(seen), 3)
            self.assertEqual(seen[1][0], 'storage')
            self.assertNotIn('Authorization', seen[1][2])
            self.assertNotIn(DUMMY_KEY, str(seen[1]))

    def test_no_proxy_bypass_or_untrusted_execution(self):
        source = SCRIPT.read_text(encoding='utf-8')
        self.assertNotIn('ProxyHandler({})', source)
        self.assertNotIn('verify=False', source)
        self.assertNotIn('CERT_NONE', source)
        self.assertNotIn('subprocess.', source)
        self.assertNotIn('os.system(', source)
        self.assertNotIn('eval(', source)

    def test_workflow_requires_manual_main_and_limited_secret_scope(self):
        workflow = SCRIPT.parents[1] / '.github' / 'workflows' / 'deploy-herenow.yml'
        source = workflow.read_text(encoding='utf-8')
        self.assertIn('workflow_dispatch:', source)
        self.assertIn("if: github.ref == 'refs/heads/main'", source)
        self.assertIn('environment: here-now-production', source)
        self.assertIn('persist-credentials: false', source)
        self.assertIn('contents: read', source)
        self.assertEqual(source.count('secrets.HERENOW_API_KEY'), 1)
        self.assertNotIn('pull_request:', source)
        self.assertNotIn('push:', source)

    def test_main_never_publishes_without_key(self):
        with patch.dict(os.environ, {'HERENOW_API_KEY': ''}), patch.object(deploy._OPENER, 'open') as opener:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(deploy.main(['--publish']), 2)
            opener.assert_not_called()
            self.assertIn('BLOCKED:', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()

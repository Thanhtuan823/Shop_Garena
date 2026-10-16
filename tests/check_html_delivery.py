"""Regression tests for raw-HTML delivery and protected page aliases; no DB writes."""
import mimetypes
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from app import app


class HtmlDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        mimetypes.init()
        self.bad_mime = patch.dict(mimetypes.types_map, {
            '.html': 'text/plain', '.js': 'text/plain', '.css': 'text/plain'
        })
        self.bad_mime.start()

    def tearDown(self):
        self.bad_mime.stop()
        self.client.close()

    def test_html_is_inline_utf8_even_with_bad_windows_associations(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'text/html; charset=utf-8')
        self.assertEqual(response.content, (ROOT / 'views/index.html').read_bytes())
        self.assertTrue(response.content.decode('utf-8').startswith('<!doctype html>'))
        self.assertNotIn('attachment', response.headers.get('content-disposition', ''))
        self.assertIn('no-store', response.headers['cache-control'])

    def test_css_and_js_have_explicit_media_types(self):
        for path, media in [('/assets/common.js','application/javascript'),
                            ('/assets/shop.css','text/css'),
                            ('/static/common.js','application/javascript')]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers['content-type'].startswith(media))
            self.assertEqual(response.headers['x-content-type-options'], 'nosniff')

    def test_guest_must_login_for_internal_pages(self):
        for path in ('/staff.html', '/admin.html'):
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertTrue(response.headers['location'].startswith('/?next='))

    def test_static_alias_cannot_expose_protected_html(self):
        for prefix in ('/static/', '/assets/'):
            for page in ('admin.html', 'staff.html'):
                self.assertEqual(self.client.get(prefix + page).status_code, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)

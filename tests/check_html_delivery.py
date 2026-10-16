"""Regression tests for raw-HTML delivery and protected page aliases; no DB writes."""
import mimetypes
from pathlib import Path
import sys
import unittest
from html.parser import HTMLParser
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
        for path, media in [('/js/auth.js','application/javascript'),
                            ('/css/common.css','text/css'),
                            ('/js/admin.js','application/javascript')]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers['content-type'].startswith(media))
            self.assertEqual(response.headers['x-content-type-options'], 'nosniff')

    def test_guest_must_login_for_internal_pages(self):
        for path in ('/staff.html', '/admin.html'):
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers['location'], '/index.html?error=unauthorized')

    def test_static_alias_cannot_expose_protected_html(self):
        for prefix in ('/static/', '/assets/'):
            for page in ('admin.html', 'staff.html'):
                self.assertEqual(self.client.get(prefix + page).status_code, 404)

    def test_separate_frontend_assets_and_no_inline_logic(self):
        class Inspector(HTMLParser):
            def handle_starttag(inner, tag, attrs):
                attrs = dict(attrs)
                self.assertNotEqual(tag, 'style')
                self.assertNotIn('style', attrs)
                self.assertFalse(any(key.startswith('on') for key in attrs))
                if tag == 'script':
                    self.assertTrue(attrs.get('src', '').startswith('/js/'))
        for name in ['index.html', 'staff.html', 'admin.html']:
            Inspector().feed((ROOT/'views'/name).read_text(encoding='utf-8'))
        for role in ['common', 'client', 'staff', 'admin']:
            self.assertEqual(self.client.get('/css/'+role+'.css').status_code, 200)
        for role in ['auth', 'client', 'staff', 'admin']:
            self.assertEqual(self.client.get('/js/'+role+'.js').status_code, 200)

    def test_client_alias_and_local_artwork(self):
        self.assertEqual(self.client.get('/index.html').content, self.client.get('/').content)
        for path in ['banners/hero_banner.png', 'games/logo_lq.png',
                     'games/logo_ff.png', 'games/logo_fco.png']:
            response = self.client.get('/assets/'+path)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers['content-type'].startswith('image/png'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

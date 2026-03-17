#!/usr/bin/env python3
"""
Page load tests — verifies index.html and admin.html load in a real browser
without uncaught JavaScript errors.

Catches issues like missing function definitions, broken script references,
and runtime errors that static analysis can't detect.

Requires:
    pip install playwright
    playwright install chromium

Usage:
    python3 tests/test_page_loads.py
"""

import http.server
import socket
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).parent.parent


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class SilentHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with logging suppressed."""

    def log_message(self, *args):
        pass


class PageLoadTests(unittest.TestCase):
    """
    Loads each page in headless Chromium and asserts no uncaught JS errors.

    A local HTTP server is used so relative fetches (data/*.json, js/*.js)
    resolve correctly — the same way GitHub Pages serves them.
    """

    @classmethod
    def setUpClass(cls):
        cls.port = find_free_port()
        handler = lambda *args, **kwargs: SilentHTTPHandler(
            *args, directory=str(PROJECT_ROOT), **kwargs
        )
        cls.server = http.server.HTTPServer(('localhost', cls.port), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def base_url(self, path=''):
        return f'http://localhost:{self.port}/{path}'

    # ── index.html ──────────────────────────────────────────────────────────

    def test_index_loads_without_js_errors(self):
        """index.html should load, fetch data, and render with no uncaught errors."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))
            page.goto(self.base_url('index.html'), wait_until='networkidle')
            browser.close()

        self.assertEqual(errors, [], f'Uncaught JS errors on index.html:\n' + '\n'.join(errors))

    def test_index_renders_leaderboard(self):
        """Leaderboard should be populated after data loads."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(self.base_url('index.html'), wait_until='networkidle')
            leaderboard_html = page.locator('#leaderboard').inner_html()
            browser.close()

        self.assertTrue(leaderboard_html.strip(), '#leaderboard is empty after load')

    def test_index_renders_bracket(self):
        """Bracket container should be populated after data loads."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(self.base_url('index.html'), wait_until='networkidle')
            bracket_html = page.locator('#bracket-container').inner_html()
            browser.close()

        self.assertTrue(bracket_html.strip(), '#bracket-container is empty after load')

    # ── admin.html ───────────────────────────────────────────────────────────

    def test_admin_unauthenticated_loads_without_js_errors(self):
        """admin.html should show the login gate with no JS errors when not authenticated."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))
            page.goto(self.base_url('admin.html'))
            browser.close()

        self.assertEqual(errors, [], f'Uncaught JS errors on admin.html (unauthenticated):\n' + '\n'.join(errors))

    def test_admin_unauthenticated_shows_auth_gate(self):
        """Auth gate should be visible and admin app should be hidden when not authenticated."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(self.base_url('admin.html'))
            auth_gate_visible = page.locator('#auth-gate').is_visible()
            admin_app_visible = page.locator('#admin-app').is_visible()
            browser.close()

        self.assertTrue(auth_gate_visible, '#auth-gate should be visible when not authenticated')
        self.assertFalse(admin_app_visible, '#admin-app should be hidden when not authenticated')

    def test_admin_authenticated_loads_without_js_errors(self):
        """
        admin.html should load the full admin app without JS errors when authenticated.

        Seeds localStorage before reload so checkAuth() returns true, which
        triggers showApp() → loadAndRender() — the path where the cacheBust
        ReferenceError was caught.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))

            # First load to get an origin for localStorage
            page.goto(self.base_url('admin.html'))
            page.evaluate("localStorage.setItem('mm_admin_authed', 'true')")

            # Reload so checkAuth() returns true on script init
            page.reload(wait_until='networkidle')
            browser.close()

        self.assertEqual(errors, [], f'Uncaught JS errors on admin.html (authenticated):\n' + '\n'.join(errors))

    def test_admin_authenticated_shows_admin_app(self):
        """Admin app should be visible and auth gate hidden after authentication."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            page = context.new_page()

            page.goto(self.base_url('admin.html'))
            page.evaluate("localStorage.setItem('mm_admin_authed', 'true')")
            page.reload(wait_until='networkidle')

            auth_gate_visible = page.locator('#auth-gate').is_visible()
            admin_app_visible = page.locator('#admin-app').is_visible()
            browser.close()

        self.assertFalse(auth_gate_visible, '#auth-gate should be hidden when authenticated')
        self.assertTrue(admin_app_visible, '#admin-app should be visible when authenticated')


if __name__ == '__main__':
    unittest.main(verbosity=2)

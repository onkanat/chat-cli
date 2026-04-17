"""
Tests for Kiwix Hotspot Plugin.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from plugins.kiwix_plugin import KiwixPlugin

class TestKiwixPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = KiwixPlugin()
        self.plugin._config["kiwix_url"] = "http://mock-kiwix:9999"

    @patch("plugins.kiwix_plugin.requests.get")
    def test_get_base_url_success(self, mock_get):
        # Mock success on primary URL
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        url = self.plugin._get_base_url()
        self.assertEqual(url, "http://mock-kiwix:9999")

    @patch("plugins.kiwix_plugin.requests.get")
    def test_get_base_url_fallback(self, mock_get):
        # Mock failure on primary, success on fallback
        def side_effect(url, **kwargs):
            m = MagicMock()
            if "mock-kiwix" in url:
                m.status_code = 404
                raise Exception("Conn Error")
            m.status_code = 200
            return m
        
        mock_get.side_effect = side_effect
        self.plugin._config["fallback_url"] = "http://localhost:9999"
        
        url = self.plugin._get_base_url()
        self.assertEqual(url, "http://localhost:9999")

    def test_html_to_text_stripping(self):
        html = """
        <html>
            <head><style>.css{}</style></head>
            <body>
                <script>alert(1)</script>
                <h1>Title</h1>
                <p>Hello &nbsp; world!</p>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
                <div class="footer">Footer content</div>
            </body>
        </html>
        """
        text = self.plugin._html_to_text(html)
        
        # Verify script/style removed
        self.assertNotIn("alert(1)", text)
        self.assertNotIn(".css", text)
        
        # Verify tags removed but content kept
        self.assertIn("Title", text)
        self.assertIn("Hello   world!", text) # &nbsp; replaced
        self.assertIn("Item 1", text)
        self.assertIn("Item 2", text)

    @patch("plugins.kiwix_plugin.requests.get")
    @patch("plugins.kiwix_plugin.console.print")
    def test_cmd_list(self, mock_print, mock_get):
        # Mock catalog response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"id": "wikid", "title": "Wikipedia", "articleCount": 100, "size": 1024*1024*1024}
        ]
        mock_get.return_value = mock_resp

        self.plugin._cmd_list()
        
        # Check if Table was printed (via mock_print)
        # Table is a rich object, we check if any call contained 'Wikipedia'
        found = False
        for call in mock_print.call_args_list:
            args = call[0]
            if args and hasattr(args[0], "title") and "Libraries" in str(args[0].title):
                found = True
        self.assertTrue(found)

    @patch("plugins.kiwix_plugin.requests.get")
    def test_cmd_open_injects_context(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><title>Physics</title><body>Gravity is a force.</body></html>"
        mock_get.return_value = mock_resp

        context = {"history": []}
        self.plugin._cmd_open(["wikid/A/Gravity.html"], context)

        # Verify history has the injected system message
        self.assertEqual(len(context["history"]), 1)
        self.assertEqual(context["history"][0]["role"], "system")
        self.assertIn("Gravity is a force", context["history"][0]["text"])
        self.assertIn("Physics", context["history"][0]["text"])

if __name__ == "__main__":
    unittest.main()

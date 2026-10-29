"""Exercise the real HTTP handler, including Unicode and error responses."""

from functools import partial
from http.server import ThreadingHTTPServer
import json
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from thelawala.search import SearchEngine
from thelawala.web import SearchHandler


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SearchHandler, engine=SearchEngine()))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_page_assets_health_and_unicode_search(self):
        for path, kind in [("/", "text/html"), ("/styles.css", "text/css"), ("/app.js", "text/javascript")]:
            with self.subTest(path=path), urlopen(self.base+path) as response:
                self.assertIn(kind, response.headers["Content-Type"])
                self.assertTrue(response.read())
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
        with urlopen(self.base+"/api/search?q="+quote("పాలు")) as response:
            result = json.load(response)
            self.assertTrue(result["results"])
            self.assertEqual("milk", result["interpreted_query"])
        with urlopen(self.base+"/api/health") as response:
            self.assertEqual("ok", json.load(response)["status"])

    def test_invalid_query_and_path(self):
        for path, status in [("/api/search?q="+"x"*501, 400), ("/../emails.md", 404)]:
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.base+path)
            self.assertEqual(status, caught.exception.code)
            self.assertIn("error", json.load(caught.exception))

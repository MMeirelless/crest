import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from crest import CustomRest


class QueryHandler(BaseHTTPRequestHandler):
    def do_QUERY(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.received.append((self.command, self.path, body, self.headers))
        response = json.dumps([{"email": json.loads(body)["email"]}]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        pass


class CustomRestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("localhost", 0), QueryHandler)
        cls.thread = Thread(target=cls.server.serve_forever)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        self.server.received = []
        self.command = CustomRest()
        self.command.options.reset()
        self.command.errors = []
        self.command.warnings = []
        self.command._metadata = SimpleNamespace(
            searchinfo=SimpleNamespace(session_key="test-session")
        )
        self.command.url = "http://localhost:{}/contacts".format(
            self.server.server_port
        )
        self.command.method = "query"
        self.command.headers = '{"Content-Type":"application/json","X-User":"$email$"}'
        self.command.data = '{"email":"alice@example.com"}'

    def assert_no_messages(self):
        self.assertEqual(self.command.errors, [])
        self.assertEqual(self.command.warnings, [])

    def test_query_generating_case_insensitive(self):
        for method in ("query", "QUERY", "QuErY"):
            with self.subTest(method=method):
                self.command.method = method
                results = list(self.command.stream(iter([])))
                self.assertEqual(results, [{
                    "status_code": 200,
                    "status_message": '[{"email": "alice@example.com"}]',
                }])
                actual_method, path, body, headers = self.server.received[-1]
                self.assertEqual(actual_method, "QUERY")
                self.assertEqual(path, "/contacts")
                self.assertEqual(body, b'{"email":"alice@example.com"}')
                self.assertEqual(headers["Content-Type"], "application/json")
                self.assertEqual(headers["Authorization"], "Splunk test-session")
                self.assert_no_messages()
        self.assertEqual(len(self.server.received), 3)

    def test_query_streaming_substitutes_each_event(self):
        self.command.url += "/$id$"
        self.command.data = '{"email":"$email$"}'
        records = [
            {"id": 1, "email": "alice@example.com"},
            {"id": 2, "email": "bob@example.com"},
        ]
        results = list(self.command.stream(iter(records)))
        self.assertEqual(len(results), 2)
        self.assertEqual(len(self.server.received), 2)
        for result, received, record in zip(results, self.server.received, records):
            method, path, body, headers = received
            self.assertEqual(method, "QUERY")
            self.assertEqual(path, "/contacts/{}".format(record["id"]))
            self.assertEqual(json.loads(body), {"email": record["email"]})
            self.assertEqual(headers["X-User"], record["email"])
            self.assertEqual(headers["Content-Type"], "application/json")
            self.assertEqual(result["id"], record["id"])
            self.assertEqual(result["status_code"], 200)
            self.assertEqual(json.loads(result["status_message"]), [
                {"email": record["email"]}
            ])
        self.assert_no_messages()

    def test_query_parsing_in_both_modes(self):
        self.command.parse_response = True
        for records in ([], [{"source": "input"}]):
            with self.subTest(records=records):
                results = list(self.command.stream(iter(records)))
                self.assertEqual(results, [{
                    **(records[0] if records else {}),
                    "crest_status_code": 200,
                    "crest_url": self.command.url,
                    "email": "alice@example.com",
                }])
                self.assert_no_messages()

    def test_query_debug_in_both_modes(self):
        self.command.debug = True
        self.command.method = "QUERY"
        self.command.data = '{"email":"$email$"}'
        for records, email in (([], "$email$"), ([{"email": "alice"}], "alice")):
            with self.subTest(records=records):
                results = list(self.command.stream(iter(records)))
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["debug_method"], "query")
                self.assertEqual(json.loads(results[0]["debug_data"]), {"email": email})
                self.assertEqual(results[0]["debug_headers"]["X-User"], email)
                self.assert_no_messages()
        self.assertEqual(self.server.received, [])

    def test_query_request_options(self):
        self.command.timeout = 27
        with patch("crest.requests.request") as request:
            response = self.command.rest(
                "https://api.example.com", "SELECT email FROM contacts",
                {"Content-Type": "application/sql"}, "query", False
            )
        self.assertIs(response, request.return_value)
        request.assert_called_once_with(
            "QUERY", "https://api.example.com",
            headers={"Content-Type": "application/sql"},
            data="SELECT email FROM contacts", timeout=27, verify=False
        )

    def test_query_request_failure(self):
        with patch("crest.requests.request", side_effect=requests.exceptions.Timeout("timeout")):
            result = self.command.rest(self.command.url, None, {}, "query", True)
        self.assertIsNone(result)
        self.assertIn("HTTP request failed: timeout", self.command.errors)

    def test_existing_method_routing(self):
        for method in ("get", "post", "put", "patch", "delete"):
            with self.subTest(method=method), patch("crest.requests." + method) as request:
                response = self.command.rest(self.command.url, "body", {}, method, True)
                self.assertIs(response, request.return_value)
                request.assert_called_once_with(
                    self.command.url, headers={}, data="body", timeout=10, verify=True
                )

    def test_unsupported_method_lists_query(self):
        self.assertIsNone(self.command.rest(self.command.url, None, {}, "invalid", True))
        self.assertEqual(self.command.errors, [
            "Method not recognized. Use: get, post, put, patch, delete, query."
        ])

    def test_query_requires_https_for_external_urls(self):
        with patch("crest.requests.request") as request:
            result = self.command.rest("http://api.example.com", None, {}, "query", True)
        self.assertIsNone(result)
        request.assert_not_called()
        self.assertEqual(self.command.errors, [
            "External URL must use HTTPS. Insecure URL: http://api.example.com"
        ])


if __name__ == "__main__":
    unittest.main()

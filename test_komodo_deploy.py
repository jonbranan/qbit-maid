#!/usr/bin/env python3
"""Tests for .gitea/scripts/komodo-deploy.sh.

Runs the real script against a local mock of the Komodo Core API, so no
network access or live Komodo instance is required.

Run with:  python3 -m unittest -v test_komodo_deploy
"""

import json
import os
import socket
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(REPO_ROOT, ".gitea", "scripts", "komodo-deploy.sh")


def _free_port():
    """Return a port that is currently closed, for the unreachable-host test."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class MockKomodo:
    """Minimal mock of the Komodo Core endpoints used by the deploy script.

    ``responses`` is a list of ``(status, body)`` pairs consumed in order. A
    single-element list repeats forever, which is what the timeout test needs.
    Every request is recorded in ``requests`` for assertions.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length).decode() if length else ""
                mock.requests.append(
                    {
                        "path": self.path,
                        "key": self.headers.get("x-api-key"),
                        "secret": self.headers.get("x-api-secret"),
                        "body": raw,
                    }
                )
                status, body = (
                    mock.responses.pop(0)
                    if len(mock.responses) > 1
                    else mock.responses[0]
                )
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.port


def run_script(env_overrides, timeout=60):
    """Run the deploy script with a clean KOMODO_* environment."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("KOMODO_")}
    env.update(env_overrides)
    return subprocess.run(
        ["sh", SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def base_env(url, **extra):
    env = {
        "KOMODO_URL": url,
        "KOMODO_API_KEY": "test-key",
        "KOMODO_API_SECRET": "test-secret",
        "KOMODO_TARGET": "qbit-maid",
        "KOMODO_WAIT_INTERVAL": "1",
    }
    env.update(extra)
    return env


class TestKomodoDeployScript(unittest.TestCase):
    # --- target selection -------------------------------------------------

    def test_skips_when_target_empty(self):
        r = run_script({"KOMODO_TARGET": ""})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("skipping", r.stdout)

    def test_fails_when_target_empty_and_required(self):
        r = run_script({"KOMODO_TARGET": "", "KOMODO_REQUIRED": "true"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("KOMODO_REQUIRED=true", r.stderr)

    def test_fails_when_url_missing(self):
        r = run_script({"KOMODO_TARGET": "qbit-maid"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("KOMODO_URL is required", r.stderr)

    def test_fails_when_api_key_missing(self):
        r = run_script(
            {
                "KOMODO_URL": "http://127.0.0.1:1",
                "KOMODO_TARGET": "qbit-maid",
                "KOMODO_API_SECRET": "s",
            }
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("KOMODO_API_KEY is required", r.stderr)

    def test_invalid_target_type(self):
        r = run_script(
            {
                "KOMODO_URL": "http://127.0.0.1:1",
                "KOMODO_API_KEY": "k",
                "KOMODO_API_SECRET": "s",
                "KOMODO_TARGET": "qbit-maid",
                "KOMODO_TARGET_TYPE": "bogus",
            }
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("must be 'stack' or 'procedure'", r.stderr)

    # --- request shape ----------------------------------------------------

    def test_sends_auth_headers_and_stack_body(self):
        with MockKomodo(
            [
                (200, {"_id": {"$oid": "u1"}}),
                (200, {"status": "Complete", "success": True}),
            ]
        ) as mock:
            r = run_script(base_env(mock.url))
        self.assertEqual(r.returncode, 0, r.stderr)
        first = mock.requests[0]
        self.assertEqual(first["path"], "/execute/DeployStack")
        self.assertEqual(first["key"], "test-key")
        self.assertEqual(first["secret"], "test-secret")
        self.assertEqual(json.loads(first["body"]), {"stack": "qbit-maid"})

    def test_procedure_target_type(self):
        with MockKomodo(
            [
                (200, {"_id": {"$oid": "u1"}}),
                (200, {"status": "Complete", "success": True}),
            ]
        ) as mock:
            r = run_script(base_env(mock.url, KOMODO_TARGET_TYPE="procedure"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(mock.requests[0]["path"], "/execute/RunProcedure")
        self.assertEqual(json.loads(mock.requests[0]["body"]), {"procedure": "qbit-maid"})

    # --- success and failure ---------------------------------------------

    def test_success_path(self):
        with MockKomodo(
            [
                (200, {"_id": {"$oid": "u1"}}),
                (200, {"status": "Complete", "success": True}),
            ]
        ) as mock:
            r = run_script(base_env(mock.url))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("completed successfully", r.stdout)

    def test_deploy_failure_surfaces_logs(self):
        with MockKomodo(
            [
                (200, {"_id": {"$oid": "u1"}}),
                (
                    200,
                    {
                        "status": "Complete",
                        "success": False,
                        "logs": [{"stage": "Deploy", "msg": "image pull failed"}],
                    },
                ),
            ]
        ) as mock:
            r = run_script(base_env(mock.url))
        self.assertEqual(r.returncode, 1)
        self.assertIn("failed", r.stderr)
        self.assertIn("image pull failed", r.stderr)

    def test_unauthorized(self):
        with MockKomodo([(401, {"error": "bad credentials"})]) as mock:
            r = run_script(base_env(mock.url))
        self.assertEqual(r.returncode, 1)
        self.assertIn("HTTP 401", r.stderr)

    def test_bad_request(self):
        with MockKomodo([(400, {"error": "stack not found"})]) as mock:
            r = run_script(base_env(mock.url))
        self.assertEqual(r.returncode, 1)
        self.assertIn("HTTP 400", r.stderr)

    def test_unreachable_host(self):
        r = run_script(base_env("http://127.0.0.1:%d" % _free_port()))
        self.assertEqual(r.returncode, 1)
        self.assertIn("Could not reach Komodo", r.stderr)

    # --- polling ----------------------------------------------------------

    def test_no_wait_returns_after_accept(self):
        with MockKomodo([(200, {"_id": {"$oid": "u1"}})]) as mock:
            r = run_script(base_env(mock.url, KOMODO_WAIT="false"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not waiting", r.stdout)
        self.assertEqual(len(mock.requests), 1)

    def test_polls_until_complete(self):
        with MockKomodo(
            [
                (200, {"_id": {"$oid": "u1"}}),
                (200, {"status": "Queued"}),
                (200, {"status": "InProgress"}),
                (200, {"status": "Complete", "success": True}),
            ]
        ) as mock:
            r = run_script(base_env(mock.url))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Queued", r.stdout)
        self.assertIn("InProgress", r.stdout)
        self.assertIn("completed successfully", r.stdout)
        self.assertEqual(len(mock.requests), 4)

    def test_timeout(self):
        with MockKomodo(
            [
                (200, {"_id": {"$oid": "u1"}}),
                (200, {"status": "InProgress"}),
            ]
        ) as mock:
            r = run_script(
                base_env(mock.url, KOMODO_WAIT_TIMEOUT="2", KOMODO_WAIT_INTERVAL="1")
            )
        self.assertEqual(r.returncode, 1)
        self.assertIn("Timed out", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

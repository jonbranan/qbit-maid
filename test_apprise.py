"""Tests for AppriseClient — the HTTP poster and its config resolution."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import AppriseClient as apprise_module
from AppriseClient import AppriseClient, apprise_notify


class FakeResponse:
    status_code = 200


class FakeRequests:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, verify=None):
        self.calls.append({"url": url, "json": json, "verify": verify})
        return FakeResponse()


class TestAppriseNotify(unittest.TestCase):
    def test_posts_the_expected_payload(self):
        req = FakeRequests()
        response = apprise_notify(
            req, "apprise.local", 8088, "mailto://u:p@example.com", "Title", "Body"
        )
        self.assertIsInstance(response, FakeResponse)
        self.assertEqual(len(req.calls), 1)
        call = req.calls[0]
        self.assertEqual(call["url"], "http://apprise.local:8088/notify/")
        self.assertEqual(call["json"], {
            "urls": "mailto://u:p@example.com",
            "title": "Title",
            "body": "Body",
        })
        self.assertFalse(call["verify"])


class TestAppriseClientConfig(unittest.TestCase):
    ENV_KEYS = ("DOCKER", "host", "port", "aurls", "title", "body", "toml_path")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, self._cwd)

        saved = {key: os.environ.get(key) for key in self.ENV_KEYS}
        for key in self.ENV_KEYS:
            os.environ.pop(key, None)
        self.addCleanup(self._restore_env, saved)

        self.captured = {}
        patcher = mock.patch.object(
            apprise_module, "apprise_notify", self._fake_notify
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_env(self, saved):
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _fake_notify(self, req_obj, host, port, aurls, title, body):
        self.captured.update(host=host, port=port, aurls=aurls, title=title, body=body)
        return "sent"

    def write_config(self, **overrides):
        values = {
            "host": "config-host",
            "port": 9999,
            "aurls": "mailto://config@example.com",
            "title": "Config Title",
            "body": "Config Body",
        }
        values.update(overrides)
        with open("config.toml", "w", encoding="utf-8") as fh:
            fh.write(
                "[apprise]\n"
                f'host = "{values["host"]}"\n'
                f"port = {values["port"]}\n"
                f'aurls = "{values["aurls"]}"\n'
                f'title = "{values["title"]}"\n'
                f'body = "{values["body"]}"\n'
            )

    def test_reads_values_from_environment(self):
        os.environ.update({
            "DOCKER": "1",
            "host": "env-host",
            "port": "1234",
            "aurls": "mailto://env@example.com",
            "title": "Env Title",
            "body": "Env Body",
        })
        AppriseClient()
        self.assertEqual(self.captured["host"], "env-host")
        self.assertEqual(self.captured["port"], "1234")
        self.assertEqual(self.captured["title"], "Env Title")

    def test_reads_values_from_config_file(self):
        self.write_config()
        AppriseClient()
        self.assertEqual(self.captured["host"], "config-host")
        self.assertEqual(self.captured["port"], 9999)
        self.assertEqual(self.captured["aurls"], "mailto://config@example.com")
        self.assertEqual(self.captured["title"], "Config Title")
        self.assertEqual(self.captured["body"], "Config Body")

    def test_config_file_overrides_environment(self):
        os.environ.update({
            "DOCKER": "1",
            "host": "env-host",
            "port": "1234",
            "aurls": "mailto://env@example.com",
            "title": "Env Title",
            "body": "Env Body",
        })
        self.write_config()
        AppriseClient()
        self.assertEqual(self.captured["host"], "config-host")
        self.assertEqual(self.captured["title"], "Config Title")

    def _write_elsewhere_config(self):
        config_path = os.path.join(self.tmp, "elsewhere.toml")
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.write(
                "[apprise]\n"
                'host = "toml-host"\n'
                "port = 4321\n"
                'aurls = "mailto://toml@example.com"\n'
                'title = "Toml Title"\n'
                'body = "Toml Body"\n'
            )
        return config_path

    def test_toml_path_is_read_when_docker_is_set(self):
        os.environ.update({
            "DOCKER": "1",
            "host": "env-host",
            "port": "1234",
            "aurls": "mailto://env@example.com",
            "title": "Env Title",
            "body": "Env Body",
        })
        os.environ["toml_path"] = self._write_elsewhere_config()
        AppriseClient()
        self.assertEqual(self.captured["host"], "toml-host")
        self.assertEqual(self.captured["port"], 4321)

    def test_toml_path_is_read_without_docker(self):
        os.environ["toml_path"] = self._write_elsewhere_config()
        AppriseClient()
        self.assertEqual(self.captured["host"], "toml-host")
        self.assertEqual(self.captured["port"], 4321)
        self.assertEqual(self.captured["title"], "Toml Title")


if __name__ == "__main__":
    unittest.main()

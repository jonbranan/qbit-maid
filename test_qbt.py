"""End-to-end tests for the Qbt object in qbit-maid.py.

The module name contains a hyphen, so it cannot be imported normally; it is
loaded by path with ``qbittorrentapi`` stubbed out.
"""
import importlib.util
import logging
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

from qbt_fakes import (
    FailingPushover,
    FakeAPIError,
    FakeQbtClient,
    StubPushover,
    torrent,
)

REPO = os.path.dirname(os.path.abspath(__file__))

CONFIG_TEMPLATE = """
[qbittorrent]
host = "127.0.0.1"
port = 8080
username = "user"
password = "pass"

[logging]
use_log = true
log_level = "{log_level}"
log_path = "{log_path}"

[app_tags]
protected_tag = "ipt"
non_protected_tag = "public"

[torrent]
max_age = 2419200
min_age = 432000
delete_torrents = {delete_torrents}

[pushover]
use_pushover = {use_pushover}
po_key = "USERKEY"
po_token = "TOKEN"

[apprise]
use_apprise = {use_apprise}
host = "localhost"
port = 8088
aurls = "mailto://user:pass@example.com"

[dragnet]
enable_dragnet = false
dragnet_outfile = "{dragnet_outfile}"

[telemetry]
enable_telemetry = false
telemetry_outfile = "{telemetry_outfile}"

[ignored_categories]
tech = "tech"

[ignored_domains]
tracker-example = "tracker.example"

[ignored_tags]
save = "save"

[healthcheck]
use_healthcheck = {use_healthcheck}
healthcheck_url = "https://example.com/ping/x"
"""


def load_qbit_maid(as_main=False):
    """Import qbit-maid.py by path, with qbittorrentapi stubbed.

    With ``as_main=True`` the module is executed as ``__main__``, which runs
    the ``Qbt()`` entry point at import time.
    """
    # Install the stub once and reuse it, so tests can patch its Client.
    # This keeps the suite off any real qBittorrent even when the real package
    # is installed in the environment.
    stub = sys.modules.get("qbittorrentapi")
    if getattr(stub, "_qbit_maid_stub", False) is not True:
        stub = types.ModuleType("qbittorrentapi")
        stub.APIError = FakeAPIError
        stub.Client = FakeQbtClient
        stub._qbit_maid_stub = True
        sys.modules["qbittorrentapi"] = stub
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    spec = importlib.util.spec_from_file_location(
        "__main__" if as_main else "qbit_maid", os.path.join(REPO, "qbit-maid.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QbtTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, self._cwd)
        self.addCleanup(self._close_log_handlers)
        self.module = load_qbit_maid()

    def _close_log_handlers(self):
        logger = logging.getLogger("qbit-maid")
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def write_config(self, **overrides):
        values = {
            "log_level": "CRITICAL",  # keep the console handler quiet
            "log_path": os.path.join(self.tmp, "qc.log"),
            "delete_torrents": "true",
            "use_pushover": "false",
            "use_apprise": "false",
            "use_healthcheck": "false",
            "dragnet_outfile": os.path.join(self.tmp, "orphaned.csv"),
            "telemetry_outfile": os.path.join(self.tmp, "telemetry.csv"),
        }
        values.update(overrides)
        with open("config.toml", "w", encoding="utf-8") as fh:
            fh.write(CONFIG_TEMPLATE.format(**values))

    def build(self, torrents, client=None, **config_overrides):
        self.write_config(**config_overrides)
        client = client or FakeQbtClient(torrents=torrents)

        def factory(**kwargs):
            client.init_kwargs = kwargs
            return client

        with mock.patch.object(self.module.qbittorrentapi, "Client",
                               side_effect=factory):
            qbt = self.module.Qbt()
        return qbt, client


class TestQbtPipeline(QbtTestCase):
    def sample_torrents(self):
        return [
            torrent(tags="ipt", ratio=0.5, time_active=9999999,
                    infohash="del-protected"),
            torrent(tags="public", tracker="https://other.example/a", ratio=0.1,
                    infohash="del-public"),
            torrent(tags="public", state="downloading", infohash="skip-downloading"),
            torrent(tags="other", infohash="orphan-1"),
            torrent(tracker="", infohash="ignored-blank-tracker"),
            torrent(category="tech", infohash="ignored-category"),
            torrent(tags="ipt", seeding_time=1, infohash="premature"),
            torrent(tags="", infohash="new-blank-tag"),
        ]

    def test_full_run_counts_every_bucket(self):
        qbt, client = self.build(self.sample_torrents())
        self.assertEqual(qbt.total_torrents, 8)
        self.assertEqual(qbt.ignored_counter, 2)
        self.assertEqual(qbt.preme_tor_counter, 1)
        self.assertEqual(qbt.up_tor_counter, 2)
        self.assertCountEqual(qbt.torrent_hash_delete_list,
                              ["del-protected", "del-public"])

    def test_full_run_deletes_the_selected_hashes(self):
        _, client = self.build(self.sample_torrents())
        self.assertEqual(len(client.deleted), 1)
        delete_files, hashes = client.deleted[0]
        self.assertTrue(delete_files)
        self.assertCountEqual(hashes, ["del-protected", "del-public"])

    def test_full_run_tags_new_torrents(self):
        _, client = self.build(self.sample_torrents())
        self.assertIn(("ipt", "new-blank-tag"), client.added_tags)

    def test_dry_run_does_not_delete(self):
        qbt, client = self.build(self.sample_torrents(), delete_torrents="false")
        self.assertFalse(qbt.delete_torrents)
        self.assertEqual(client.deleted, [])
        self.assertCountEqual(qbt.torrent_hash_delete_list,
                              ["del-protected", "del-public"])

    def test_client_is_constructed_from_config(self):
        _, client = self.build([torrent(tags="ipt")])
        self.assertEqual(client.init_kwargs["host"], "127.0.0.1")
        self.assertEqual(client.init_kwargs["port"], 8080)
        self.assertEqual(client.init_kwargs["username"], "user")

    def test_client_logs_in(self):
        _, client = self.build([torrent(tags="ipt")])
        self.assertTrue(client.logged_in)

    def test_runtime_is_recorded(self):
        qbt, _ = self.build([torrent(tags="ipt")])
        self.assertIsNotNone(qbt.et)
        self.assertGreaterEqual(qbt.et, qbt.st)

    def test_empty_torrent_list_is_handled(self):
        """A qBittorrent instance with zero torrents must not abort the run."""
        qbt, client = self.build([])
        self.assertEqual(qbt.total_torrents, 0)
        self.assertEqual(qbt.torrent_hash_delete_list, [])
        self.assertEqual(client.deleted, [])

    def test_empty_torrent_list_still_sends_a_summary(self):
        stub = StubPushover()
        with mock.patch.object(self.module.pushover, "Pushover",
                               return_value=stub):
            self.build([], use_pushover="true")
        self.assertEqual(len(stub.calls), 1)
        self.assertEqual(stub.calls[0]["kwargs"]["title"],
                         "qbit-maid: nothing removed")


class TestQbtConfigSources(QbtTestCase):
    def test_config_is_read_from_toml_path_env(self):
        config_path = os.path.join(self.tmp, "from-env.toml")
        self.write_config()
        os.replace("config.toml", config_path)
        os.environ["toml_path"] = config_path
        self.addCleanup(os.environ.pop, "toml_path", None)
        with mock.patch.object(self.module.qbittorrentapi, "Client",
                               return_value=FakeQbtClient(torrents=[torrent(tags="ipt")])):
            qbt = self.module.Qbt()
        self.assertEqual(qbt.tracker_protected_tag, "ipt")

    def test_local_config_toml_wins_over_toml_path(self):
        elsewhere = os.path.join(self.tmp, "elsewhere.toml")
        with open(elsewhere, "w", encoding="utf-8") as fh:
            fh.write(CONFIG_TEMPLATE.format(
                log_level="CRITICAL",
                log_path=os.path.join(self.tmp, "other.log"),
                delete_torrents="true", use_pushover="false",
                use_apprise="false", use_healthcheck="false",
                dragnet_outfile="a.csv", telemetry_outfile="b.csv",
            ).replace('protected_tag = "ipt"', 'protected_tag = "from-elsewhere"'))
        os.environ["toml_path"] = elsewhere
        self.addCleanup(os.environ.pop, "toml_path", None)
        self.write_config()
        with mock.patch.object(self.module.qbittorrentapi, "Client",
                               return_value=FakeQbtClient(torrents=[torrent(tags="ipt")])):
            qbt = self.module.Qbt()
        self.assertEqual(qbt.tracker_protected_tag, "ipt")


class TestQbtNotifiers(QbtTestCase):
    def test_pushover_summary_is_sent_when_enabled(self):
        stub = StubPushover()
        with mock.patch.object(self.module.pushover, "Pushover",
                               return_value=stub):
            qbt, _ = self.build([torrent(tags="public", infohash="h1")],
                                use_pushover="true")
        self.assertEqual(len(stub.calls), 1)
        self.assertEqual(stub.calls[0]["kwargs"]["title"],
                         "qbit-maid: 1 torrent removed")

    def test_apprise_is_sent_when_enabled(self):
        captured = {}

        def fake_apprise(req_obj, host, port, aurls, title, body):
            captured.update(host=host, port=port, title=title, body=body)

        with mock.patch.object(self.module, "apprise_notify", fake_apprise):
            self.build([torrent(tags="public", infohash="h1")],
                       use_apprise="true")
        self.assertEqual(captured["host"], "localhost")
        self.assertEqual(captured["port"], 8088)
        self.assertIn("1 removed", captured["body"])

    def test_healthcheck_is_pinged_twice_when_enabled(self):
        calls = []

        def fake_ping(obj, req_obj, url):
            calls.append(url)

        with mock.patch.object(self.module, "send_ping", fake_ping):
            self.build([torrent(tags="ipt")], use_healthcheck="true")
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0].endswith("/start"))
        self.assertFalse(calls[1].endswith("/start"))


class TestQbtLoginFailure(QbtTestCase):
    def test_login_error_notifies_and_continues(self):
        client = FakeQbtClient(torrents=[torrent(tags="ipt")],
                               login_error=FakeAPIError("bad credentials"))
        stub = StubPushover()
        with mock.patch.object(self.module.pushover, "Pushover",
                               return_value=stub):
            qbt, _ = self.build([torrent(tags="ipt")], client=client,
                                use_pushover="true")
        # The error notification goes out first, then the run summary.
        self.assertEqual(len(stub.calls), 2)
        self.assertEqual(stub.calls[0]["kwargs"]["title"],
                         "qbit-maid API ERROR")
        self.assertIn("bad credentials", stub.calls[0]["body"])
        self.assertEqual(qbt.total_torrents, 1)

    def test_login_error_without_pushover_does_not_crash(self):
        client = FakeQbtClient(torrents=[torrent(tags="ipt")],
                               login_error=FakeAPIError("bad credentials"))
        qbt, _ = self.build([torrent(tags="ipt")], client=client)
        self.assertEqual(qbt.total_torrents, 1)

    def test_login_error_survives_a_failing_pushover(self):
        client = FakeQbtClient(torrents=[torrent(tags="ipt")],
                               login_error=FakeAPIError("bad credentials"))
        with mock.patch.object(self.module.pushover, "Pushover",
                               return_value=FailingPushover()):
            qbt, _ = self.build([torrent(tags="ipt")], client=client,
                                use_pushover="true")
        self.assertEqual(qbt.total_torrents, 1)


class TestMainGuard(QbtTestCase):
    def test_running_as_main_executes_the_pipeline(self):
        self.write_config()
        client = FakeQbtClient(torrents=[torrent(tags="ipt")])
        stub = sys.modules["qbittorrentapi"]
        with mock.patch.object(stub, "Client", return_value=client):
            load_qbit_maid(as_main=True)
        self.assertTrue(client.logged_in)
        self.assertEqual(len(client.deleted), 1)


class TestIgnoredTagsConfig(QbtTestCase):
    def test_ignored_tags_reads_the_ignored_tags_section(self):
        qbt, _ = self.build([torrent(tags="ipt")])
        self.assertEqual(qbt.ignored_tags, {"save": "save"})
        self.assertNotIn("tracker-example", qbt.ignored_tags)

    def test_ignored_tag_from_config_is_skipped(self):
        qbt, _ = self.build([torrent(tags="save", infohash="ignored-tag")])
        self.assertEqual(qbt.ignored_counter, 1)
        self.assertEqual(qbt.tracker_list, [])


if __name__ == "__main__":
    unittest.main()

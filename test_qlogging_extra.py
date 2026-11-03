"""Tests for the qlogging helpers that the notifier tests do not reach."""
import datetime
import logging
import os
import shutil
import tempfile
import unittest
from collections import Counter

from qbt_fakes import FailingPushover, FakeQbt, StubPushover, torrent
from qlogging import (
    LOGGER_NAME,
    debug_torrent_list,
    format_runtime,
    get_script_runtime,
    list_first_tor,
    list_qbit_api_info,
    log_torrent,
    print_processor,
    process_counts,
    send_ping,
    setup_logging,
    summary_runtime,
    summary_stats,
    tor_notify,
    tor_notify_error,
    tor_notify_summary,
    tornotifytest,
    torrent_count,
)


class FakePushoverModule:
    """Stands in for the vendored ``pushover`` module."""

    def __init__(self):
        self.created = []

    def Pushover(self, token):  # noqa: N802 - mirrors the library's name
        self.created.append(token)
        return StubPushover()


class FailingRequests:
    class RequestException(Exception):
        pass

    def __init__(self):
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        raise self.RequestException("boom")


class TestNotifySetup(unittest.TestCase):
    def test_tor_notify_creates_client_when_enabled(self):
        qbt = FakeQbt(use_pushover=True, po_token="TOKEN")
        qbt.po = FakePushoverModule()
        tor_notify(qbt)
        self.assertEqual(qbt.po.created, ["TOKEN"])
        self.assertIsInstance(qbt.poc, StubPushover)

    def test_tor_notify_is_a_noop_when_disabled(self):
        qbt = FakeQbt(use_pushover=False)
        qbt.po = FakePushoverModule()
        tor_notify(qbt)
        self.assertEqual(qbt.po.created, [])

    def test_tornotifytest_sends_a_test_message(self):
        qbt = FakeQbt()
        tornotifytest(qbt)
        self.assertEqual(len(qbt.poc.calls), 1)
        self.assertEqual(qbt.poc.calls[0]["user"], "USERKEY")
        self.assertEqual(qbt.poc.calls[0]["body"], "Test Message")
        self.assertEqual(qbt.poc.calls[0]["kwargs"]["title"], "qbit-maid")


class TestTorNotifyError(unittest.TestCase):
    def test_sends_through_the_pushover_client(self):
        qbt = FakeQbt(use_pushover=True)
        tor_notify_error(qbt, RuntimeError("boom"))
        self.assertEqual(len(qbt.poc.calls), 1)
        self.assertEqual(qbt.poc.calls[0]["user"], "USERKEY")
        self.assertIn("boom", qbt.poc.calls[0]["body"])
        self.assertEqual(qbt.poc.calls[0]["kwargs"]["title"],
                         "qbit-maid API ERROR")

    def test_skips_pushover_when_disabled(self):
        qbt = FakeQbt(use_pushover=False)
        tor_notify_error(qbt, RuntimeError("boom"))
        self.assertEqual(qbt.poc.calls, [])

    def test_skips_pushover_when_no_client_was_built(self):
        qbt = FakeQbt(use_pushover=True, poc=None)
        tor_notify_error(qbt, RuntimeError("boom"))  # must not raise

    def test_survives_a_failing_pushover(self):
        qbt = FakeQbt(use_pushover=True, poc=FailingPushover())
        tor_notify_error(qbt, RuntimeError("boom"))  # must not raise

    def test_accepts_a_custom_title(self):
        qbt = FakeQbt(use_pushover=True)
        tor_notify_error(qbt, RuntimeError("boom"), title="Custom")
        self.assertEqual(qbt.poc.calls[0]["kwargs"]["title"], "Custom")


class TestCounters(unittest.TestCase):
    def test_process_counts_buckets_by_tag(self):
        qbt = FakeQbt(
            ct=Counter,
            tracker_list=[torrent(tags="ipt"), torrent(tags="ipt"), torrent(tags="public")],
        )
        process_counts(qbt)
        self.assertEqual(qbt.c["ipt"], 2)
        self.assertEqual(qbt.c["public"], 1)

    def test_print_processor_logs_every_counter(self):
        qbt = FakeQbt()
        with self.assertLogs("qbit-maid-test", level="INFO") as captured:
            print_processor(qbt)
        joined = "\n".join(captured.output)
        for label in ("Total", "Premature", "Ignored", "Protected",
                      "Non-protected", "Orphaned", "Marked for deletion"):
            self.assertIn(label, joined)

    def test_torrent_count_logs_both_tags(self):
        qbt = FakeQbt()
        with self.assertLogs("qbit-maid-test", level="DEBUG") as captured:
            torrent_count(qbt)
        joined = "\n".join(captured.output)
        self.assertIn('tag["ipt"] 10', joined)
        self.assertIn('tag["public"] 20', joined)


class TestDebugHelpers(unittest.TestCase):
    def test_list_first_tor_logs_each_field(self):
        qbt = FakeQbt(torrent_list=[torrent(name="First")])
        with self.assertLogs("qbit-maid-test", level="DEBUG") as captured:
            list_first_tor(qbt)
        self.assertIn("First", "\n".join(captured.output))

    def test_list_first_tor_honours_the_index(self):
        qbt = FakeQbt(torrent_list=[torrent(name="Zero"), torrent(name="One")])
        with self.assertLogs("qbit-maid-test", level="DEBUG") as captured:
            list_first_tor(qbt, index=1)
        self.assertIn("One", "\n".join(captured.output))

    def test_list_first_tor_handles_an_empty_list(self):
        qbt = FakeQbt(torrent_list=[])
        with self.assertLogs("qbit-maid-test", level="DEBUG") as captured:
            list_first_tor(qbt)
        self.assertIn("No torrents found", "\n".join(captured.output))

    def test_list_qbit_api_info_logs_versions(self):
        qbt = FakeQbt()
        with self.assertLogs("qbit-maid-test", level="DEBUG") as captured:
            list_qbit_api_info(qbt)
        joined = "\n".join(captured.output)
        self.assertIn("v4.6.2", joined)
        self.assertIn("2.9.3", joined)

    def test_debug_torrent_list_logs_the_list(self):
        qbt = FakeQbt(torrent_list=[torrent(name="Logged")])
        with self.assertLogs("qbit-maid-test", level="DEBUG") as captured:
            debug_torrent_list(qbt)
        self.assertIn("Logged", "\n".join(captured.output))


class TestRuntime(unittest.TestCase):
    def test_get_script_runtime_sets_extm_for_pushover(self):
        qbt = FakeQbt(use_pushover=True, use_apprise=False)
        get_script_runtime(qbt)
        self.assertEqual(qbt.extm, "Execution time: [0:00:12]")

    def test_get_script_runtime_sets_extm_for_apprise(self):
        qbt = FakeQbt(use_pushover=False, use_apprise=True)
        get_script_runtime(qbt)
        self.assertEqual(qbt.extm, "Execution time: [0:00:12]")

    def test_get_script_runtime_without_notifiers_leaves_extm_alone(self):
        qbt = FakeQbt(use_pushover=False, use_apprise=False, extm="")
        get_script_runtime(qbt)
        self.assertEqual(qbt.extm, "")

    def test_format_runtime_falls_back_to_str_for_non_timedelta(self):
        self.assertEqual(format_runtime(12), "12")
        self.assertEqual(format_runtime("n/a"), "n/a")

    def test_summary_runtime_falls_back_to_extm(self):
        class OnlyExtm:
            extm = "Execution time: [5s]"

        self.assertEqual(summary_runtime(OnlyExtm()), "5s")

    def test_summary_runtime_returns_unknown_without_any_source(self):
        class Nothing:
            pass

        self.assertEqual(summary_runtime(Nothing()), "unknown")


class TestSummaryStatsEdgeCases(unittest.TestCase):
    def test_missing_tag_returns_zero(self):
        qbt = FakeQbt(c={})
        stats = summary_stats(qbt)
        self.assertEqual(stats["protected"], 0)
        self.assertEqual(stats["non_protected"], 0)

    def test_unindexable_counter_returns_zero(self):
        qbt = FakeQbt(c=[])
        stats = summary_stats(qbt)
        self.assertEqual(stats["protected"], 0)

    def test_blank_tag_returns_zero(self):
        qbt = FakeQbt(tracker_protected_tag="", tracker_non_protected_tag="")
        stats = summary_stats(qbt)
        self.assertEqual(stats["protected"], 0)
        self.assertEqual(stats["non_protected"], 0)


class TestSendPing(unittest.TestCase):
    def test_send_ping_swallows_request_errors(self):
        qbt = FakeQbt()
        failing = FailingRequests()
        send_ping(qbt, failing, "https://example.com/ping/x")  # must not raise
        self.assertEqual(failing.calls, ["https://example.com/ping/x"])

    def test_send_ping_logs_the_failure(self):
        qbt = FakeQbt()
        with self.assertLogs("qbit-maid-test", level="INFO") as captured:
            send_ping(qbt, FailingRequests(), "https://example.com/ping/x")
        self.assertIn("Ping failed", "\n".join(captured.output))


class TestSetupLogging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log_path = os.path.join(self.tmp, "qc.log")
        self.addCleanup(self._reset_logger)

    def _reset_logger(self):
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def test_disabled_logging_uses_a_null_handler(self):
        logger = setup_logging(False, self.log_path, "INFO")
        self.assertEqual(logger.level, logging.CRITICAL)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.NullHandler)
        self.assertFalse(os.path.exists(self.log_path))

    def test_enabled_logging_writes_to_file_and_console(self):
        logger = setup_logging(True, self.log_path, "DEBUG")
        self.assertEqual(logger.level, logging.DEBUG)
        self.assertEqual(len(logger.handlers), 2)
        logger.info("hello from the test")
        for handler in logger.handlers:
            handler.flush()
        with open(self.log_path, encoding="utf-8") as fh:
            self.assertIn("hello from the test", fh.read())

    def test_unknown_level_falls_back_to_info(self):
        logger = setup_logging(True, self.log_path, "shouty")
        self.assertEqual(logger.level, logging.INFO)

    def test_setup_is_idempotent(self):
        first = setup_logging(True, self.log_path, "INFO")
        previous_file_handler = first.handlers[0]
        self.assertIsNotNone(previous_file_handler.stream)
        logger = setup_logging(True, self.log_path, "INFO")
        self.assertEqual(len(logger.handlers), 2)
        # The replaced handler is closed, so its file descriptor is released.
        self.assertIsNone(previous_file_handler.stream)

    def test_rotation_parameters_are_applied(self):
        logger = setup_logging(True, self.log_path, "INFO",
                               max_bytes=1234, backup_count=7)
        file_handler = logger.handlers[0]
        self.assertEqual(file_handler.maxBytes, 1234)
        self.assertEqual(file_handler.backupCount, 7)


class TestLogTorrent(unittest.TestCase):
    def test_log_torrent_attaches_structured_fields(self):
        logger = logging.getLogger("qbit-maid-test")
        previous_level = logger.level
        logger.setLevel(logging.DEBUG)
        self.addCleanup(logger.setLevel, previous_level)
        record = {}

        class Capture(logging.Handler):
            def emit(self, rec):
                record.update(rec.__dict__)

        handler = Capture()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)

        log_torrent(logger, logging.INFO, torrent(name="A" * 40, infohash="deadbeef"),
                    message="processing")
        self.assertEqual(record["torrent_hash"], "deadbeef")
        self.assertEqual(record["torrent_name"], "A" * 20)
        self.assertEqual(record["msg"], "processing")

    def test_log_torrent_tolerates_missing_fields(self):
        logger = logging.getLogger("qbit-maid-test")
        log_torrent(logger, logging.INFO, {})  # must not raise


class TestNotifySummarySound(unittest.TestCase):
    def test_sound_is_passed_through(self):
        qbt = FakeQbt(config={"pushover": {"sound": "siren"}})
        tor_notify_summary(qbt)
        self.assertEqual(qbt.poc.calls[0]["kwargs"]["sound"], "siren")


if __name__ == "__main__":
    unittest.main()

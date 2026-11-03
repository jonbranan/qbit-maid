"""Shared fakes for the qbit-maid test suite.

This is test scaffolding, not production code, so it is excluded from the
coverage report (see ``.coveragerc``).
"""
import datetime
import logging
from collections import Counter

# Keep test output clean: the pipeline logs warnings for ignored torrents.
_test_logger = logging.getLogger("qbit-maid-test")
_test_logger.addHandler(logging.NullHandler())
_test_logger.propagate = False


# ---------------------------------------------------------------------------
# qbittorrentapi stand-in
# ---------------------------------------------------------------------------
class FakeApp:
    version = "v4.6.2"
    web_api_version = "2.9.3"


class FakeAPIError(Exception):
    """Stands in for qbittorrentapi.APIError."""


class FakeQbtClient:
    """Records calls instead of talking to a real qBittorrent instance."""

    def __init__(self, torrents=None, login_error=None, **kwargs):
        self.app = FakeApp()
        self._torrents = list(torrents or [])
        self._login_error = login_error
        self.init_kwargs = kwargs
        self.added_tags = []
        self.deleted_tags = []
        self.deleted = []
        self.logged_in = False

    def auth_log_in(self):
        if self._login_error is not None:
            raise self._login_error
        self.logged_in = True

    def torrents_info(self):
        return list(self._torrents)

    def torrents_add_tags(self, tags, torrent_hash):
        self.added_tags.append((tags, torrent_hash))

    def torrents_delete_tags(self, tags):
        self.deleted_tags.append(list(tags))

    def torrents_delete(self, delete_files, hashes):
        self.deleted.append((delete_files, list(hashes)))


def torrent(name="Example.Torrent.Release", tracker="https://tracker.example/announce",
            category="general", tags="", seeding_time=999999, state="uploading",
            ratio=2.0, time_active=999999, infohash="abc123", added_on=1):
    """Build a torrent dict shaped like a qbittorrentapi response."""
    return {
        "name": name,
        "tracker": tracker,
        "category": category,
        "tags": tags,
        "seeding_time": seeding_time,
        "state": state,
        "ratio": ratio,
        "time_active": time_active,
        "infohash_v1": infohash,
        "hash": infohash,
        "added_on": added_on,
    }


# ---------------------------------------------------------------------------
# Pushover stand-ins
# ---------------------------------------------------------------------------
class StubPushover:
    """Records message() calls instead of hitting the Pushover API."""

    def __init__(self):
        self.calls = []

    def message(self, user, body, **kwargs):
        self.calls.append({"user": user, "body": body, "kwargs": kwargs})


class FailingPushover:
    def message(self, *args, **kwargs):
        raise RuntimeError("pushover is down")


# ---------------------------------------------------------------------------
# The Qbt object
# ---------------------------------------------------------------------------
class FakeQbt:
    """Stand-in for the Qbt object.

    Defaults match the notifier tests (42 scanned, 7 removed, 4 orphaned).
    Pipeline tests override ``torrent_list`` and ``qbt_client``.
    """

    def __init__(self, **overrides):
        # --- notifier surface ---
        self.config = {"pushover": {}}
        self.total_torrents = 42
        self.torrent_hash_delete_list = ["a"] * 7
        self.up_tor_counter = 4
        self.ignored_counter = 5
        self.preme_tor_counter = 3
        self.tracker_protected_tag = "ipt"
        self.tracker_non_protected_tag = "public"
        self.c = Counter({"ipt": 10, "public": 20})
        self.delete_torrents = True
        self.st = datetime.datetime(2026, 10, 27, 9, 54, 0)
        self.et = datetime.datetime(2026, 10, 27, 9, 54, 12)
        self.po_key = "USERKEY"
        self.poc = StubPushover()
        self.apprise_host = "localhost"
        self.apprise_port = 8088
        self.apprise_aurls = "mailto://user:pass@example.com"
        self.tl = logging.getLogger("qbit-maid-test")

        # --- pipeline surface ---
        self.torrent_list = []
        self.tracker_list = []
        self.qbt_client = FakeQbtClient()
        self.cat_whitelist = {}
        self.tracker_whitelist = {"tracker.example": "tracker.example"}
        self.ignored_tags = {}
        self.min_age = 432000
        self.max_age = 2419200
        self.enable_telemetry = False
        self.telemetry_outfile = "telemetry.csv"
        self.enable_dragnet = False
        self.dragnet_outfile = "orphaned.csv"
        self.cv = None
        self.use_pushover = False
        self.use_apprise = False
        self.extm = ""

        for key, value in overrides.items():
            setattr(self, key, value)

    def reset_counters(self):
        """Zero the pipeline counters.

        The constructor defaults are the notifier fixture (42 scanned, 7
        removed, ...), which pipeline tests must not inherit.
        """
        self.up_tor_counter = 0
        self.preme_tor_counter = 0
        self.ignored_counter = 0
        self.torrent_hash_delete_list = []
        return self

import datetime
import unittest

from qbt_fakes import FailingPushover, FakeQbt, StubPushover
from qlist import (
    is_cat_ignored,
    is_ignored_tag,
    is_not_protected_tracker,
    is_preme,
    is_protected_tracker,
    is_tag_blank,
    is_tracker_blank,
)
from qlogging import (
    build_summary,
    format_runtime,
    get_notify_options,
    send_ping,
    summary_stats,
    tor_notify_apprise,
    tor_notify_summary,
)
from qprocess import (
    is_downloading,
    is_not_protected_tor,
    is_old_tor,
    is_protected_over_ratio,
    is_protected_under_ratio,
)


class RecordingRequests:
    """Stands in for the requests module without touching the network."""

    class RequestException(Exception):
        pass

    def __init__(self):
        self.calls = []
        self.timeouts = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        self.timeouts.append(timeout)
        return "ok"


class TestPredicates(unittest.TestCase):
    def test_is_preme(self):
        self.assertTrue(is_preme(1, 1))  # equal to min_age counts as premature
        self.assertTrue(is_preme(1, 2))
        self.assertFalse(is_preme(2, 1))

    def test_is_cat_ignored(self):
        cats = ["a", "b", "c"]
        for cat in cats:
            self.assertTrue(is_cat_ignored(cat, cats))
        self.assertFalse(is_cat_ignored("d", cats))
        self.assertFalse(is_cat_ignored(1, cats))
        self.assertFalse(is_cat_ignored(1.0, cats))

    def test_is_tracker_blank(self):
        self.assertTrue(is_tracker_blank(""))
        self.assertFalse(is_tracker_blank("a"))
        self.assertFalse(is_tracker_blank(1))
        self.assertFalse(is_tracker_blank(1.0))

    def test_is_protected_tracker(self):
        whitelist = ["a.com", "b.me", "c.io"]
        self.assertTrue(is_protected_tracker("https://a.com/", whitelist))
        self.assertFalse(is_protected_tracker("https://google.com/", whitelist))
        self.assertFalse(is_protected_tracker("https://d.com", whitelist))
        self.assertFalse(is_protected_tracker("", whitelist))

    def test_is_not_protected_tracker(self):
        whitelist = ["a.com", "b.me", "c.io"]
        self.assertFalse(is_not_protected_tracker("https://a.com/", whitelist))
        self.assertTrue(is_not_protected_tracker("https://google.com/", whitelist))
        self.assertTrue(is_not_protected_tracker("https://d.com", whitelist))
        self.assertFalse(is_not_protected_tracker("", whitelist))

    def test_is_tag_blank(self):
        self.assertTrue(is_tag_blank(""))
        for value in ("a", 1, 1.0001, False, True):
            self.assertFalse(is_tag_blank(value))

    def test_is_downloading(self):
        self.assertTrue(is_downloading("downloading"))
        self.assertFalse(is_downloading("DOWNLOADING"))
        self.assertFalse(is_downloading("dOwNlOaDiNg"))
        self.assertFalse(is_downloading("uploading"))

    def test_is_protected_under_ratio(self):
        self.assertTrue(is_protected_under_ratio(0.5, 1, "a", "a,b,c"))
        self.assertFalse(is_protected_under_ratio(1.5, 1, "a", "a,b,c"))
        self.assertFalse(is_protected_under_ratio(0.5, 1, "z", "a,b,c"))

    def test_is_old_tor(self):
        self.assertTrue(is_old_tor(1, 1))
        self.assertTrue(is_old_tor(2, 1))
        self.assertFalse(is_old_tor(1, 2))

    def test_is_protected_over_ratio(self):
        self.assertTrue(is_protected_over_ratio(2, 1, "a", "a,b,c"))
        self.assertFalse(is_protected_over_ratio(0.5, 1, "a", "a,b,c"))
        self.assertFalse(is_protected_over_ratio(2, 1, "z", "a,b,c"))

    def test_is_not_protected_tor(self):
        self.assertTrue(is_not_protected_tor("a", "a,b,c"))
        self.assertFalse(is_not_protected_tor("z", "a,b,c"))

    def test_is_ignored_tag(self):
        self.assertTrue(is_ignored_tag(["save"], "save,public,ipt"))
        self.assertFalse(is_ignored_tag(["save"], "public,ipt"))

    def test_is_ignored_tag_matches_whole_tags_only(self):
        """A configured tag must match a whole tag, not a substring of one.

        'ipt' must not match 'iptorrents' and 'save' must not match 'unsaved'.
        """
        self.assertFalse(is_ignored_tag(["ipt"], "iptorrents"))
        self.assertFalse(is_ignored_tag(["save"], "unsaved"))
        self.assertTrue(is_ignored_tag(["ipt"], "save,ipt"))
        self.assertTrue(is_ignored_tag(["save"], " save , public"))
        self.assertFalse(is_ignored_tag(["save"], ""))


class TestSendPing(unittest.TestCase):
    def test_send_ping_requests_the_url(self):
        req = RecordingRequests()
        send_ping(FakeQbt(), req, "https://example.com/ping/x")
        self.assertEqual(req.calls, ["https://example.com/ping/x"])

    def test_send_ping_uses_a_five_second_timeout(self):
        req = RecordingRequests()
        send_ping(FakeQbt(), req, "https://example.com/ping/x")
        self.assertEqual(req.timeouts, [5])


# --- notification formatting -----------------------------------------------

class TestFormatRuntime(unittest.TestCase):
    def test_format_runtime(self):
        self.assertEqual(format_runtime(datetime.timedelta(seconds=0)), "0s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=12)), "12s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=64)), "1m 04s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=3723)), "1h 02m 03s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=-5)), "0s")


class TestSummaryStats(unittest.TestCase):
    def test_summary_stats(self):
        stats = summary_stats(FakeQbt())
        self.assertEqual(stats["total"], 42)
        self.assertEqual(stats["removed"], 7)
        self.assertEqual(stats["orphaned"], 4)
        self.assertEqual(stats["ignored"], 5)
        self.assertEqual(stats["premature"], 3)
        self.assertEqual(stats["protected"], 10)
        self.assertEqual(stats["non_protected"], 20)
        self.assertEqual(stats["runtime"], "12s")

    def test_summary_stats_missing_attributes(self):
        class Bare:
            pass

        stats = summary_stats(Bare())
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["removed"], 0)
        self.assertEqual(stats["runtime"], "unknown")


class TestBuildSummary(unittest.TestCase):
    def test_build_summary_plain(self):
        title, body = build_summary(FakeQbt(), style="plain", use_emoji=False)
        self.assertEqual(title, "qbit-maid: 7 torrents removed")
        self.assertEqual(
            body,
            "Scanned 42 torrents in 12s\n"
            "\n"
            "7 removed  \u00b7  4 orphaned\n"
            "5 ignored  \u00b7  3 premature\n"
            "\n"
            "10 protected  \u00b7  20 public",
        )

    def test_build_summary_plain_emoji(self):
        _, body = build_summary(FakeQbt(), style="plain", use_emoji=True)
        self.assertEqual(
            body,
            "Scanned 42 torrents in 12s\n"
            "\n"
            "\U0001F5D1\uFE0F 7 removed  \u00b7  \U0001F47B 4 orphaned\n"
            "\u23ED\uFE0F 5 ignored  \u00b7  \U0001F423 3 premature\n"
            "\n"
            "\U0001F6E1\uFE0F 10 protected  \u00b7  \U0001F310 20 public",
        )

    def test_build_summary_plain_has_no_leading_indent(self):
        _, body = build_summary(FakeQbt(), style="plain")
        for line in body.splitlines():
            self.assertFalse(line.startswith(" "), f"unexpected indent: {line!r}")

    def test_build_summary_has_no_space_padding(self):
        """Pushover uses a proportional font, so padded columns never align."""
        for style in ("plain", "html"):
            for emoji in (False, True):
                _, body = build_summary(FakeQbt(), style=style, use_emoji=emoji)
                for line in body.splitlines():
                    stripped = line.replace("  \u00b7  ", "")
                    self.assertNotIn("   ", stripped,
                                     f"padded column in {style}/{emoji}: {line!r}")

    def test_build_summary_groups_two_counters_per_line(self):
        _, body = build_summary(FakeQbt(), style="plain")
        rows = [ln for ln in body.splitlines() if "\u00b7" in ln]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row.count("\u00b7"), 1, row)

    def test_build_summary_value_leads_label(self):
        """The number comes first so it is the first thing the eye lands on."""
        _, body = build_summary(FakeQbt(), style="plain", use_emoji=False)
        self.assertIn("7 removed", body)
        self.assertIn("20 public", body)
        self.assertNotIn("Removed 7", body)
        self.assertNotIn("Non-protected", body)

    def test_build_summary_html(self):
        title, body = build_summary(FakeQbt(), style="html")
        self.assertEqual(title, "qbit-maid: 7 torrents removed")
        self.assertIn("Scanned <b>42</b> torrents in <b>12s</b>", body)
        self.assertIn("<b>7</b> removed", body)
        self.assertIn("<b>20</b> public", body)
        self.assertNotIn("---", title)

    def test_build_summary_emoji(self):
        _, plain = build_summary(FakeQbt(), style="plain", use_emoji=True)
        self.assertIn("\U0001F5D1\uFE0F 7 removed", plain)
        self.assertIn("\U0001F47B 4 orphaned", plain)
        _, html = build_summary(FakeQbt(), style="html", use_emoji=True)
        self.assertIn("\U0001F5D1\uFE0F <b>7</b> removed", html)

    def test_build_summary_emoji_off_has_no_emoji(self):
        _, body = build_summary(FakeQbt(), style="plain", use_emoji=False)
        for marker in ("\U0001F5D1", "\U0001F47B", "\u23ED", "\U0001F423",
                       "\U0001F6E1", "\U0001F310"):
            self.assertNotIn(marker, body)

    def test_build_summary_delete_disabled(self):
        title, body = build_summary(FakeQbt(delete_torrents=False))
        self.assertEqual(title, "qbit-maid: 7 torrents would be removed")
        self.assertIn("7 would be removed", body)
        self.assertNotIn("7 removed", body)

    def test_build_summary_body_does_not_repeat_title_phrase(self):
        """The title carries the outcome; the body must not restate it verbatim."""
        title, body = build_summary(FakeQbt(), style="plain", use_emoji=False)
        self.assertNotIn("torrents removed", body)
        self.assertNotIn("torrents would be removed", body)
        self.assertIn("7 removed", body)
        self.assertTrue(title.endswith("7 torrents removed"))

    def test_build_summary_nothing_to_do(self):
        title, _ = build_summary(FakeQbt(torrent_hash_delete_list=[], up_tor_counter=0))
        self.assertEqual(title, "qbit-maid: nothing removed")
        title, _ = build_summary(
            FakeQbt(torrent_hash_delete_list=[], up_tor_counter=0, delete_torrents=False)
        )
        self.assertEqual(title, "qbit-maid: nothing to remove")

    def test_build_summary_singular(self):
        title, _ = build_summary(FakeQbt(torrent_hash_delete_list=["a"], total_torrents=1))
        self.assertEqual(title, "qbit-maid: 1 torrent removed")

    def test_build_summary_hostname(self):
        _, body = build_summary(FakeQbt(), include_hostname=True)
        self.assertTrue(body.startswith("Host: "))

    def test_build_summary_hostname_html(self):
        _, body = build_summary(FakeQbt(), style="html", include_hostname=True)
        self.assertTrue(body.startswith("<b>Host:</b> "))

    def test_build_summary_unknown_style_falls_back(self):
        _, body = build_summary(FakeQbt(), style="markdown")
        self.assertNotIn("<b>", body)


class TestNotifyOptions(unittest.TestCase):
    def test_get_notify_options_defaults(self):
        opts = get_notify_options(FakeQbt())
        self.assertEqual(opts["style"], "plain")
        self.assertTrue(opts["use_emoji"])
        self.assertFalse(opts["include_hostname"])
        self.assertTrue(opts["notify_on_empty"])
        self.assertIsNone(opts["priority"])
        self.assertIsNone(opts["sound"])

    def test_get_notify_options_emoji_can_be_disabled(self):
        opts = get_notify_options(FakeQbt(config={"pushover": {"use_emoji": False}}))
        self.assertFalse(opts["use_emoji"])

    def test_get_notify_options_overrides(self):
        fake = FakeQbt(config={"pushover": {
            "format": "HTML",
            "use_emoji": False,
            "include_hostname": True,
            "notify_on_empty": False,
            "priority": 2,
            "sound": "siren",
            "retry": 30,
            "expire": 600,
        }})
        opts = get_notify_options(fake)
        self.assertEqual(opts["style"], "html")
        self.assertFalse(opts["use_emoji"])
        self.assertTrue(opts["include_hostname"])
        self.assertFalse(opts["notify_on_empty"])
        self.assertEqual(opts["priority"], 2)
        self.assertEqual(opts["sound"], "siren")
        self.assertEqual(opts["retry"], 30)
        self.assertEqual(opts["expire"], 600)

    def test_get_notify_options_invalid_style(self):
        fake = FakeQbt(config={"pushover": {"format": "bogus"}})
        self.assertEqual(get_notify_options(fake)["style"], "plain")


class TestTorNotifySummary(unittest.TestCase):
    def test_tor_notify_summary_plain_payload(self):
        fake = FakeQbt()
        tor_notify_summary(fake)
        self.assertEqual(len(fake.poc.calls), 1)
        call = fake.poc.calls[0]
        self.assertEqual(call["user"], "USERKEY")
        self.assertEqual(call["kwargs"]["title"], "qbit-maid: 7 torrents removed")
        self.assertNotIn("html", call["kwargs"])

    def test_tor_notify_summary_html_payload(self):
        fake = FakeQbt(config={"pushover": {"format": "html"}})
        tor_notify_summary(fake)
        call = fake.poc.calls[0]
        self.assertEqual(call["kwargs"]["html"], 1)
        self.assertIn("<b>", call["body"])

    def test_tor_notify_summary_priority_two_adds_retry_expire(self):
        fake = FakeQbt(config={"pushover": {"priority": 2, "retry": 30, "expire": 600}})
        tor_notify_summary(fake)
        kwargs = fake.poc.calls[0]["kwargs"]
        self.assertEqual(kwargs["priority"], 2)
        self.assertEqual(kwargs["retry"], 30)
        self.assertEqual(kwargs["expire"], 600)

    def test_tor_notify_summary_priority_one_has_no_retry(self):
        fake = FakeQbt(config={"pushover": {"priority": 1}})
        tor_notify_summary(fake)
        kwargs = fake.poc.calls[0]["kwargs"]
        self.assertEqual(kwargs["priority"], 1)
        self.assertNotIn("retry", kwargs)

    def test_tor_notify_summary_skips_when_empty(self):
        fake = FakeQbt(
            config={"pushover": {"notify_on_empty": False}},
            torrent_hash_delete_list=[],
            up_tor_counter=0,
        )
        tor_notify_summary(fake)
        self.assertEqual(fake.poc.calls, [])

    def test_tor_notify_summary_sends_when_empty_by_default(self):
        fake = FakeQbt(torrent_hash_delete_list=[], up_tor_counter=0)
        tor_notify_summary(fake)
        self.assertEqual(len(fake.poc.calls), 1)

    def test_tor_notify_summary_swallows_send_errors(self):
        fake = FakeQbt()
        fake.poc = FailingPushover()
        tor_notify_summary(fake)  # must not raise


class TestTorNotifyApprise(unittest.TestCase):
    def test_tor_notify_apprise_uses_plain_body(self):
        captured = {}

        def app_obj(req_obj, host, port, aurls, title, body):
            captured.update(host=host, port=port, aurls=aurls, title=title, body=body)

        fake = FakeQbt(config={"pushover": {"format": "html"}})
        tor_notify_apprise(fake, None, app_obj)
        self.assertEqual(captured["title"], "qbit-maid: 7 torrents removed")
        self.assertNotIn("<b>", captured["body"])
        self.assertEqual(captured["port"], 8088)

    def test_pushover_and_apprise_bodies_match(self):
        fake = FakeQbt()
        tor_notify_summary(fake)
        captured = {}
        tor_notify_apprise(
            fake, None,
            lambda req, host, port, aurls, title, body: captured.update(title=title, body=body),
        )
        self.assertEqual(fake.poc.calls[0]["body"], captured["body"])
        self.assertEqual(fake.poc.calls[0]["kwargs"]["title"], captured["title"])


if __name__ == "__main__":
    unittest.main()

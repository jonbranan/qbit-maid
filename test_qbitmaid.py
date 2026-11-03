import datetime
import logging
import unittest
from collections import Counter

import requests as r
from qlist import is_preme,is_cat_ignored,is_tracker_blank,is_protected_tracker,is_not_protected_tracker,is_tag_blank,is_ignored_tag
from qprocess import is_downloading,is_protected_under_ratio,is_old_tor,is_protected_over_ratio,is_not_protected_tor
from qlogging import (
    send_ping,
    build_summary,
    format_runtime,
    get_notify_options,
    summary_stats,
    tor_notify_apprise,
    tor_notify_summary,
)


class FakeQbt:
    """Minimal stand-in for the Qbt object, holding only what notifiers read."""

    def __init__(self, **overrides):
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
        for key, value in overrides.items():
            setattr(self, key, value)


class StubPushover:
    """Records message() calls instead of hitting the Pushover API."""

    def __init__(self):
        self.calls = []

    def message(self, user, body, **kwargs):
        self.calls.append({"user": user, "body": body, "kwargs": kwargs})


class FailingPushover:
    def message(self, *args, **kwargs):
        raise RuntimeError("pushover is down")

class TestQbitmaid(unittest.TestCase):
    def test_ispreme_sanity(self):
        self.assertTrue(is_preme(1,1))
        self.assertTrue(is_preme(1,2))
        self.assertFalse(is_preme(2,1))
    
    def test_ispreme(self):
        pass

    def test_iscatignored_sanity(self):
        self.assertTrue(is_cat_ignored('a', ['a','b','c']))
        self.assertTrue(is_cat_ignored('b', ['a','b','c']))
        self.assertTrue(is_cat_ignored('c', ['a','b','c']))
        self.assertFalse(is_cat_ignored('d', ['a','b','c']))
        self.assertFalse(is_cat_ignored(1, ['a','b','d']))
        self.assertFalse(is_cat_ignored(1.0000000, ['a','b','c']))

    def test_iscatignored(self):
        pass

    def test_istrackerblank_sanity(self):
        self.assertTrue(is_tracker_blank(''))
        self.assertFalse(is_tracker_blank('a'))
        self.assertFalse(is_tracker_blank(1))
        self.assertFalse(is_tracker_blank(1.00000000))

    def test_istrackerblank(self):
        pass

    def test_isprotectedtracker_sanity(self):
        self.assertTrue(is_protected_tracker('https://a.com/',['a.com','b.me','c.io']))
        self.assertFalse(is_protected_tracker('https://google.com/',['a.com','b.me','c.io']))
        self.assertFalse(is_protected_tracker('https://d.com',['a.com','b.me','c.io']))

    def test_isprotectedtracker(self):
        pass

    def test_isnotprotectedtracker_sanity(self):
        self.assertFalse(is_not_protected_tracker('https://a.com/',['a.com','b.me','c.io']))
        self.assertTrue(is_not_protected_tracker('https://google.com/',['a.com','b.me','c.io']))
        self.assertTrue(is_not_protected_tracker('https://d.com',['a.com','b.me','c.io']))

    def test_isnotprotectedtracker(self):
        pass

    def test_istagblank(self):
        self.assertTrue(is_tag_blank(''))
        self.assertFalse(is_tag_blank('a'))
        self.assertFalse(is_tag_blank(1))
        self.assertFalse(is_tag_blank(1.0001))
        self.assertFalse(is_tag_blank(False))
        self.assertFalse(is_tag_blank(True))

    def test_isdownloading_sanity(self):
        self.assertTrue(is_downloading('downloading'))
    
    def test_isdownloading(self):
        self.assertFalse(is_downloading('DOWNLOADING'))
        self.assertFalse(is_downloading('dOwNlOaDiNg'))

    def test_isprotectedunderratio_sanity(self):
        self.assertTrue(is_protected_under_ratio(0.5,1,'a','a,b,c'))

    def test_isprotectedunderratio(self):
        pass

    def test_isoldtor_sanity(self):
        self.assertFalse(is_old_tor(1,2))

    def test_isoldtor(self):
        self.assertTrue(is_old_tor(1,1))
        self.assertTrue(is_old_tor(2,1))
        self.assertFalse(is_old_tor(1,2))

    def test_isprotectedoverratio_sanity(self):
        self.assertTrue(is_protected_over_ratio(2,1,'a','a,b,c'))

    def test_isprotectedoverratio(self):
        pass

    def test_isnonprotectedtor_sanity(self):
        self.assertTrue(is_not_protected_tor('a','a,b,c'))

    def test_isnonprotectedtor(self):
        pass

    def test_isignoredtag_sanity(self):
        self.assertTrue(is_ignored_tag(['a','b','c'], 'first,second,third,a'))
    
    def test_isignoredtag(self):
        self.assertTrue(is_ignored_tag(['save'], 'save,public,ipt'))

    def test_sendpingstart_sanity(self):
        send_ping(self, r, "https://thunder.jonb.io/ping/921625e5-5b76-4f45-a0c3-56145e16f3bb" + "/start")
        url = "https://thunder.jonb.io/ping/921625e5-5b76-4f45-a0c3-56145e16f3bb"
        send_ping(self, r, url)

    def test_sendping_start(self):
        url = "https://thunder.jonb.io/ping/921625e5-5b76-4f45-a0c3-56145e16f3bb/"
        send_ping(self, r, url.strip("/") + "/start")
        send_ping(self, r, "https://thunder.jonb.io/ping/921625e5-5b76-4f45-a0c3-56145e16f3bb")
        

    # --- notification formatting -------------------------------------------

    def test_format_runtime(self):
        self.assertEqual(format_runtime(datetime.timedelta(seconds=0)), "0s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=12)), "12s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=64)), "1m 04s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=3723)), "1h 02m 03s")
        self.assertEqual(format_runtime(datetime.timedelta(seconds=-5)), "0s")

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

    def test_build_summary_unknown_style_falls_back(self):
        _, body = build_summary(FakeQbt(), style="markdown")
        self.assertNotIn("<b>", body)

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

    # def test__sanity(self):
    #     pass

    # def test_(self):
    #     pass
        
if __name__ == '__main__':
    unittest.main()

"""Tests for qlist.build_tor_list — the tagging and sorting pass."""
import unittest

from qbt_fakes import FakeQbt, torrent
from qlist import build_tor_list


class TestBuildTorList(unittest.TestCase):
    def run_build(self, torrents, **overrides):
        qbt = FakeQbt(torrent_list=list(torrents), **overrides).reset_counters()
        build_tor_list(qbt)
        return qbt

    def test_sets_total_torrents(self):
        qbt = self.run_build([torrent(infohash="a"), torrent(infohash="b")])
        self.assertEqual(qbt.total_torrents, 2)

    def test_blank_tracker_is_ignored(self):
        qbt = self.run_build([torrent(tracker="")])
        self.assertEqual(qbt.ignored_counter, 1)
        self.assertEqual(qbt.tracker_list, [])

    def test_ignored_category_is_ignored(self):
        qbt = self.run_build(
            [torrent(category="tech")],
            cat_whitelist={"tech": "tech"},
        )
        self.assertEqual(qbt.ignored_counter, 1)
        self.assertEqual(qbt.tracker_list, [])

    def test_ignored_tag_is_ignored(self):
        qbt = self.run_build(
            [torrent(tags="save,public")],
            ignored_tags={"save": "save"},
        )
        self.assertEqual(qbt.ignored_counter, 1)
        self.assertEqual(qbt.tracker_list, [])

    def test_blank_tag_on_protected_tracker_gets_protected_tag(self):
        qbt = self.run_build([torrent(tags="", infohash="h1")])
        self.assertIn(("ipt", "h1"), qbt.qbt_client.added_tags)
        self.assertEqual(len(qbt.tracker_list), 1)

    def test_blank_tag_on_non_protected_tracker_gets_public_tag(self):
        qbt = self.run_build(
            [torrent(tags="", tracker="https://other.example/announce", infohash="h2")]
        )
        self.assertIn(("public", "h2"), qbt.qbt_client.added_tags)
        self.assertEqual(len(qbt.tracker_list), 1)

    def test_blank_tag_is_applied_twice_for_non_premature_torrents(self):
        """KNOWN REDUNDANCY: the tagging block runs twice for the same torrent.

        Lines 24-29 tag any blank-tag torrent; lines 34-43 tag it again inside
        the tracker branch. qBittorrent treats the second call as a no-op, so
        the outcome is correct but one API call per new torrent is wasted.
        Pinned here so the duplication is visible rather than silent.
        """
        qbt = self.run_build([torrent(tags="", infohash="h1")])
        self.assertEqual(qbt.qbt_client.added_tags, [("ipt", "h1"), ("ipt", "h1")])

    def test_premature_blank_tag_torrent_is_tagged_once(self):
        """Premature torrents are tagged by the first block, then skipped."""
        qbt = self.run_build([torrent(tags="", seeding_time=1, infohash="h3")])
        self.assertEqual(qbt.qbt_client.added_tags, [("ipt", "h3")])
        self.assertEqual(qbt.preme_tor_counter, 1)
        self.assertEqual(qbt.tracker_list, [])

    def test_premature_torrent_is_counted_and_not_queued(self):
        qbt = self.run_build([torrent(seeding_time=10, tags="ipt")])
        self.assertEqual(qbt.preme_tor_counter, 1)
        self.assertEqual(qbt.tracker_list, [])

    def test_protected_torrent_with_tag_is_queued_without_retagging(self):
        qbt = self.run_build([torrent(tags="ipt")])
        self.assertEqual(qbt.qbt_client.added_tags, [])
        self.assertEqual(len(qbt.tracker_list), 1)

    def test_non_protected_torrent_with_tag_is_queued_without_retagging(self):
        qbt = self.run_build(
            [torrent(tags="public", tracker="https://other.example/announce")]
        )
        self.assertEqual(qbt.qbt_client.added_tags, [])
        self.assertEqual(len(qbt.tracker_list), 1)

    def test_mixed_batch_counts_each_bucket(self):
        qbt = self.run_build([
            torrent(tracker=""),                                   # ignored
            torrent(category="tech"),                              # ignored
            torrent(tags="save"),                                  # ignored
            torrent(seeding_time=1, tags="ipt"),                   # premature
            torrent(tags="ipt", infohash="p1"),                    # queued
            torrent(tags="public", tracker="https://o.example/a",
                    infohash="n1"),                                # queued
        ], cat_whitelist={"tech": "tech"}, ignored_tags={"save": "save"})
        self.assertEqual(qbt.ignored_counter, 3)
        self.assertEqual(qbt.preme_tor_counter, 1)
        self.assertEqual(len(qbt.tracker_list), 2)
        self.assertEqual(qbt.total_torrents, 6)

    def test_consumes_the_input_list(self):
        qbt = self.run_build([torrent(tags="ipt")])
        self.assertEqual(qbt.torrent_list, [])


if __name__ == "__main__":
    unittest.main()

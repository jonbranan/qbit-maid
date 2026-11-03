"""Tests for qprocess — the deletion decision pass and the delete calls."""
import csv
import os
import shutil
import tempfile
import unittest

from qbt_fakes import FakeQbt, torrent
from qprocess import tor_delete, tor_delete_tags, tor_processor


class TestTorProcessor(unittest.TestCase):
    def run_processor(self, candidates, **overrides):
        qbt = FakeQbt(tracker_list=list(candidates), cv=csv, **overrides).reset_counters()
        tor_processor(qbt)
        return qbt

    def test_downloading_torrent_is_skipped(self):
        qbt = self.run_processor([torrent(state="downloading", tags="public")])
        self.assertEqual(qbt.torrent_hash_delete_list, [])
        self.assertEqual(qbt.up_tor_counter, 0)

    def test_protected_under_ratio_and_old_is_deleted(self):
        qbt = self.run_processor([
            torrent(tags="ipt", ratio=0.5, time_active=9999999, infohash="old1"),
        ])
        self.assertEqual(qbt.torrent_hash_delete_list, ["old1"])

    def test_protected_under_ratio_but_young_is_kept(self):
        qbt = self.run_processor([
            torrent(tags="ipt", ratio=0.5, time_active=1, infohash="young1"),
        ])
        self.assertEqual(qbt.torrent_hash_delete_list, [])
        self.assertEqual(qbt.up_tor_counter, 0)

    def test_protected_over_ratio_is_deleted(self):
        qbt = self.run_processor([
            torrent(tags="ipt", ratio=2.0, infohash="over1"),
        ])
        self.assertEqual(qbt.torrent_hash_delete_list, ["over1"])

    def test_non_protected_is_deleted(self):
        qbt = self.run_processor([
            torrent(tags="public", ratio=0.1, infohash="np1"),
        ])
        self.assertEqual(qbt.torrent_hash_delete_list, ["np1"])

    def test_unmatched_torrent_is_orphaned(self):
        qbt = self.run_processor([torrent(tags="other", ratio=0.1)])
        self.assertEqual(qbt.torrent_hash_delete_list, [])
        self.assertEqual(qbt.up_tor_counter, 1)

    def test_telemetry_writes_a_row_per_candidate(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        outfile = os.path.join(tmp, "telemetry.csv")
        qbt = self.run_processor(
            [torrent(tags="public", infohash="t1"), torrent(tags="public", infohash="t2")],
            enable_telemetry=True,
            telemetry_outfile=outfile,
        )
        with open(outfile, newline="", encoding="UTF8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["state", "ratio", "tags", "added", "hash", "name", "tracker"])
        self.assertEqual(len(rows), 3)  # header + 2 candidates
        self.assertEqual(qbt.torrent_hash_delete_list, ["t1", "t2"])

    def test_dragnet_writes_orphans_only(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        outfile = os.path.join(tmp, "orphaned.csv")
        qbt = self.run_processor(
            [torrent(tags="other", infohash="orph1"), torrent(tags="public", infohash="del1")],
            enable_dragnet=True,
            dragnet_outfile=outfile,
        )
        with open(outfile, newline="", encoding="UTF8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["state", "ratio", "tags", "added", "thash", "tname", "trname"])
        self.assertEqual(len(rows), 2)  # header + the single orphan
        self.assertEqual(rows[1][4], "orph1")
        self.assertEqual(qbt.up_tor_counter, 1)


class TestDeleteCalls(unittest.TestCase):
    def test_delete_tags_removes_both_tags(self):
        qbt = FakeQbt()
        tor_delete_tags(qbt)
        self.assertEqual(qbt.qbt_client.deleted_tags, [["ipt", "public"]])

    def test_delete_removes_files_for_each_hash(self):
        qbt = FakeQbt(torrent_hash_delete_list=["h1", "h2"])
        tor_delete(qbt)
        self.assertEqual(qbt.qbt_client.deleted, [(True, ["h1", "h2"])])

    def test_delete_is_a_noop_on_empty_list(self):
        qbt = FakeQbt(torrent_hash_delete_list=[])
        tor_delete(qbt)
        self.assertEqual(qbt.qbt_client.deleted, [])


if __name__ == "__main__":
    unittest.main()

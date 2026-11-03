"""Tests for qprocess.write_csv — header-once, append semantics."""
import csv
import os
import shutil
import tempfile
import unittest

from qprocess import write_csv

HEADER = ["state", "ratio", "tags", "added", "hash", "name", "tracker"]
ROW = ["downloading", 1.05, "ipt", 1, "asfasdf23412adfqwer",
       "thisismynamehahahah", "https://localhost.stackoverflow.tech/announce"]


class TestWriteCSV(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.outfile = os.path.join(self.tmp, "out.csv")

    def read_rows(self):
        with open(self.outfile, newline="", encoding="UTF8") as fh:
            return list(csv.reader(fh))

    def test_writes_header_then_row(self):
        write_csv(csv, self.outfile, HEADER, ROW)
        rows = self.read_rows()
        self.assertEqual(rows[0], HEADER)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][4], "asfasdf23412adfqwer")

    def test_header_is_written_only_once(self):
        write_csv(csv, self.outfile, HEADER, ROW)
        write_csv(csv, self.outfile, HEADER, ROW)
        rows = self.read_rows()
        self.assertEqual(rows.count(HEADER), 1)
        self.assertEqual(len(rows), 3)

    def test_creates_the_file_when_missing(self):
        self.assertFalse(os.path.exists(self.outfile))
        write_csv(csv, self.outfile, HEADER, ROW)
        self.assertTrue(os.path.exists(self.outfile))

    def test_values_are_round_tripped(self):
        write_csv(csv, self.outfile, HEADER, ROW)
        self.assertEqual(self.read_rows()[1], [str(value) for value in ROW])


if __name__ == "__main__":
    unittest.main()

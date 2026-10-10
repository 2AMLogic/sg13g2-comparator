"""Negative controls for scripts/check_signoff_report.py (issue #117).

A fake `klt` (a throwaway script printing canned JSON) stands in for the
real tool; stdlib only, no network.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "check_signoff_report.py"
spec = importlib.util.spec_from_file_location("check_signoff_report", SCRIPT)
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

COMMITTED = {
    "tier": "none",
    "t1_met_count": 1,
    "t1_item_count": 2,
    "build": {"version": "0.6.0+gaaaa", "dirty": False},
    "items": [
        {"id": 1, "status": "met"},
        {"id": 2, "status": "unmet"},
    ],
}


def _copy(obj):
    return json.loads(json.dumps(obj))


class ParityBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.manifest = self.tmp / "manifest.json"
        self.manifest.write_text("{}")
        self.report = self.tmp / "report.json"
        self.write_report(COMMITTED)

    def write_report(self, obj):
        self.report.write_text(json.dumps(obj))

    def fake_klt(self, body, code=0, raw=False):
        payload = self.tmp / "payload.txt"
        payload.write_text(body if raw else json.dumps(body))
        klt = self.tmp / "klt"
        klt.write_text(
            f"#!{sys.executable}\n"
            "import sys\n"
            f"sys.stdout.write(open({str(payload)!r}).read())\n"
            f"sys.exit({code})\n"
        )
        klt.chmod(0o755)
        return str(klt)

    def run_main(self, klt=None, manifest=None, report=None):
        argv = [
            "check_signoff_report.py",
            "--manifest", str(manifest or self.manifest),
            "--report", str(report or self.report),
            "--klt", klt or "klt-not-used",
        ]
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main()
        return rc, out.getvalue(), err.getvalue()


class TestParity(ParityBase):
    def test_accepted_exits_constant(self):
        self.assertEqual(chk._ACCEPTED_EXITS, (0, 3))

    def test_equal_exit_0_and_3_pass(self):
        for code in (0, 3):
            with self.subTest(code=code):
                rc, out, err = self.run_main(self.fake_klt(COMMITTED, code))
                self.assertEqual(rc, 0, err)
                self.assertIn("OK:", out)

    def test_error_exits_fail(self):
        for code in (1, 2):
            with self.subTest(code=code):
                rc, _, err = self.run_main(self.fake_klt(COMMITTED, code))
                self.assertEqual(rc, 1)
                self.assertIn("klt signoff exited", err)

    def test_non_json_stdout_fails(self):
        rc, _, err = self.run_main(self.fake_klt("not json {", raw=True))
        self.assertEqual(rc, 1)
        self.assertIn("not valid JSON", err)

    def test_mutated_leaf_names_path_and_values(self):
        fresh = _copy(COMMITTED)
        fresh["items"][0]["status"] = "unmet"
        rc, _, err = self.run_main(self.fake_klt(fresh, 3))
        self.assertEqual(rc, 1)
        self.assertIn(".items[0].status", err)
        self.assertIn('committed "met"', err)
        self.assertIn('fresh "unmet"', err)

    def test_extra_key_in_fresh_fails(self):
        fresh = _copy(COMMITTED)
        fresh["surprise"] = 1
        rc, _, err = self.run_main(self.fake_klt(fresh, 3))
        self.assertEqual(rc, 1)
        self.assertIn("<absent in committed>", err)

    def test_missing_key_in_fresh_fails(self):
        fresh = _copy(COMMITTED)
        del fresh["items"][1]
        rc, _, err = self.run_main(self.fake_klt(fresh, 3))
        self.assertEqual(rc, 1)
        self.assertIn("<absent in fresh>", err)

    def test_build_version_mismatch_adds_note(self):
        fresh = _copy(COMMITTED)
        fresh["build"]["version"] = "0.7.0+gbbbb"
        rc, _, err = self.run_main(self.fake_klt(fresh, 3))
        self.assertEqual(rc, 1)
        self.assertIn("note: fresh build", err)
        self.assertIn("0.7.0+gbbbb", err)
        self.assertIn("vs frozen", err)

    def test_no_note_when_build_version_same(self):
        fresh = _copy(COMMITTED)
        fresh["items"][0]["status"] = "unmet"
        rc, _, err = self.run_main(self.fake_klt(fresh, 3))
        self.assertEqual(rc, 1)
        self.assertNotIn("note: fresh build", err)

    def test_missing_manifest_fails(self):
        rc, _, err = self.run_main(self.fake_klt(COMMITTED),
                                   manifest=self.tmp / "nope.json")
        self.assertEqual(rc, 1)
        self.assertIn("does not exist", err)

    def test_missing_report_fails(self):
        rc, _, err = self.run_main(self.fake_klt(COMMITTED),
                                   report=self.tmp / "nope.json")
        self.assertEqual(rc, 1)
        self.assertIn("does not exist", err)


class TestHelpers(unittest.TestCase):
    def test_flatten_nested(self):
        got = dict(chk._flatten({"b": [1, {"c": 2}], "a": 3}))
        self.assertEqual(got, {".a": 3, ".b[0]": 1, ".b[1].c": 2})

    def test_flatten_key_order_sorted(self):
        keys = [k for k, _ in chk._flatten({"z": 1, "a": 2})]
        self.assertEqual(keys, [".a", ".z"])

    def test_first_differences_none_when_equal(self):
        self.assertEqual(chk._first_differences(COMMITTED, _copy(COMMITTED)), [])

    def test_first_differences_limit_and_order(self):
        committed = {f"k{i}": 0 for i in range(10)}
        fresh = {f"k{i}": 1 for i in range(10)}
        diffs = chk._first_differences(fresh, committed, limit=3)
        self.assertEqual([d[0] for d in diffs], [".k0", ".k1", ".k2"])
        self.assertEqual(diffs[0], (".k0", 0, 1))
        self.assertEqual(len(chk._first_differences(fresh, committed)), 5)


if __name__ == "__main__":
    unittest.main()

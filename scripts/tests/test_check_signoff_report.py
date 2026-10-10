"""Negative controls for scripts/check_signoff_report.py (issue #117).

A fake `klt` (a throwaway script printing canned JSON) stands in for the
real tool; stdlib only, no network.
"""

import contextlib
import importlib.util
import io
import json
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
        self.assertIn("not a valid JSON report object", err)

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


class TestStructure(ParityBase):
    def fail_with(self, fresh, committed=None, code=3):
        if committed is not None:
            self.write_report(committed)
        rc, _, err = self.run_main(self.fake_klt(fresh, code))
        self.assertEqual(rc, 1, err)
        return err

    def test_reordered_object_keys_pass(self):
        fresh = {
            "items": COMMITTED["items"],
            "build": {"dirty": False, "version": "0.6.0+gaaaa"},
            "t1_item_count": 2, "t1_met_count": 1, "tier": "none",
        }
        for code in (0, 3):
            rc, _, err = self.run_main(self.fake_klt(fresh, code))
            self.assertEqual(rc, 0, err)

    def test_int_float_equivalence(self):
        fresh = _copy(COMMITTED)
        fresh["t1_met_count"] = 1.0
        rc, _, err = self.run_main(self.fake_klt(fresh, 3))
        self.assertEqual(rc, 0, err)

    def test_added_empty_field_fails(self):
        for empty in ({}, []):
            fresh = _copy(COMMITTED)
            fresh["extra"] = empty
            err = self.fail_with(fresh, COMMITTED)
            self.assertIn(".extra", err)
            self.assertIn("<absent in committed>", err)

    def test_removed_empty_field_fails(self):
        committed = _copy(COMMITTED)
        committed["extra"] = []
        err = self.fail_with(COMMITTED, committed)
        self.assertIn(".extra", err)
        self.assertIn("<absent in fresh>", err)

    def test_empty_object_vs_array_fails(self):
        committed = _copy(COMMITTED)
        committed["extra"] = []
        fresh = _copy(COMMITTED)
        fresh["extra"] = {}
        err = self.fail_with(fresh, committed)
        self.assertIn(".extra", err)

    def test_empty_object_vs_array_nested_in_array_fails(self):
        committed = _copy(COMMITTED)
        committed["items"][1]["notes"] = [[]]
        fresh = _copy(COMMITTED)
        fresh["items"][1]["notes"] = [{}]
        err = self.fail_with(fresh, committed)
        self.assertIn(".items[1].notes[0]", err)

    def test_bool_vs_number_fails(self):
        for a, b in ((True, 1), (False, 0), (1, True)):
            committed = _copy(COMMITTED)
            committed["flag"] = a
            fresh = _copy(COMMITTED)
            fresh["flag"] = b
            err = self.fail_with(fresh, committed)
            self.assertIn(".flag", err)

    def test_array_length_mismatch_reported(self):
        fresh = _copy(COMMITTED)
        fresh["items"].append({"id": 3, "status": "met"})
        err = self.fail_with(fresh)
        self.assertIn(".items.length", err)
        self.assertIn(".items[2]", err)

    def test_array_order_matters(self):
        fresh = _copy(COMMITTED)
        fresh["items"].reverse()
        self.fail_with(fresh)

    def test_nan_in_fresh_fails_controlled(self):
        body = json.dumps(COMMITTED).replace('"none"', "NaN")
        rc, _, err = self.run_main(self.fake_klt(body, 3, raw=True))
        self.assertEqual(rc, 1)
        self.assertIn("NaN", err)

    def test_infinity_in_committed_fails_controlled(self):
        self.report.write_text(json.dumps(COMMITTED).replace('"none"', "Infinity"))
        rc, _, err = self.run_main(self.fake_klt(COMMITTED, 3))
        self.assertEqual(rc, 1)
        self.assertIn("Infinity", err)

    def test_non_object_roots_fail(self):
        rc, _, err = self.run_main(self.fake_klt([], 3, raw=False))
        self.assertEqual(rc, 1)
        self.assertIn("root must be a JSON object", err)
        self.write_report([])
        rc, _, err = self.run_main(self.fake_klt(COMMITTED, 3))
        self.assertEqual(rc, 1)
        self.assertIn("root must be a JSON object", err)

    def test_malformed_committed_report_fails_controlled(self):
        self.report.write_text("{oops")
        rc, _, err = self.run_main(self.fake_klt(COMMITTED, 3))
        self.assertEqual(rc, 1)
        self.assertIn("committed report", err)


class TestHelpers(unittest.TestCase):
    def test_first_differences_none_when_equal(self):
        self.assertEqual(chk._first_differences(COMMITTED, _copy(COMMITTED)), [])

    def test_first_differences_limit_and_order(self):
        committed = {f"k{i}": 0 for i in range(10)}
        fresh = {f"k{i}": 1 for i in range(10)}
        diffs = chk._first_differences(fresh, committed, limit=3)
        self.assertEqual([d[0] for d in diffs], [".k0", ".k1", ".k2"])
        self.assertEqual(diffs[0], (".k0", 0, 1))
        self.assertEqual(len(chk._first_differences(fresh, committed)), 5)

    def test_type_mismatch_reported_before_scalars(self):
        diffs = chk._first_differences({"a": {}}, {"a": []})
        self.assertEqual(diffs, [(".a", [], {})])


if __name__ == "__main__":
    unittest.main()

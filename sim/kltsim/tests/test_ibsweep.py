"""Regression tests for the issue #80 bias-point sweep helpers (stdlib only)."""

from __future__ import annotations

import unittest
from pathlib import Path

from kltsim import build, ibsweep
from kltsim.benches import REGENERATION


class OverrideTests(unittest.TestCase):
    def body(self, **kw):
        return build.compose_body(REGENERATION, build.BATCH_OSDI_DIR, **kw)

    def test_default_body_uses_dut_json(self):
        self.assertIn(".param dut_ib=2e-05", self.body())
        self.assertNotIn("OVERRIDE", self.body())

    def test_override_changes_param_and_is_stated(self):
        text = self.body(param_overrides={"dut_ib": 5e-6})
        self.assertIn(".param dut_ib=5e-06", text)
        self.assertNotIn(".param dut_ib=2e-05", text)
        self.assertIn("OVERRIDE (issue #80 sweep; sim/dut.json untouched): dut_ib=5e-06", text)
        # the embedded DUT is untouched
        self.assertEqual(build.extract_dut_block(text)[1], build.extract_dut_block(self.body())[1])

    def test_unknown_override_refused(self):
        with self.assertRaises(build.BuildError):
            self.body(param_overrides={"not_a_param": 1.0})

    def test_dut_json_default_unchanged(self):
        self.assertEqual(build.load_dut_binding()["params"]["dut_ib"], 2e-05)


class FlagTests(unittest.TestCase):
    def point(self, **mirror):
        base = {"points": 45, "weak_inversion_points": 0, "tail_near_triode_points": 0,
                "tail_ref_vds_mismatch_points": 0}
        base.update(mirror)
        return {"mirror": base}

    def test_clean_point_has_no_flag(self):
        self.assertEqual(ibsweep.flags(self.point()), [])

    def test_weak_inversion_is_a_note_not_a_flag(self):
        p = self.point(weak_inversion_points=10)
        self.assertEqual(ibsweep.flags(p), [])
        self.assertEqual(len(ibsweep.notes(p)), 1)

    def test_triode_and_ratio_flags(self):
        p = self.point(tail_near_triode_points=3, tail_ref_vds_mismatch_points=7)
        self.assertEqual(len(ibsweep.flags(p)), 2)

    def test_missing_probes_flagged(self):
        self.assertEqual(ibsweep.flags({"mirror": {}}), ["no mirror/headroom probes"])

    def test_incomplete_row_is_not_met_nor_unswept(self):
        def cell(verdict, **kw):
            return dict({"state": "measured", "target_verdict": verdict, "points_valid": 44,
                         "points_expected": 45, "missing": [{"point": "ff_-40c_1.08v", "why": "x"}]}, **kw)
        point = {"rows": {"3a": cell("PASS"), "3b": cell("FAIL"), "3c": cell("PASS"),
                          "1": cell("INCOMPLETE"), "2": {"state": "not swept"},
                          "5b": cell("NOT SPECIFIED")}}
        met, failed, incomplete, unswept = ibsweep.target_rows_met(point)
        self.assertEqual((met, failed, incomplete, unswept), (["3a", "3c"], ["3b"], ["1"], ["2"]))
        self.assertIn("44/45 points valid; ff_-40c_1.08v: x", ibsweep._incomplete_detail(point, "1"))

    def test_ib_of(self):
        self.assertEqual(ibsweep.ib_of(Path("ib_2.5uA")), 2.5)
        self.assertIsNone(ibsweep.ib_of(Path("smoke")))


if __name__ == "__main__":
    unittest.main()

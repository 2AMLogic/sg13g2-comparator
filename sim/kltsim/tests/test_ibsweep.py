"""Regression tests for the issue #80 bias-point sweep helpers (stdlib only)."""

from __future__ import annotations

import json
import tempfile
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


GRID = [(p, v, t) for p in ("tt", "ff") for v in (1.08, 1.2) for t in (-40.0, 27.0)]


def _corner(key, vref=0.4, tmid=0.3, unit="V", status="pass", name=None):
    p, v, t = key
    cid = name or f"mos_{p}/vsup={v:.3f}/{t:g}C"
    return {"corner_id": cid, "process": f"mos_{p}", "supply_v": {"vsup": v, "vsupa": v},
            "temperature_c": t, "status": status, "diagnostics": [], "monte_carlo": None,
            "measurements": [
                {"name": "vdd_meas", "value": v, "unit": "V", "status": "pass"},
                {"name": "vdda_meas", "value": v, "unit": "V", "status": "pass"},
                {"name": "temp_meas", "value": t, "unit": "C", "status": "pass"},
                {"name": "vref_v", "value": vref, "unit": unit, "status": "pass"},
                {"name": "tmid_eval_v", "value": tmid, "unit": unit, "status": "pass"}]}


class ProbeSummaryTests(unittest.TestCase):
    """Issue #267: bias probes are validated per expected PVT point."""

    def summary(self, corners):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "regeneration.envelope.json").write_text(json.dumps({"corners": corners}))
            return ibsweep.probe_summary(Path(d), GRID)

    def good(self):
        return [_corner(k, vref=0.4 + 0.01 * i, tmid=0.3) for i, k in enumerate(GRID)]

    def reasons(self, m):
        return " | ".join(r["why"] for r in m["rejected"])

    def test_golden_complete(self):
        m = self.summary(self.good())
        self.assertTrue(m["complete"])
        self.assertEqual((m["points_valid"], m["points_expected"], m["points"]), (8, 8, 8))
        self.assertEqual(m["rejected"], [])
        self.assertAlmostEqual(m["vref_v"]["min"][0], 0.4)
        self.assertAlmostEqual(m["vref_v"]["max"][0], 0.47)
        self.assertAlmostEqual(m["tail_to_ref"]["max"][0], 0.3 / 0.4)
        self.assertEqual(ibsweep.flags({"mirror": m}), [])

    def check_rejected(self, corners, text, valid=7):
        m = self.summary(corners)
        self.assertFalse(m["complete"])
        self.assertEqual(m["points_valid"], valid)
        self.assertIn(text, self.reasons(m))
        self.assertTrue(any("INCOMPLETE" in f for f in ibsweep.flags({"mirror": m})))
        return m

    def test_errored_corner_excluded_from_extrema(self):
        cs = self.good()
        cs[0] = _corner(GRID[0], vref=0.01, tmid=0.0, status="error")
        m = self.check_rejected(cs, "errored")
        self.assertGreater(m["vref_v"]["min"][0], 0.4)

    def test_repeated_corner_name_rejected(self):
        cs = self.good()
        cs[1]["corner_id"] = cs[0]["corner_id"]
        m = self.check_rejected(cs, "repeated or malformed corner name", valid=6)
        self.assertEqual(m["points_valid"], 6)

    def test_repeated_physical_point_rejected_without_selection(self):
        cs = self.good()
        dup = _corner(GRID[0], vref=0.9, name="other-name")
        m = self.check_rejected(cs + [dup], "ambiguous duplicate PVT result")
        self.assertLess(m["vref_v"]["max"][0], 0.9)
        self.assertEqual(self.summary(cs + [dup]), self.summary([dup] + cs))

    def test_missing_probe(self):
        cs = self.good()
        cs[2]["measurements"] = cs[2]["measurements"][:4]
        self.check_rejected(cs, "tmid_eval_v missing")
        cs = self.good()
        cs[2]["measurements"][3]["value"] = None
        self.check_rejected(cs, "vref_v missing")

    def test_nan_inf_bool_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf"), True, False, "x"):
            cs = self.good()
            cs[3]["measurements"][4]["value"] = bad
            self.check_rejected(cs, "invalid numeric evidence")

    def test_unit_mismatch_rejected_and_valid_conversion(self):
        cs = self.good()
        cs[0]["measurements"][3]["unit"] = "A"
        self.check_rejected(cs, "not a voltage unit")
        cs = self.good()
        cs[0]["measurements"][3].pop("unit")
        self.check_rejected(cs, "unit")
        cs = self.good()
        cs[0]["measurements"][3].update(value=400.0, unit="mV")
        m = self.summary(cs)
        self.assertTrue(m["complete"])
        self.assertAlmostEqual(m["vref_v"]["min"][0], 0.4)

    def test_zero_or_negative_vref_rejected_no_exception(self):
        for bad in (0.0, -0.1):
            cs = self.good()
            cs[0]["measurements"][3]["value"] = bad
            self.check_rejected(cs, "zero or negative")

    def test_partial_coverage_flagged_not_clean(self):
        m = self.summary(self.good()[:5])
        self.assertEqual((m["points_valid"], m["points_expected"]), (5, 8))
        self.assertIn("grid point not in the envelope", self.reasons(m))
        fl = ibsweep.flags({"mirror": m})
        self.assertTrue(any("INCOMPLETE screening: 5/8" in f for f in fl))

    def test_no_valid_points_does_not_crash_report(self):
        m = self.summary([_corner(k, status="error") for k in GRID])
        self.assertEqual(m["points_valid"], 0)
        self.assertNotIn("vref_v", m)
        point = {"dut_ib_ua": 5.0, "tail_ua": 20.0, "mirror": m, "rows": {}}
        self.assertTrue(any("INCOMPLETE" in f for f in ibsweep.flags(point)))
        cells = {r: {"state": "not swept"} for r, _l, _u in ibsweep.ROWS}
        md = ibsweep.render_markdown({"campaign": "x", "points": [dict(point, rows=cells)]})
        self.assertIn("INCOMPLETE screening: 0/8", md)

    def test_outside_grid_corner_rejected(self):
        cs = self.good() + [_corner(("tt", 1.32, 27.0))]
        m = self.summary(cs)
        self.assertIn("outside the expected PVT grid", self.reasons(m))
        self.assertFalse(m["complete"])
        self.assertEqual(m["points_valid"], 8)


if __name__ == "__main__":
    unittest.main()

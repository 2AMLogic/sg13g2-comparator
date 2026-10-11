"""Clock/supply sensitivity (issue #173) unit tests. Stdlib only, no PDK, no
ngspice. Covers the circuit rewrites (exact, one-for-one), the disturbance
timing, the request shape and the paired offset statistics."""

from __future__ import annotations

import copy
import json
import unittest

from kltsim import clocksupply as cs
from kltsim import clocksupply_report as rep


class CircuitRewrites(unittest.TestCase):
    def test_base_is_inert_and_clock_unchanged(self):
        c = cs.condition("base")
        text = cs.regeneration_circuit(c)
        self.assertIn("pulse(0 1 10n 0.1n 0.1n 10n 30n)", text)
        self.assertIn("vdist vdd vddr pulse(0 0 ", text)
        self.assertIn(".param t_flip=20n", text)
        self.assertNotIn("v(vdd)'", text.split("Bclk ")[1].split("\n")[0])

    def test_all_conditions_rewrite_both_circuits(self):
        for c in cs.CONDITIONS:
            self.assertIn("vddar", cs.regeneration_circuit(c))
            off = cs.offset_circuit(c)
            self.assertIn("at=29.0000n", off)
            self.assertIn("at=989.0000n", off)
            self.assertNotIn("at=27.0000n", off)

    def test_disturbance_returns_before_sampling(self):
        for c in cs.CONDITIONS:
            fall_start = c.t_s_n() + cs.DIST_EDGE_N + c.pw_d_n()
            self.assertAlmostEqual(fall_start, cs.DIST_FALL_START_N)
            self.assertLess(fall_start + cs.DIST_EDGE_N, 27.0)

    def test_step_timing(self):
        mid = cs.condition("supmid-p50")
        ev = cs.condition("supeval-m50")
        # strobe midpoint (10 + 0.1 + 5 = 15.1 ns) is the centre of the 1 ns ramp
        self.assertAlmostEqual(mid.t_s_n() + 0.5, 15.1)
        # regeneration condition is centred on the clock's 50 % rising crossing
        self.assertAlmostEqual(ev.t_s_n() + 0.5, 10.05)
        self.assertEqual(ev.vstep, -0.05)

    def test_flip_follows_strobe(self):
        self.assertAlmostEqual(cs.condition("strobe-15n").shift_n(), 5.0)
        self.assertAlmostEqual(cs.condition("edge-2n").shift_n(), 3.8)
        self.assertIn(".param t_flip=25n", cs.regeneration_circuit(cs.condition("strobe-15n")))

    def test_sub_refuses_missing_line(self):
        with self.assertRaises(cs.SensitivityError):
            cs._sub("abc", "xyz", "q")


class Requests(unittest.TestCase):
    def test_regen_request_shape(self):
        req = cs.compose_request("regen", cs.condition("edge-500p"), "b.spice")
        self.assertEqual(len(req["corners"]["process"]) * len(req["corners"]["supply_v"]["vsup"])
                         * len(req["corners"]["temperature_c"]), 45)
        self.assertFalse(req["options"]["keep_artifacts"])
        for m in req["measurements"]:
            if m["name"] in cs.REGEN_SPEC_NAMES:
                self.assertNotIn("limits", m)
        names = [m["name"] for m in req["measurements"]]
        self.assertNotIn("p_avg", names)

    def test_offset_request_is_reduced_and_seeded(self):
        req = cs.compose_request("offset", cs.condition("base"), "b.spice")
        self.assertEqual(req["monte_carlo"]["n"], cs.OFFSET_N)
        self.assertEqual(req["monte_carlo"]["seed"], cs.OFFSET_SEED)
        self.assertEqual(req["corners"]["supply_v"], {"vsup": [1.08, 1.32]})
        self.assertEqual(req["corners"]["temperature_c"], [-40, 125])

    def test_strobe_gate_times_follow_the_strobe(self):
        bench = cs.regeneration_bench(cs.condition("strobe-15n"))
        first = bench.measurement("dout_od1_first").spice
        self.assertIn("at=23n", first)
        self.assertIn("at=58n", bench.measurement("dout_od1_end").spice)


def _corner(vos, idx, seed, key=("tt", 1.08, -40.0)):
    return {"vos_mv": vos, "seed": seed, "lowcount": 10.0, "clipped": False, "problem": None}


class OfflinePairing(unittest.TestCase):
    def setUp(self):
        self.key = ("tt", 1.08, -40.0)
        self.base = {self.key: {i: _corner(float(v), i, 100 + i) for i, v in enumerate([0, 3, -3, 6])}}

    def test_paired_shift(self):
        cond = {self.key: {i: _corner(float(v) + 1.0, i, 100 + i) for i, v in enumerate([0, 3, -3, 6])}}
        p = cs.offset_pair(cond, self.base)
        self.assertEqual(p["n_pairs"], 4)
        self.assertAlmostEqual(p["mean_shift_mv"], 1.0)
        self.assertAlmostEqual(p["sd_delta_mv"], 0.0)
        self.assertEqual(p["changed"], 0)  # 1 mV is below half a 3 mV staircase level

    def test_changed_counts_level_moves_only(self):
        cond = {self.key: {i: _corner(float(v) + (3.0 if i < 2 else 0.0004), i, 100 + i)
                           for i, v in enumerate([0, 3, -3, 6])}}
        p = cs.offset_pair(cond, self.base)
        self.assertEqual(p["changed"], 2)

    def test_seed_mismatch_is_not_paired(self):
        cond = {self.key: {i: _corner(0.0, i, 999 + i) for i in range(4)}}
        p = cs.offset_pair(cond, self.base)
        self.assertEqual(p["n_pairs"], 0)
        self.assertEqual(p["seed_mismatch"], 4)

    def test_clipped_or_untrusted_dropped(self):
        cond = {self.key: {i: _corner(0.0, i, 100 + i) for i in range(4)}}
        cond[self.key][1]["clipped"] = True
        cond[self.key][2]["problem"] = "sample errored"
        p = cs.offset_pair(cond, self.base)
        self.assertEqual(p["n_pairs"], 2)
        self.assertEqual(p["dropped"], 2)


def _m(name, value, unit):
    return {"name": name, "value": value, "unit": unit, "status": "pass", "margin": None}


def _regen_corner(proc="tt", v=1.08, t=-40, **over):
    ms = {"vdd_meas": (v, "V"), "vdda_meas": (v, "V"), "temp_meas": (float(t), "C"),
          "td_od50_ns": (0.7, "ns"), "td_od1_ns": (1.0, "ns"), "td_od01_ns": (1.2, "ns"),
          "tau_ps": (90.0, "ps"),
          "dout_od50_first": (0.0, "V/V"), "dout_od50_end": (1.0, "V/V"),
          "dout_od1_first": (0.0, "V/V"), "dout_od1_end": (1.0, "V/V"),
          "dout_od01_first": (0.0, "V/V"), "dout_od01_end": (1.0, "V/V")}
    ms.update(over)
    return {"corner_id": f"mos_{proc}/{v}/{t}", "process": f"mos_{proc}",
            "supply_v": {"vsup": v, "vsupa": v}, "temperature_c": t, "status": "pass",
            "measurements": [_m(n, *vu) for n, vu in ms.items()]}


def _full_regen_env():
    return {"corners": [_regen_corner(p, v, t) for p in cs.PROCESSES
                        for v in cs.SUPPLIES_V for t in cs.TEMPERATURES_C]}


def _off_corner(proc="tt", v=1.08, t=-40, idx=0, seed="auto", vos=3.0, **over):
    ms = {"vdd_meas": (v, "V"), "temp_meas": (float(t), "C"), "lowcount": (16.0, "levels"),
          "vos_mv": (vos, "mV")}
    ms.update(over)
    mc = {"sample_index": idx}
    if seed == "auto":
        seed = 1000 + idx
    if seed is not None:
        mc["seed"] = seed
    return {"corner_id": f"mos_{proc}_mismatch/{v}/{t}/mc{idx}", "process": f"mos_{proc}_mismatch",
            "supply_v": {"vsup": v}, "temperature_c": t, "status": "pass",
            "measurements": [_m(n, *vu) for n, vu in ms.items()], "monte_carlo": mc}


def _full_off_env(**kw):
    return {"corners": [_off_corner(p, v, t, i, **kw) for p in cs.PROCESSES
                        for v in cs.OFFSET_SUPPLIES_V for t in cs.OFFSET_TEMPERATURES_C
                        for i in range(cs.OFFSET_N)]}


KEY = ("tt", 1.08, -40.0)


class RegenValidation(unittest.TestCase):
    def one(self, **over):
        pts = cs.regen_points({"corners": [_regen_corner(**over)]})
        return pts[KEY]

    def test_clean_full_grid_is_complete_and_strict_json(self):
        pts = cs.regen_points(_full_regen_env())
        s = cs.regen_summary(pts, None)
        self.assertEqual((s["coverage"]["expected"], s["coverage"]["usable"]), (45, 45))
        self.assertTrue(s["coverage"]["complete"])
        json.dumps(s, allow_nan=False)

    def test_bad_probe_values_are_untrusted(self):
        units = {"vdd_meas": "V", "temp_meas": "C", "dout_od1_end": "V/V", "td_od50_ns": "ns"}
        for bad in (float("nan"), float("inf"), -float("inf"), True, "1.0", "abc"):
            for name, unit in units.items():
                p = self.one(**{name: (bad, unit)})
                self.assertTrue(p["problem"], (name, bad))

    def test_nan_never_enters_summary(self):
        env = _full_regen_env()
        env["corners"][0] = _regen_corner(td_od50_ns=(float("nan"), "ns"))
        s = cs.regen_summary(cs.regen_points(env), None)
        self.assertEqual(s["coverage"]["usable"], 44)
        self.assertEqual(s["td50_ns"]["n"], 44)
        self.assertEqual(s["td50_within_1p5ns"], 44)
        json.dumps(s, allow_nan=False)

    def test_nan_supply_and_temperature(self):
        c = _regen_corner()
        c["supply_v"]["vsup"] = float("nan")
        pts = cs.regen_points({"corners": [c]})
        self.assertEqual(len(pts), 0)
        self.assertEqual(len(pts.rejected), 1)
        c = _regen_corner()
        c["temperature_c"] = float("nan")
        self.assertEqual(len(cs.regen_points({"corners": [c]}).rejected), 1)
        c = _regen_corner()
        c["supply_v"]["vsupa"] = float("nan")
        self.assertTrue(cs.regen_points({"corners": [c]})[KEY]["problem"])

    def test_wrong_dimension_and_wrong_temperature(self):
        self.assertTrue(self.one(vdd_meas=(1.08, "ps"))["problem"])
        self.assertTrue(self.one(temp_meas=(-40.0, "pC"))["problem"])
        self.assertTrue(self.one(td_od50_ns=(0.7, "V"))["problem"])
        self.assertTrue(self.one(temp_meas=(27.0, "C"))["problem"])
        self.assertTrue(self.one(vdd_meas=(1.08, None))["problem"])

    def test_compatible_units_normalise(self):
        a = self.one()
        b = self.one(td_od50_ns=(700.0, "ps"), vdd_meas=(1080.0, "mV"), tau_ps=(0.09, "ns"))
        self.assertIsNone(b["problem"])
        self.assertAlmostEqual(b["td50_ns"], a["td50_ns"])
        self.assertAlmostEqual(b["tau_ps"], a["tau_ps"])

    def test_duplicate_measurement_name_reason_kept(self):
        c = _regen_corner()
        c["measurements"].append(_m("tau_ps", 91.0, "ps"))
        self.assertIn("duplicate measurement", cs.regen_points({"corners": [c]})[KEY]["problem"])

    def test_duplicate_corner_rejected_in_any_order(self):
        a, b = _regen_corner(), _regen_corner(td_od50_ns=(0.9, "ns"))
        other = _regen_corner("ff", 1.2, 27)
        fwd = cs.regen_points({"corners": [a, b, other]})
        rev = cs.regen_points({"corners": [other, b, a]})
        self.assertEqual(dict(fwd), dict(rev))
        self.assertIn("duplicate", fwd[KEY]["problem"])
        self.assertIsNone(fwd[KEY]["td50_ns"])
        self.assertIsNone(fwd[("ff", 1.2, 27.0)]["problem"])
        s = cs.regen_summary(fwd, None)
        self.assertEqual(s["coverage"]["usable"], 1)

    def test_partial_grid_is_labelled(self):
        env = _full_regen_env()
        del env["corners"][5:]
        s = cs.regen_summary(cs.regen_points(env), None)
        self.assertFalse(s["coverage"]["complete"])
        self.assertIn("PARTIAL", s["coverage"]["label"])
        self.assertEqual(len(s["coverage"]["missing"]), 40)

    def test_off_grid_point_not_usable(self):
        self.assertIn("grid", cs.regen_points({"corners": [_regen_corner(v=1.1)]})[("tt", 1.1, -40.0)]["problem"])


class OffsetValidation(unittest.TestCase):
    def test_full_grid_coverage(self):
        smp = cs.offset_samples(_full_off_env())
        cov = cs.offset_coverage(smp)
        self.assertEqual((cov["expected"], cov["usable"]), (20 * cs.OFFSET_N, 20 * cs.OFFSET_N))
        self.assertTrue(cov["complete"])

    def test_duplicate_sample_identity_rejected_in_any_order(self):
        a, b = _off_corner(idx=1), _off_corner(idx=1, vos=6.0)
        c = _off_corner(idx=2)
        fwd = cs.offset_samples({"corners": [a, b, c]})
        rev = cs.offset_samples({"corners": [c, b, a]})
        self.assertEqual(dict(fwd), dict(rev))
        self.assertIn("duplicate", fwd[KEY][1]["problem"])
        self.assertIsNone(fwd[KEY][1]["vos_mv"])
        self.assertIsNone(fwd[KEY][2]["problem"])

    def test_bad_probes_untrusted(self):
        for over in ({"vos_mv": (float("nan"), "mV")}, {"vos_mv": (3.0, "V/V")},
                     {"lowcount": (float("inf"), "levels")}, {"temp_meas": (27.0, "C")},
                     {"temp_meas": (float("nan"), "C")}, {"vdd_meas": (1.08, "ps")},
                     {"vdd_meas": (1.2, "V")}):
            p = cs.offset_samples({"corners": [_off_corner(**over)]})[KEY][0]
            self.assertTrue(p["problem"], over)
        p = cs.offset_samples({"corners": [_off_corner(vos_mv=(0.003, "V"))]})[KEY][0]
        self.assertIsNone(p["problem"])
        self.assertAlmostEqual(p["vos_mv"], 3.0)

    def test_bad_identity_rejected(self):
        for mc in (None, {"seed": 1}, {"sample_index": True}, {"sample_index": "0"},
                   {"sample_index": -1}):
            c = _off_corner()
            if mc is None:
                del c["monte_carlo"]
            else:
                c["monte_carlo"] = mc
            smp = cs.offset_samples({"corners": [c]})
            self.assertEqual(len(smp), 0)
            self.assertEqual(len(smp.rejected), 1)

    def test_absent_seed_on_both_sides_is_not_paired(self):
        base = cs.offset_samples({"corners": [_off_corner(idx=i, seed=None) for i in range(3)]})
        cond = cs.offset_samples({"corners": [_off_corner(idx=i, seed=None) for i in range(3)]})
        p = cs.offset_pair(cond, base)
        self.assertEqual((p["n_pairs"], p["seed_absent"], p["seed_mismatch"]), (0, 3, 0))
        self.assertIsNone(p["pooled_sigma_mv"])

    def test_valid_pairs_remain_paired_and_mismatch_counted_apart(self):
        base = cs.offset_samples({"corners": [_off_corner(idx=i) for i in range(3)]})
        cond = cs.offset_samples({"corners": [_off_corner(idx=0, vos=6.0), _off_corner(idx=1, seed=5),
                                              _off_corner(idx=2, seed=None)]})
        p = cs.offset_pair(cond, base)
        self.assertEqual((p["n_pairs"], p["seed_mismatch"], p["seed_absent"]), (1, 1, 1))
        self.assertAlmostEqual(p["mean_shift_mv"], 3.0)

    def test_untrusted_sample_not_in_stats(self):
        base = cs.offset_samples({"corners": [_off_corner(idx=i) for i in range(2)]})
        cond = cs.offset_samples({"corners": [_off_corner(idx=0, vos=3.0),
                                              _off_corner(idx=1, vos_mv=(float("nan"), "mV"))]})
        p = cs.offset_pair(cond, base)
        self.assertEqual(p["n_pairs"], 1)
        self.assertEqual(p["dropped"], 1)

    def test_partial_grid_labelled(self):
        env = _full_off_env()
        env["corners"] = env["corners"][:-3]
        cov = cs.offset_coverage(cs.offset_samples(env))
        self.assertEqual((cov["present"], cov["missing"], cov["complete"]), (317, 3, False))
        self.assertIn("PARTIAL", cov["label"])


class ReportJson(unittest.TestCase):
    def test_dumps_report_is_strict(self):
        out = rep.dumps_report({"a": float("nan"), "b": [float("inf"), 1.0]})
        self.assertNotIn("NaN", out)
        self.assertNotIn("Infinity", out)
        json.loads(out, parse_constant=lambda c: self.fail(c))

    def test_reference_campaign_still_readable(self):
        d = rep.build_mod.EXPERIMENT_DIR / "campaigns" / rep.REFERENCE_CAMPAIGN
        p = d / "regeneration.envelope.json"
        if not p.is_file():
            self.skipTest("reference campaign not present")
        pts = cs.regen_points(json.loads(p.read_text(encoding="utf-8")))
        self.assertEqual(sum(1 for q in pts.values() if not q["problem"]), 45)


if __name__ == "__main__":
    unittest.main()

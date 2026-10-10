"""Memory / hysteresis characterization tests (issue #159). Stdlib only, no
PDK, no ngspice, writes nothing outside a temporary directory.

Covers: bisection (10-ary search) termination and the exact 10 uV bracket,
resolution accounting, the signed shift, rejected / unresolved points,
wrong-polarity classification (kept apart from unresolved), both control
verdict boundaries (20 / 40 / +20 uV, exact), and the netlist / request
contract (paired histories in one deck, 9 ns sample, control clocks).
"""

from __future__ import annotations

import unittest
from fractions import Fraction

from kltsim import build, memory as mem


def sigmoid_decision(threshold_uv, unresolved_halfwidth_uv=0.0):
    """Synthetic decision function: -1 below the threshold, +1 above, and a
    metastable band (|x - thr| < halfwidth) in between."""
    def f(x):
        d = x - threshold_uv
        if abs(d) < unresolved_halfwidth_uv:
            return 0.0
        return 1.0 if d > 0 else -1.0
    return f


def run_search(f, *, max_rounds=mem.MAX_ROUNDS):
    s = mem.Search()
    n = 0
    while s.active and n < max_rounds:
        probes = s.next_probes()
        s.update({p: f(p) for p in probes})
        n += 1
    return s


class ClassifyTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(mem.classify(0.8, 10)["class"], mem.POS)
        self.assertEqual(mem.classify(-0.8, -10)["class"], mem.NEG)
        self.assertEqual(mem.classify(0.7999, 10)["class"], mem.UNRES)
        self.assertEqual(mem.classify(-0.7999, -10)["class"], mem.UNRES)
        self.assertIsNone(mem.classify(None, 0)["class"])
        self.assertIsNone(mem.classify(float("nan"), 0)["class"])

    def test_wrong_polarity_is_not_unresolved(self):
        w = mem.classify(1.0, -5)
        self.assertEqual(w["class"], mem.POS)
        self.assertTrue(w["wrong_polarity"])
        w = mem.classify(-1.0, +5)
        self.assertTrue(w["wrong_polarity"])
        self.assertFalse(mem.classify(1.0, +5)["wrong_polarity"])
        self.assertFalse(mem.classify(-1.0, -5)["wrong_polarity"])
        # a zero probe has no polarity to oppose
        self.assertFalse(mem.classify(1.0, 0)["wrong_polarity"])
        # unresolved is never wrong-polarity
        u = mem.classify(0.1, -5)
        self.assertEqual(u["class"], mem.UNRES)
        self.assertFalse(u["wrong_polarity"])


class SearchTests(unittest.TestCase):
    def test_schedule_is_exactly_10uv_in_four_rounds(self):
        widths = [mem.round_step_uv(k) * mem.FANOUT for k in range(1, mem.MAX_ROUNDS + 1)]
        self.assertEqual(widths, [100_000, 10_000, 1_000, 100])
        self.assertEqual(mem.round_step_uv(mem.MAX_ROUNDS), mem.RESOLUTION_UV)

    def test_terminates_within_four_rounds_at_exactly_10uv(self):
        for thr in (-49_995, -1234, 0, 3, 17_777, 49_994):
            s = run_search(sigmoid_decision(thr))
            self.assertTrue(s.done, thr)
            self.assertEqual(s.rounds, mem.MAX_ROUNDS)
            self.assertEqual(s.width_uv, 10)
            self.assertLessEqual(s.width_uv, mem.RESOLUTION_UV)
            self.assertLessEqual(s.lo_uv, thr)
            self.assertGreaterEqual(s.hi_uv, thr)
            self.assertLessEqual(abs(float(s.threshold_uv()) - thr), 5.0)

    def test_round_probe_counts(self):
        self.assertEqual(len(mem.round_probes(-50_000, 50_000, True)), 11)
        self.assertEqual(mem.round_probes(-50_000, 50_000, True)[0], -50_000)
        self.assertEqual(mem.round_probes(-50_000, 50_000, True)[-1], 50_000)
        interior = mem.round_probes(-10_000, 0, False)
        self.assertEqual(len(interior), 9)
        self.assertNotIn(-10_000, interior)
        self.assertNotIn(0, interior)

    def test_threshold_exactly_on_a_grid_point(self):
        # thr = 0: f(0) > 0 when d > 0 is False, so 0 resolves negative; the
        # bracket still closes around it.
        s = run_search(sigmoid_decision(0))
        self.assertTrue(s.done)
        self.assertEqual(s.width_uv, 10)
        self.assertEqual(s.lo_uv, 0 - 0)  # [0, 10]: 0 resolves negative
        self.assertEqual(s.hi_uv, 10)

    def test_resolution_accounting(self):
        s = run_search(sigmoid_decision(1234))
        t = s.tally
        self.assertEqual(t["evaluated"], 11 + 9 * 3)
        self.assertEqual(t["resolved_positive"] + t["resolved_negative"] + t["unresolved"], t["evaluated"])
        self.assertEqual(t["unresolved"], 0)
        self.assertEqual(t["missing"], 0)
        self.assertEqual([r["round"] for r in s.log], [1, 2, 3, 4])
        # wrong polarity: every probe below 0 that resolves positive, etc.
        # threshold +1234: probes in (0, 1234) resolve negative with a positive
        # input -> wrong polarity.
        self.assertGreater(t["wrong_polarity"], 0)
        res = mem.history_result(s)
        self.assertEqual(res["bracket_width_uv"], 10)
        self.assertEqual(res["rounds"], 4)

    def test_signed_shift(self):
        p = run_search(sigmoid_decision(-300))
        n = run_search(sigmoid_decision(+450))
        shift = mem.memory_shift_uv(p, n)
        self.assertIsInstance(shift, Fraction)
        self.assertLess(shift, 0)               # P threshold below N threshold
        self.assertLessEqual(abs(float(shift) - (-750)), 10.0)
        swapped = mem.memory_shift_uv(n, p)
        self.assertEqual(swapped, -shift)
        res = mem.point_result(p, n)
        self.assertAlmostEqual(res["memory_shift_mV"], float(shift) / 1000.0)
        self.assertAlmostEqual(res["abs_memory_shift_mV"], abs(float(shift)) / 1000.0)
        self.assertEqual(res["final_bracket_width_uV"], {"P": 10, "N": 10})
        self.assertIsNone(res["rejected"])
        self.assertLess(res["threshold_after_P_mV"], res["threshold_after_N_mV"])

    def test_identical_histories_give_zero_shift(self):
        p = run_search(sigmoid_decision(777))
        n = run_search(sigmoid_decision(777))
        self.assertEqual(mem.memory_shift_uv(p, n), 0)

    def test_rejected_initial_bracket_same_polarity(self):
        s = run_search(lambda x: 1.0)        # always positive: no sign change
        self.assertFalse(s.done)
        self.assertIn("initial bracket", s.rejected)
        self.assertIsNone(s.threshold_uv())
        s = run_search(lambda x: -1.0)
        self.assertIn("initial bracket", s.rejected)

    def test_rejected_reversed_polarity(self):
        s = run_search(lambda x: -1.0 if x > 0 else 1.0)
        self.assertTrue(s.rejected)
        self.assertFalse(s.done)

    def test_rejected_unresolved_endpoint(self):
        s = run_search(lambda x: 0.1 if x == mem.INIT_LO_UV else (1.0 if x > 0 else -1.0))
        self.assertIn("endpoint unresolved", s.rejected)

    def test_unresolved_inside_bracket_rejects_without_fabricating(self):
        # a metastable band wider than the probe spacing at the crossing
        s = run_search(sigmoid_decision(1234, unresolved_halfwidth_uv=3000))
        self.assertFalse(s.done)
        self.assertIn("unresolved point inside the switching bracket", s.rejected)
        self.assertIsNone(s.threshold_uv())
        self.assertGreater(s.tally["unresolved"], 0)
        res = mem.history_result(s)
        self.assertIsNone(res["threshold_mv"])
        self.assertIsNone(res["bracket_width_uv"])

    def test_unresolved_off_path_is_counted_not_rejected(self):
        # a stray unresolved probe far from the crossing does not stop the search
        def f(x):
            if x == -30_000:
                return 0.0
            return 1.0 if x > 1234 else -1.0
        s = run_search(f)
        self.assertTrue(s.done)
        self.assertEqual(s.tally["unresolved"], 1)
        self.assertEqual(s.tally["wrong_polarity"] > 0, True)

    def test_non_monotone_rejects(self):
        # - + - + ...: more than one sign change
        s = run_search(lambda x: {-50_000: -1.0, -40_000: 1.0, -30_000: -1.0}.get(
            x, 1.0 if x > 0 else -1.0))
        self.assertFalse(s.done)
        self.assertIn("non-monotone", s.rejected)

    def test_missing_measurement_rejects(self):
        s = mem.Search()
        probes = s.next_probes()
        d = {p: (1.0 if p > 0 else -1.0) for p in probes}
        d[probes[3]] = None
        s.update(d)
        self.assertEqual(s.rejected, "missing measurement")
        self.assertEqual(s.tally["missing"], 1)

    def test_wrong_polarity_counts_are_separate_from_unresolved(self):
        # offset +20 mV: probes in (0, 20 mV) are resolved negative with a
        # positive input -> wrong polarity, none unresolved.
        s = run_search(sigmoid_decision(20_000))
        self.assertTrue(s.done)
        self.assertGreater(s.tally["wrong_polarity"], 0)
        self.assertEqual(s.tally["unresolved"], 0)
        # and the reverse mix: an unresolved band that is NOT the crossing
        s2 = mem.Search()
        probes = s2.next_probes()
        d = {p: (1.0 if p > 20_000 else -1.0) for p in probes}
        d[probes[2]] = 0.2   # unresolved, off the crossing
        s2.update(d)
        self.assertEqual(s2.tally["unresolved"], 1)
        self.assertEqual(s2.tally["wrong_polarity"], 2)   # probes 0 and 10 mV
        self.assertIsNone(s2.rejected)

    def test_bracket_off_schedule_is_refused(self):
        searches = mem.new_searches([("mos_tt", 1.2, 27.0)])
        with self.assertRaises(mem.MemoryError_):
            mem.build_plan(searches, 2)   # round 2 before round 1 has narrowed it


class ControlVerdictTests(unittest.TestCase):
    def test_long_reset_boundary(self):
        self.assertEqual(mem.long_reset_verdict(20.0)["verdict"], "PASS")
        self.assertEqual(mem.long_reset_verdict(-20.0)["verdict"], "PASS")
        self.assertEqual(mem.long_reset_verdict(0)["verdict"], "PASS")
        self.assertEqual(mem.long_reset_verdict(20.5)["verdict"], "FAIL")
        self.assertEqual(mem.long_reset_verdict(-20.5)["verdict"], "FAIL")
        self.assertEqual(mem.long_reset_verdict(None)["verdict"], "FAIL")

    def test_short_reset_boundary(self):
        # exactly 40 uV and exactly +20 uV over the long-reset shift passes
        self.assertEqual(mem.short_reset_verdict(40.0, 20.0)["verdict"], "PASS")
        self.assertEqual(mem.short_reset_verdict(-40.0, 20.0)["verdict"], "PASS")
        self.assertEqual(mem.short_reset_verdict(40.0, 0.0)["verdict"], "PASS")
        # just below 40
        v = mem.short_reset_verdict(39.5, 0.0)
        self.assertEqual(v["verdict"], "FAIL")
        self.assertIn("below 40", v["reason"])
        # >= 40 but not 20 uV above the long-reset shift
        v = mem.short_reset_verdict(45.0, 26.0)
        self.assertEqual(v["verdict"], "FAIL")
        self.assertIn("excess over long-reset", v["reason"])
        self.assertEqual(mem.short_reset_verdict(46.0, 26.0)["verdict"], "PASS")
        self.assertEqual(mem.short_reset_verdict(None, 0.0)["verdict"], "FAIL")
        self.assertEqual(mem.short_reset_verdict(100.0, None)["verdict"], "FAIL")

    def test_controls_from_synthetic_searches(self):
        # long reset: history-independent thresholds 10 uV apart -> shift 10 PASS;
        # short reset: 60 uV apart -> PASS
        lp, ln = run_search(sigmoid_decision(105)), run_search(sigmoid_decision(95))
        sp, sn = run_search(sigmoid_decision(125)), run_search(sigmoid_decision(65))
        ls, ss = mem.memory_shift_uv(lp, ln), mem.memory_shift_uv(sp, sn)
        self.assertEqual(mem.long_reset_verdict(ls)["verdict"], "PASS")
        self.assertEqual(mem.short_reset_verdict(ss, ls)["verdict"], "PASS")
        # a short-reset run showing no memory fails the sensitivity control
        flat = mem.memory_shift_uv(run_search(sigmoid_decision(105)), run_search(sigmoid_decision(105)))
        self.assertEqual(mem.short_reset_verdict(flat, ls)["verdict"], "FAIL")


class NetlistContractTests(unittest.TestCase):
    def setUp(self):
        keys = mem.grid_keys(["tt"])
        self.searches = mem.new_searches(keys)
        self.plan = mem.build_plan(self.searches, 1)
        self.tables = mem.lo_tables_for(self.plan)

    def circuit(self, period=30.0, first=True, step=10_000):
        return mem.compose_circuit(period, first, step, self.tables)

    def test_both_histories_one_deck_one_clock_one_supply(self):
        c = self.circuit()
        self.assertEqual(c.count("\nvsup "), 1)
        self.assertEqual(c.count("\nvclku "), 1)
        self.assertIn("pulse(0 1 10n 100p 100p 10n 30n)", c)
        for h in ("P", "N"):
            for m in range(11):
                self.assertIn(f"\nX{h}{m} ", c)
        self.assertEqual(c.count("comparator_dut"), 22)
        # the histories differ only in the conditioning source
        p = [ln for ln in c.splitlines() if ln.startswith("BsP3 ")][0]
        n = [ln for ln in c.splitlines() if ln.startswith("BsN3 ")][0]
        self.assertEqual(p.replace("BsP3 sP3", "X").replace("v(cp)", "C").replace("loP", "L"),
                         n.replace("BsN3 sN3", "X").replace("v(cn)", "C").replace("loN", "L"))
        self.assertIn("vcp   cp   0 dc 0.05", c)
        self.assertIn("vcn   cn   0 dc -0.05", c)

    def test_sample_time_nine_ns_after_fourth_rise(self):
        for period, t_sample in ((30.0, 109.0), (110.0, 349.0), (11.0, 52.0)):
            ck = mem.clock_times_ns(period)
            self.assertEqual(ck["rise_ns"][3], 10.0 + 3 * period)
            self.assertEqual(ck["t_sample_ns"], t_sample)
            self.assertEqual(ck["reset_ns"], period - 10.0)
            meas = {m["name"]: m["spice"] for m in mem.measurements(period, True)}
            self.assertIn(f"at={mem._ns(t_sample)}", meas["d_P_5"])
            self.assertIn(f"at={mem._ns(t_sample)}", meas["s_N_0"])
            # the input changes after the third strobe has fallen and before the fourth rises
            self.assertGreater(ck["t_switch_ns"], ck["rise_ns"][2] + 10.2)
            self.assertLess(ck["t_switch_ns"] + 0.1, ck["rise_ns"][3])

    def test_committed_reference_circuit_is_current(self):
        self.assertEqual(mem.REFERENCE_CIRCUIT.read_text(encoding="utf-8"), mem.reference_circuit())

    def test_controls_keep_the_10ns_pulse(self):
        self.assertEqual(mem.LONG_RESET_PERIOD_NS - mem.HIGH_NS, 100.0)
        self.assertEqual(mem.SHORT_RESET_PERIOD_NS - mem.HIGH_NS, 1.0)
        self.assertIn("10n 110n)", self.circuit(period=110.0))
        self.assertIn("10n 11n)", self.circuit(period=11.0))

    def test_measurement_set_and_no_limits(self):
        first = mem.measurements(30.0, True)
        later = mem.measurements(30.0, False)
        self.assertEqual(len(first), 4 + 2 * 11 * 2)
        self.assertEqual(len(later), 4 + 2 * 9 * 2)
        self.assertTrue(all("limits" not in m for m in first))
        decision = mem.compose_circuit(30.0, True, 10_000, self.tables)
        self.assertIn("(v(doutP0)-v(doutbP0))/v(vdd)", decision)

    def test_lookup_expression_is_constant_when_uniform_else_selects(self):
        self.assertEqual(mem.lookup_expr({(1.2, 27): -50_000, (1.08, 27): -50_000}), "-50000")
        expr = mem.lookup_expr({(1.08, -40): 100, (1.2, 27): 200, (1.32, 125): 300})
        self.assertIn("temper<0", expr)
        self.assertIn("*300", expr)

    def test_request_shape(self):
        req = mem.compose_request(30.0, True, "b.spice", ["mos_tt"])
        self.assertEqual(req["backend"], "batch")
        self.assertEqual(req["corners"]["process"], ["mos_tt"])
        self.assertEqual(len(req["corners"]["supply_v"]["vsup"]) * len(req["corners"]["temperature_c"]), 9)
        self.assertEqual(req["analysis"]["kind"], "tran")
        self.assertEqual(req["analysis"]["args"], "5p 110n")
        one = mem.compose_request(11.0, False, "b.spice", ["mos_tt"], grid=[(1.2, 27)])
        self.assertEqual(one["corners"]["supply_v"], {"vsup": [1.2]})
        self.assertEqual(one["corners"]["temperature_c"], [27])
        self.assertNotIn("monte_carlo", req)

    def test_body_embeds_the_current_dut_with_its_hash(self):
        body = mem.compose_body(30.0, True, 10_000, self.tables, title="t")
        path, sha, embedded = build.extract_dut_block(body)
        binding = build.load_dut_binding()
        self.assertEqual(sha, build.sha256_file(binding["_netlist_path"]))
        self.assertEqual(embedded.encode("utf-8"), binding["_netlist_path"].read_bytes())
        self.assertIn("pre_osdi", body)
        # re-composing is byte-stable (append-only campaign inputs)
        self.assertEqual(body, mem.compose_body(30.0, True, 10_000, self.tables, title="t"))


def _corner(process, supply, temp, values, status="pass"):
    return {"corner_id": f"{process}/{supply:.3f}V/{temp:g}C", "process": process,
            "supply_v": {"vsup": supply}, "temperature_c": temp, "status": status,
            "runtime_s": 1.0,
            "measurements": [{"name": k, "value": v, "status": "pass"} for k, v in values.items()]}


def synthetic_env(plan, thresholds, key, period=30.0, first=True, **overrides):
    """An envelope for one corner whose P/N histories switch at thresholds."""
    proc, supply, temp = key
    vals = {"vdd_meas": supply, "temp_meas": float(temp)}
    mult = list(range(0, 11)) if first else list(range(1, 10))
    for h in mem.HISTORIES:
        vals[f"lo_{h}_meas"] = float(plan[key][h]["lo"])
        for m, p in zip(mult, plan[key][h]["probes"]):
            vals[f"d_{h}_{m}"] = 1.0 if p > thresholds[h] else -1.0
            vals[f"s_{h}_{m}"] = p * 1e-6
    vals.update(overrides)
    return {"corners": [_corner(proc, supply, temp, vals)]}


class ReplayTests(unittest.TestCase):
    KEY = ("mos_tt", 1.2, 27.0)

    def drive(self, thresholds, **kw):
        searches = mem.new_searches([self.KEY])
        for k in range(1, mem.MAX_ROUNDS + 1):
            if not searches[self.KEY].active():
                break
            plan = mem.build_plan(searches, k)
            env = synthetic_env(plan, thresholds, self.KEY, first=(k == 1), **(kw if k == 1 else {}))
            ex = mem.extract_round(env, 30.0, k == 1, plan)
            mem.apply_round(searches, ex, k == 1)
        return searches[self.KEY]

    def test_four_rounds_close_both_histories(self):
        ps = self.drive({"P": -1234, "N": 4321})
        self.assertIsNone(ps.problem)
        self.assertTrue(ps.P.done and ps.N.done)
        self.assertEqual((ps.P.width_uv, ps.N.width_uv), (10, 10))
        shift = mem.memory_shift_uv(ps.P, ps.N)
        self.assertLessEqual(abs(float(shift) + 5555), 10)

    def test_applied_probe_mismatch_rejects_the_point(self):
        ps = self.drive({"P": 0, "N": 0}, s_P_3=0.0123)
        self.assertIn("applied probe", ps.problem)
        self.assertFalse(ps.P.done)

    def test_wrong_supply_probe_rejects_the_point(self):
        ps = self.drive({"P": 0, "N": 0}, vdd_meas=1.08)
        self.assertIn("supply probe", ps.problem)

    def test_bracket_lookup_mismatch_rejects_the_point(self):
        ps = self.drive({"P": 0, "N": 0}, lo_N_meas=-1.0)
        self.assertIn("bracket lookup", ps.problem)

    def test_missing_corner_is_a_problem_not_a_pass(self):
        searches = mem.new_searches([self.KEY])
        plan = mem.build_plan(searches, 1)
        ex = mem.extract_round({"corners": []}, 30.0, True, plan)
        mem.apply_round(searches, ex, True)
        self.assertIn("missing", searches[self.KEY].problem)

    def test_errored_corner_is_a_problem(self):
        searches = mem.new_searches([self.KEY])
        plan = mem.build_plan(searches, 1)
        env = {"corners": [_corner(*self.KEY, {}, status="error")]}
        ex = mem.extract_round(env, 30.0, True, plan)
        self.assertIn("status", ex[self.KEY]["problem"])


if __name__ == "__main__":
    unittest.main()

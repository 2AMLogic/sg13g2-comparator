"""Clock/supply sensitivity (issue #173) unit tests. Stdlib only, no PDK, no
ngspice. Covers the circuit rewrites (exact, one-for-one), the disturbance
timing, the request shape and the paired offset statistics."""

from __future__ import annotations

import unittest

from kltsim import clocksupply as cs


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


if __name__ == "__main__":
    unittest.main()

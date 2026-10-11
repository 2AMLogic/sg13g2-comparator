"""CM-band decision-time tests (issue #164). Stdlib only, no PDK, no ngspice."""

from __future__ import annotations

import unittest

from kltsim import cmdecision as cd
from kltsim.benches import REGENERATION


def _corner(key, *, vcm=0.6, td50=0.7, td01=1.3, tau=100.0, status="pass", gate_ok=True,
            drop=None):
    proc, v, t = key
    proc = f"mos_{proc}"
    ms = {
        "vdd_meas": (v, "V"), "vdda_meas": (v, "V"), "temp_meas": (t, "C"),
        "td_od50_ns": (td50, "ns"), "td_od1_ns": (1.0, "ns"), "td_od01_ns": (td01, "ns"),
        "tau_ps": (tau, "ps"), "resolve_decades": (8.0, "1"), "p_avg_uw": (50.0, "uW"),
        "vcm_meas": (vcm, "V"),
    }
    for g in cd.GATES:
        first = g.endswith("_first")
        ms[g] = ((0.0 if first else 1.0) if gate_ok else 0.5, "V/V")
    out = [{"name": n, "value": val, "unit": u,
            "status": "pass" if (gate_ok or n not in cd.GATES) else "fail"}
           for n, (val, u) in ms.items() if n != drop]
    return {"corner_id": f"{proc}/{v}/{t}", "process": proc,
            "supply_v": {"vsup": v, "vsupa": v}, "temperature_c": t,
            "status": status, "measurements": out}


def _env(over=None):
    over = over or {}
    corners = []
    for k in cd.expected_keys():
        corners.append(_corner(k, **over.get(k, {})))
    return {"corners": corners}


class BodyTests(unittest.TestCase):
    def test_transform_round_trip_and_condition(self):
        body = "* a\n* b\nfoo\n" + cd.VCM_LINE + "\nbar"
        for cond in cd.CONDITIONS:
            out = cd.apply_transform(body, cond)
            self.assertIn(f".param vcm_delta={cond.delta_v!r}", out)
            self.assertIn(cd.VCM_LINE_CM, out)
            self.assertNotIn("\n" + cd.VCM_LINE + "\n", out)
            self.assertEqual(cd.undo_transform(out).split("\n")[2:], body.split("\n")[2:])

    def test_exactly_one_source_line_required(self):
        with self.assertRaises(cd.DecisionCmError):
            cd.apply_transform("a\nb\nc", cd.condition("vcm-nom"))
        with self.assertRaises(cd.DecisionCmError):
            cd.apply_transform(f"a\nb\n{cd.VCM_LINE}\n{cd.VCM_LINE}", cd.condition("vcm-nom"))

    def test_request_is_regeneration_plus_probe(self):
        req = cd.compose_request(cd.condition("vcm-m050"))
        names = [m["name"] for m in req["measurements"]]
        self.assertEqual(names, [m.name for m in REGENERATION.measurements] + ["vcm_meas"])
        self.assertEqual(req["backend"], "batch")
        self.assertNotIn("monte_carlo", req)
        self.assertEqual(len(req["corners"]["process"]), 5)
        self.assertEqual(req["corners"]["supply_v"]["vsup"], req["corners"]["supply_v"]["vsupa"])
        self.assertEqual(req["analysis"], {"kind": "tran", "args": "5p 60n"})
        self.assertEqual(req["_condition"]["vcm_delta_v"], -0.05)
        self.assertAlmostEqual(req["_condition"]["vcm_v"], 0.55)


class AnalysisTests(unittest.TestCase):
    def test_all_valid(self):
        s = cd.summarize(cd.load_points(_env(), 0.6))
        self.assertEqual((s["points_valid"], s["rejected"]), (45, []))
        self.assertEqual(s["grid"]["td_od50_ns"]["target_fail_points"], 0)
        self.assertEqual(s["grid"]["td_od50_ns"]["stretch_fail_points"], 0)

    def test_target_fail_is_graded_not_rejected(self):
        k = cd.expected_keys()[3]
        s = cd.summarize(cd.load_points(_env({k: {"td50": 1.6}}), 0.6))
        self.assertEqual(s["points_valid"], 45)
        self.assertEqual(s["grid"]["td_od50_ns"]["target_fail_points"], 1)

    def test_rejections_named_with_reason(self):
        keys = cd.expected_keys()
        env = _env({keys[0]: {"status": "error"}, keys[1]: {"vcm": 0.7},
                      keys[2]: {"gate_ok": False}, keys[3]: {"drop": "tau_ps"}})
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 41)
        reasons = {r["point"]: r["reason"] for r in s["rejected"]}
        self.assertEqual(len(reasons), 4)
        self.assertIn("errored", reasons[cd.key_label(keys[0])])
        self.assertIn("vcm_meas", reasons[cd.key_label(keys[1])])
        self.assertIn("gate", reasons[cd.key_label(keys[2])])
        self.assertIn("tau_ps", reasons[cd.key_label(keys[3])])

    def test_missing_point_is_rejected(self):
        env = _env()
        env["corners"].pop()
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 44)
        self.assertIn("missing", s["rejected"][0]["reason"])

    def test_reproduction(self):
        a, b = _env(), _env()
        for c in b["corners"]:
            c["measurements"] = [m for m in c["measurements"] if m["name"] != "vcm_meas"]
        self.assertTrue(cd.reproduction(a, b)["bit_identical"])
        b["corners"][5]["measurements"][4]["value"] += 1e-12
        rep = cd.reproduction(a, b)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(len(rep["mismatches"]), 1)

    def _drop(self, env, name, only=None):
        for i, c in enumerate(env["corners"]):
            if only is None or i == only:
                c["measurements"] = [m for m in c["measurements"] if m["name"] != name]

    def test_reproduction_missing_measurement_one_point(self):
        a, b = _env(), _env()
        self._drop(a, "td_od1_ns", only=7)
        rep = cd.reproduction(a, b)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(len(rep["mismatches"]), 1)
        self.assertEqual(rep["mismatches"][0]["measurement"], "td_od1_ns")
        self.assertEqual(rep["mismatches"][0]["point"], cd.key_label(cd.expected_keys()[7]))

    def test_reproduction_missing_measurement_all_points(self):
        a, b = _env(), _env()
        self._drop(a, "td_od1_ns")
        rep = cd.reproduction(a, b)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(len(rep["mismatches"]), 45)
        self.assertTrue(all(m["measurement"] == "td_od1_ns" for m in rep["mismatches"]))

    def test_reproduction_extra_nominal_probe_still_identical(self):
        a, b = _env(), _env()
        self._drop(b, "vcm_meas")
        rep = cd.reproduction(a, b)
        self.assertTrue(rep["bit_identical"])
        self.assertEqual(rep["values_compared"], 45 * 9 + 45 * 0 + 45 * len(cd.GATES))

    def test_reproduction_missing_corner_and_malformed_lists(self):
        a, b = _env(), _env()
        a["corners"].pop()
        self.assertFalse(cd.reproduction(a, b)["bit_identical"])
        a = _env()
        a["corners"][3]["measurements"].append(dict(a["corners"][3]["measurements"][0]))
        self.assertFalse(cd.reproduction(a, b)["bit_identical"])
        a = _env()
        a["corners"][3]["measurements"] = "bad"
        self.assertFalse(cd.reproduction(a, b)["bit_identical"])

    def test_vcm_probe_rejections(self):
        keys = cd.expected_keys()
        bad = [float("nan"), float("inf"), float("-inf"), True, False, None, "0.6", [0.6], {}]
        for v in bad:
            with self.subTest(v=v):
                env = _env({keys[2]: {"vcm": v}})
                s = cd.summarize(cd.load_points(env, 0.6))
                self.assertEqual(s["points_valid"], 44)
                self.assertEqual(len(s["rejected"]), 1)
                self.assertIn("vcm_meas", s["rejected"][0]["reason"])
        env = _env({keys[2]: {"drop": "vcm_meas"}})
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 44)
        self.assertIn("vcm_meas", s["rejected"][0]["reason"])

    def test_vcm_probe_controls(self):
        keys = cd.expected_keys()
        env = _env({keys[0]: {"vcm": 0.6 + 5e-7}, keys[1]: {"vcm": 0.7}})
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 44)
        self.assertIn("does not match", s["rejected"][0]["reason"])


if __name__ == "__main__":
    unittest.main()

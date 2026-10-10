"""Grading-adapter regression tests (issue #62). Stdlib only, no PDK, no
ngspice, writes nothing.

Synthetic envelopes in klt sim's own response shape stand in for campaign
output, so each rule in kltsim.grade is exercised in isolation: unit
conversion, Target vs Stretch, the absent power Target, the noise statistic, an
absent kickback-charge measurement, a missing corner, a collapsed grid, a
wrong/placeholder DUT, a deliberately tighter limit (negative control), and
the Monte-Carlo sampling basis.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import unittest

from kltsim import build, grade
from kltsim.benches import BENCHES, PROCESSES, SUPPLIES_V, TEMPERATURES_C

ROWS = json.loads((build.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
GRID = ROWS["grid"]


def _row(row_id: str) -> dict:
    return next(r for r in ROWS["rows"] if r["id"] == row_id)


def _spec(rows: list[dict]) -> dict:
    return {"grid": GRID, "rows": rows, "spec_source": ROWS["spec_source"]}


def _body(bench_name: str) -> str:
    return build.compose_body(BENCHES[bench_name], build.BATCH_OSDI_DIR)


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _corner(bench, process, supply, temp, values, statuses=None, sample=None):
    statuses = statuses or {}
    measurements = []
    for m in bench.measurements:
        if m.name not in values:
            continue
        value = values[m.name]
        status = statuses.get(m.name, "pass")
        measurements.append({"name": m.name, "value": value, "unit": m.unit,
                             "status": status, "margin": None})
    mismatch = bench.process_sections[0].endswith("_mismatch")
    section = f"mos_{process}_mismatch" if mismatch else f"mos_{process}"
    cid = f"{section}/{supply:.3f}V/{temp:g}C"
    if sample is not None:
        cid += f"/mc{sample}"
    return {
        "corner_id": cid,
        "process": section,
        "supply_v": {k: supply for k in bench.supply_keys},
        "temperature_c": temp,
        "status": "pass",
        "measurements": measurements,
        "diagnostics": [],
        "monte_carlo": None if sample is None else {"sample_index": sample},
    }


def _probe_values(bench, supply, temp):
    vals = {name: supply for name in bench.probes.get("supply", ())}
    vals[bench.probes["temperature"]] = temp
    return vals


def regeneration_envelope(body: str, td50=lambda p, v, t: 0.7, extra=None, drop=()):
    bench = BENCHES["regeneration"]
    corners = []
    for p in PROCESSES:
        for v in SUPPLIES_V:
            for t in TEMPERATURES_C:
                if (p, v, t) in drop:
                    continue
                vals = _probe_values(bench, v, t)
                vals.update({
                    "dout_od50_first": 1e-7, "dout_od1_first": 1e-7, "dout_od01_first": 1e-7,
                    "dout_od50_end": 1.0, "dout_od1_end": 1.0, "dout_od01_end": 1.0,
                    "td_od50_ns": td50(p, v, t), "td_od01_ns": 1.2, "tau_ps": 90.0,
                    "p_avg_uw": 25.0,
                })
                if extra:
                    vals.update(extra(p, v, t))
                corners.append(_corner(bench, p, v, t, vals))
    return {"schema_version": 3, "status": "pass", "corner_count": len(corners),
            "provenance": {"input": {"content_hash": _sha(body), "role": "netlist"}},
            "environment": {"netlist_source": "schematic"},
            "measurements": [], "corners": corners}


def kickback_envelope(body: str, q=lambda p, v, t: 20.0, include_q=True):
    bench = BENCHES["kickback"]
    corners = []
    for p in PROCESSES:
        for v in SUPPLIES_V:
            for t in TEMPERATURES_C:
                vals = _probe_values(bench, v, t)
                vals.update({"kick_sigdep_uv": 10.0, "kick_1k_peak_mv": 120.0,
                             "dout_1k_end": 1.0, "dout_float_small_end": 1.0,
                             "dout_float_big_end": 1.0})
                if include_q:
                    vals["qkick_fc"] = q(p, v, t)
                corners.append(_corner(bench, p, v, t, vals))
    return {"schema_version": 3, "status": "pass", "corner_count": len(corners),
            "provenance": {"input": {"content_hash": _sha(body), "role": "netlist"}},
            "environment": {"netlist_source": "schematic"},
            "measurements": [], "corners": corners}


def offset_envelope(body: str, n=60, stddev=lambda p, v, t: 3.0, mean=0.0):
    bench = BENCHES["offset_mc"]
    corners, by_corner = [], []
    for p in PROCESSES:
        for v in SUPPLIES_V:
            for t in TEMPERATURES_C:
                for k in range(n):
                    vals = _probe_values(bench, v, t)
                    vals.update({"lowcount": 16.0, "vos_mv": mean})
                    corners.append(_corner(bench, p, v, t, vals, sample=k))
                base = corners[-1]["corner_id"].rsplit("/mc", 1)[0]
                by_corner.append({"corner_id": base, "n": n, "errored": 0, "mean": mean,
                                  "stddev": stddev(p, v, t),
                                  "sigma_window": {"k": 3.0, "status": "pass"}})
    return {"schema_version": 3, "status": "pass", "corner_count": len(corners),
            "provenance": {"input": {"content_hash": _sha(body), "role": "netlist"}},
            "environment": {"netlist_source": "schematic"},
            "measurements": [{"name": "vos_mv", "unit": "mV",
                              "monte_carlo": {"by_corner": by_corner}}],
            "corners": corners}


def noise_envelope(body: str, kplus=lambda p, v, t: 76, kminus=lambda p, v, t: 4,
                   kzero=lambda p, v, t: 40, n=80, duplicate_at=None, drop=()):
    """Transient-noise Monte-Carlo envelope: per point, n one-trial samples
    whose 0/1 hit_* outcomes have the given counts of ones, unique raw noise
    draws (unless ``duplicate_at`` names a point whose sample 1 repeats
    sample 0's draw), and klt-style by_corner means."""
    bench = BENCHES["transient_noise"]
    corners = []
    by_corner = {"hit_plus": [], "hit_minus": [], "hit_zero": []}
    draw = 0
    for p in PROCESSES:
        for v in SUPPLIES_V:
            for t in TEMPERATURES_C:
                if (p, v, t) in drop:
                    continue
                counts = {"hit_plus": kplus(p, v, t), "hit_minus": kminus(p, v, t),
                          "hit_zero": kzero(p, v, t)}
                for k in range(n):
                    draw += 1
                    vals = _probe_values(bench, v, t)
                    vals.update({"vn0_a": draw * 1e-6, "vn0_b": -draw * 1e-6, "vn1_a": draw * 2e-6,
                                 "res_zero": 0.5, "res_plus": 0.5, "res_minus": 0.5})
                    if duplicate_at == (p, v, t) and k == 1:
                        vals.update({"vn0_a": (draw - 1) * 1e-6, "vn0_b": -(draw - 1) * 1e-6,
                                     "vn1_a": (draw - 1) * 2e-6})
                    for name, ones in counts.items():
                        vals[name] = 1.0 if k < ones else 0.0
                    corners.append(_corner(bench, p, v, t, vals, sample=k))
                base = corners[-1]["corner_id"].rsplit("/mc", 1)[0]
                for name, ones in counts.items():
                    by_corner[name].append({"corner_id": base, "n": n, "errored": 0,
                                            "mean": ones / n, "stddev": None})
    return {"schema_version": 3, "status": "pass", "corner_count": len(corners),
            "provenance": {"input": {"content_hash": _sha(body), "role": "netlist"}},
            "environment": {"netlist_source": "schematic"},
            "measurements": [{"name": name, "unit": "1", "monte_carlo": {"by_corner": entries}}
                             for name, entries in by_corner.items()],
            "corners": corners}


def _evidence(name, env, body):
    return grade.BenchEvidence(name=name, envelopes=[(name, env)], body_text=body)


class UnitTests(unittest.TestCase):
    def test_conversions(self):
        self.assertAlmostEqual(grade.convert(1.5e-9, "s", "ns"), 1.5)
        self.assertAlmostEqual(grade.convert(250.0, "ps", "ns"), 0.25)
        self.assertAlmostEqual(grade.convert(0.1, "mV", "uV"), 100.0)
        self.assertAlmostEqual(grade.convert(25e-15, "C", "fC"), 25.0)
        self.assertAlmostEqual(grade.convert(2.0e-5, "W", "uW"), 20.0)
        self.assertEqual(grade.convert(1.0, "mV rms", "mV"), 1.0)

    def test_incompatible_units_refused(self):
        with self.assertRaises(grade.UnitError):
            grade.convert(1.0, "ns", "mV")
        with self.assertRaises(grade.UnitError):
            grade.convert(1.0, "furlong", "mV")

    def test_unit_mismatch_never_passes(self):
        body = _body("regeneration")
        env = regeneration_envelope(body)
        for c in env["corners"]:
            for m in c["measurements"]:
                if m["name"] == "td_od50_ns":
                    m["unit"] = "mV"
        out = grade.grade(_spec([_row("3a")]),
                          {"regeneration": _evidence("regeneration", env, body)},
                          grade.load_dut_reference())
        self.assertEqual(out["rows"][0]["target_verdict"], grade.INCOMPLETE)

    def test_seconds_converted_to_row_unit(self):
        body = _body("regeneration")
        env = regeneration_envelope(body)
        for c in env["corners"]:
            for m in c["measurements"]:
                if m["name"] == "td_od50_ns":
                    m["unit"], m["value"] = "s", m["value"] * 1e-9
        out = grade.grade(_spec([_row("3a")]),
                          {"regeneration": _evidence("regeneration", env, body)},
                          grade.load_dut_reference())
        row = out["rows"][0]
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertAlmostEqual(row["target"]["binding"]["value"], 0.7)


class TargetStretchTests(unittest.TestCase):
    def setUp(self):
        self.body = _body("regeneration")
        self.dut = grade.load_dut_reference()

    def _grade(self, env, rows):
        return grade.grade(_spec(rows), {"regeneration": _evidence("regeneration", env, self.body)},
                           self.dut)

    def test_target_pass_stretch_fail_with_binding_corner(self):
        env = regeneration_envelope(self.body, td50=lambda p, v, t: 0.85 if p == "ss" else 0.6)
        row = self._grade(env, [_row("3a")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertEqual(row["stretch_verdict"], grade.FAIL)
        self.assertEqual(row["stretch"]["points_failing"], 9)
        self.assertTrue(row["stretch"]["binding"]["point"].startswith("ss_"))

    def test_tighter_limit_negative_control_fails(self):
        env = regeneration_envelope(self.body)
        tight = copy.deepcopy(_row("3a"))
        tight["target"] = {"max": 0.5}
        row = self._grade(env, [tight])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.FAIL)
        self.assertEqual(row["target"]["points_failing"], 45)

    def test_power_has_no_target(self):
        env = regeneration_envelope(self.body)
        row = self._grade(env, [_row("5b")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.NOT_SPECIFIED)
        self.assertEqual(row["stretch_verdict"], grade.FAIL)  # 25 uW > 20 uW
        out = self._grade(env, [_row("5b")])
        self.assertTrue(out["t1_item5"]["all_target_rows_pass"])  # nothing to block on

    def test_missing_corner_is_incomplete_not_pass(self):
        env = regeneration_envelope(self.body, drop={("ss", 1.08, -40)})
        row = self._grade(env, [_row("3a")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertEqual(row["target"]["points_valid"], 44)

    def test_missing_corner_does_not_hide_a_real_miss(self):
        env = regeneration_envelope(self.body, td50=lambda p, v, t: 2.0 if p == "ff" else 0.7,
                                    drop={("ss", 1.08, -40)})
        row = self._grade(env, [_row("3a")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.FAIL)

    def test_collapsed_grid_cannot_pass(self):
        env = regeneration_envelope(self.body)
        for c in env["corners"]:
            c["process"] = "mos_tt"  # every corner claims tt: a collapsed grid
        row = self._grade(env, [_row("3a")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        # The 9 surviving tt points each collide (issue #102): ambiguous, so
        # none of the 45 points is a usable value.
        self.assertEqual(row["target"]["points_valid"], 0)
        self.assertTrue(any("ambiguous duplicate" in n for n in row["notes"]))

    def test_supply_not_applied_is_untrusted(self):
        env = regeneration_envelope(self.body)
        for c in env["corners"]:
            for m in c["measurements"]:
                if m["name"] in ("vdd_meas", "vdda_meas"):
                    m["value"] = 1.2  # alter never reached the circuit
        row = self._grade(env, [_row("3a")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertEqual(row["target"]["points_valid"], 15)

    def test_errored_corner_is_not_a_value(self):
        env = regeneration_envelope(self.body)
        env["corners"][0]["status"] = "error"
        env["corners"][0]["diagnostics"] = [{"severity": "error", "code": "nonconvergence"}]
        row = self._grade(env, [_row("3a")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertIn("nonconvergence", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_wrong_decision_gate_invalidates_point(self):
        env = regeneration_envelope(self.body)
        for m in env["corners"][3]["measurements"]:
            if m["name"] == "dout_od50_end":
                m["value"], m["status"] = 0.0, "fail"
        row = self._grade(env, [_row("3a")])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)


class KickbackAndNoiseTests(unittest.TestCase):
    def setUp(self):
        self.body = _body("kickback")
        self.dut = grade.load_dut_reference()

    def test_absent_charge_measurement_is_not_pass(self):
        env = kickback_envelope(self.body, include_q=False)
        out = grade.grade(_spec([_row("4a"), _row("4b")]),
                          {"kickback": _evidence("kickback", env, self.body)}, self.dut)
        q, resid = out["rows"]
        self.assertEqual(q["target_verdict"], grade.INCOMPLETE)
        self.assertEqual(resid["target_verdict"], grade.PASS)  # residue is not charge
        self.assertFalse(out["t1_item5"]["all_target_rows_pass"])

    def test_charge_over_bound_fails_at_its_binding_point(self):
        env = kickback_envelope(self.body, q=lambda p, v, t: 31.5 if (p, v, t) == ("ff", 1.32, 125) else 20.0)
        row = grade.grade(_spec([_row("4a")]),
                          {"kickback": _evidence("kickback", env, self.body)}, self.dut)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.FAIL)
        self.assertEqual(row["target"]["binding"]["point"], "ff_125c_1.32v")
        self.assertEqual(row["stretch_verdict"], grade.FAIL)

    def test_peak_excursion_is_reported_not_graded(self):
        env = kickback_envelope(self.body)
        row = grade.grade(_spec([_row("4c")]),
                          {"kickback": _evidence("kickback", env, self.body)}, self.dut)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.NOT_SPECIFIED)
        self.assertEqual(row["report_verdict"], grade.REPORTED)

    def test_missing_bench_is_incomplete(self):
        out = grade.grade(_spec([_row("4a")]), {}, self.dut)
        self.assertEqual(out["rows"][0]["target_verdict"], grade.INCOMPLETE)


class TransientNoiseTests(unittest.TestCase):
    """Row 2: the DR-designated statistic (grid-wide mean of the per-point
    two-rung probit-slope sigma) from klt per-corner means."""

    def setUp(self):
        self.body = _body("transient_noise")
        self.dut = grade.load_dut_reference()

    def _grade(self, env, rows=None):
        return grade.grade(_spec(rows or [_row("2")]),
                           {"transient_noise": _evidence("transient_noise", env, self.body)}, self.dut)

    @staticmethod
    def _sigma(kp, km, n=80):
        z = grade.NormalDist().inv_cdf
        return 2.0 / (z(kp / n) - z(km / n))

    def test_slope_estimator_matches_original(self):
        # p = Phi(+-1) => sigma = od_x exactly; offset-immune: a shifted pair
        # with the same probit gap gives the same sigma.
        phi = grade.NormalDist().cdf
        self.assertAlmostEqual(grade.probit_slope_sigma(phi(1), phi(-1), 1.0), 1.0, places=9)
        self.assertAlmostEqual(grade.probit_slope_sigma(phi(1.7), phi(-0.3), 1.0), 1.0, places=9)
        with self.assertRaises(ValueError):
            grade.probit_slope_sigma(1.0, 0.2, 1.0)  # saturated rung
        with self.assertRaises(ValueError):
            grade.probit_slope_sigma(0.2, 0.8, 1.0)  # inverted rungs

    def test_failed_noise_bound_fails_both_columns(self):
        row = self._grade(noise_envelope(self.body, kplus=lambda *a: 67, kminus=lambda *a: 13))["rows"][0]
        self.assertAlmostEqual(row["target"]["grid_mean"], self._sigma(67, 13))
        self.assertGreater(row["target"]["grid_mean"], 1.0)
        self.assertEqual(row["target_verdict"], grade.FAIL)
        self.assertEqual(row["stretch_verdict"], grade.FAIL)
        self.assertEqual(row["target"]["binding"]["point"], "grid-wide mean (DR-designated statistic)")

    def test_target_pass_stretch_fail(self):
        row = self._grade(noise_envelope(self.body))["rows"][0]  # 76/4 of 80: sigma ~0.608 mV
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertEqual(row["stretch_verdict"], grade.FAIL)

    def test_one_noisy_point_moves_the_mean_not_a_per_point_bound(self):
        # The bound is on the grid MEAN: one point above 1 mV does not fail it.
        env = noise_envelope(self.body, kplus=lambda p, v, t: 67 if (p, v, t) == ("tt", 1.08, 125) else 78,
                             kminus=lambda p, v, t: 13 if (p, v, t) == ("tt", 1.08, 125) else 2)
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertEqual(row["target"]["worst_point"]["point"], "tt_125c_1.08v")

    def test_tighter_limit_negative_control_fails(self):
        tight = copy.deepcopy(_row("2"))
        tight["target"] = {"max": 0.5}
        row = self._grade(noise_envelope(self.body), rows=[tight])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.FAIL)

    def test_saturated_rung_is_incomplete_not_pass(self):
        env = noise_envelope(self.body, kplus=lambda p, v, t: 80 if p == "ff" else 78, kminus=lambda *a: 2)
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertEqual(row["stretch_verdict"], grade.INCOMPLETE)
        self.assertIn("saturated", row["target"]["points_missing_or_invalid"][0]["why"])
        self.assertIn("partial_mean_ungraded", row["target"])
        self.assertNotIn("binding", row["target"])

    def test_duplicated_noise_draw_is_not_independent(self):
        env = noise_envelope(self.body, kplus=lambda *a: 78, kminus=lambda *a: 2, duplicate_at=("ss", 1.2, 27))
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        bad = row["target"]["points_missing_or_invalid"]
        self.assertEqual([b["point"] for b in bad], ["ss_27c_1.20v"])
        self.assertIn("not independent", bad[0]["why"])

    def test_draw_shared_across_points_is_reported_not_invalidating(self):
        # Separate batch jobs can reuse a noise stream (pid-seeded TRNOISE):
        # each point stays valid, the correlation is disclosed.
        env = noise_envelope(self.body, kplus=lambda *a: 78, kminus=lambda *a: 2)
        first, second = env["corners"][0], env["corners"][80]  # sample 0 of two points
        self.assertNotEqual(first["corner_id"].rsplit("/mc", 1)[0], second["corner_id"].rsplit("/mc", 1)[0])
        src = {m["name"]: m["value"] for m in first["measurements"]}
        for m in second["measurements"]:
            if m["name"] in ("vn0_a", "vn0_b", "vn1_a"):
                m["value"] = src[m["name"]]
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertEqual(row["target"]["points_valid"], 45)
        self.assertTrue(any("ANOTHER grid point" in n for n in row["notes"]))
        shared = [d["samples_sharing_a_draw_with_another_point"] for d in row["monte_carlo_per_point"]]
        self.assertEqual(sum(shared), 2)

    def test_noise_not_injected_is_incomplete(self):
        # zero-overdrive rung all one way: the injection guard trips.
        env = noise_envelope(self.body, kplus=lambda *a: 78, kminus=lambda *a: 2, kzero=lambda *a: 0)
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertIn("not demonstrably injected", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_short_sample_basis_is_incomplete(self):
        row = self._grade(noise_envelope(self.body, kplus=lambda *a: 70, kminus=lambda *a: 2, n=79))["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertIn("N = 80", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_missing_point_cannot_pass(self):
        env = noise_envelope(self.body, kplus=lambda *a: 78, kminus=lambda *a: 2, drop={("sf", 1.32, -40)})
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertEqual(row["target"]["points_valid"], 44)

    def test_absent_bench_blocks_item5(self):
        out = grade.grade(_spec([_row("2")]), {}, self.dut)
        self.assertEqual(out["rows"][0]["target_verdict"], grade.INCOMPLETE)
        self.assertFalse(out["t1_item5"]["all_target_rows_pass"])

    def test_retained_record_is_carried_as_cross_check(self):
        row = self._grade(noise_envelope(self.body))["rows"][0]
        self.assertEqual(row["retained_record"]["recorded_verdict_target"], "NOT MET")


class DutTests(unittest.TestCase):
    def setUp(self):
        self.dut = grade.load_dut_reference()

    def _grade(self, body, env):
        return grade.grade(_spec([_row("3a")]),
                           {"regeneration": _evidence("regeneration", env, body)}, self.dut)["rows"][0]

    def test_real_dut_accepted(self):
        body = _body("regeneration")
        self.assertEqual(self._grade(body, regeneration_envelope(body))["target_verdict"], grade.PASS)

    def test_placeholder_dut_rejected(self):
        body = _body("regeneration")
        placeholder = (build.SIM_DIR / "dut" / "placeholder_comparator.spice").read_text(encoding="utf-8")
        path, sha, embedded = build.extract_dut_block(body)
        fake = body.replace(embedded.rstrip("\n"), placeholder.rstrip("\n"))
        fake = fake.replace(sha, hashlib.sha256(placeholder.encode("utf-8")).hexdigest())
        row = self._grade(fake, regeneration_envelope(fake))
        self.assertEqual(row["target_verdict"], grade.INVALID_DUT)

    def test_edited_dut_rejected(self):
        body = _body("regeneration")
        edited = body.replace("w=12u l=0.34u", "w=24u l=0.34u", 1)
        row = self._grade(edited, regeneration_envelope(edited))
        self.assertEqual(row["target_verdict"], grade.INVALID_DUT)

    def test_envelope_of_a_different_body_rejected(self):
        body = _body("regeneration")
        env = regeneration_envelope(body + "* trailing edit\n")
        row = self._grade(body, env)
        self.assertEqual(row["target_verdict"], grade.INVALID_DUT)

    def test_non_schematic_binding_rejected(self):
        body = _body("regeneration")
        dut = grade.DutReference(self.dut.netlist_bytes, self.dut.netlist_rel,
                                 dict(self.dut.dut_json, provenance="placeholder"))
        row = grade.grade(_spec([_row("3a")]),
                          {"regeneration": _evidence("regeneration", regeneration_envelope(body), body)},
                          dut)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INVALID_DUT)

    def test_build_refuses_non_schematic_binding(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "dut.json"
            binding = dict(self.dut.dut_json, provenance="placeholder")
            binding["netlist"] = str(build.SIM_DIR / "dut" / "placeholder_comparator.spice")
            fake.write_text(json.dumps(binding), encoding="utf-8")
            with self.assertRaises(build.BuildError):
                build.compose_body(BENCHES["regeneration"], "/x", dut_json=fake)


class MonteCarloTests(unittest.TestCase):
    def setUp(self):
        self.body = _body("offset_mc")
        self.dut = grade.load_dut_reference()

    def _grade(self, env, rows=None):
        return grade.grade(_spec(rows or [_row("1")]),
                           {"offset_mc": _evidence("offset_mc", env, self.body)}, self.dut)

    def test_dr_basis_statistic(self):
        # s = 3 mV Bessel at N = 60, 3 mV staircase step:
        expected = 3 * math.sqrt(9.0 * 59 / 60 - 9.0 / 12)
        self.assertAlmostEqual(grade.three_sigma_dr_basis(60, 3.0, 3.0), expected)
        self.assertEqual(grade.three_sigma_dr_basis(60, 0.5, 3.0), 0.0)
        self.assertIsNone(grade.three_sigma_dr_basis(1, 3.0, 3.0))

    def test_target_pass_stretch_fail(self):
        env = offset_envelope(self.body, stddev=lambda p, v, t: 3.6 if t == 125 else 2.5)
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertEqual(row["stretch_verdict"], grade.FAIL)
        self.assertTrue(row["stretch"]["binding"]["point"].endswith("_125c_1.08v")
                        or "_125c_" in row["stretch"]["binding"]["point"])

    def test_target_fail(self):
        env = offset_envelope(self.body, stddev=lambda p, v, t: 6.0 if p == "ff" else 3.0)
        self.assertEqual(self._grade(env)["rows"][0]["target_verdict"], grade.FAIL)

    def test_short_sample_basis_is_incomplete(self):
        env = offset_envelope(self.body, n=30)
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertIn("N = 60", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_zero_spread_is_sabotage_not_pass(self):
        env = offset_envelope(self.body, stddev=lambda p, v, t: 0.0)
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)

    def test_out_of_range_draw_is_untrusted(self):
        env = offset_envelope(self.body)
        for m in env["corners"][5]["measurements"]:
            if m["name"] == "lowcount":
                m["value"], m["status"] = 0.0, "fail"
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)

    def test_coverage_row(self):
        body_r, body_k, body_n = _body("regeneration"), _body("kickback"), _body("transient_noise")
        benches = {
            "regeneration": _evidence("regeneration", regeneration_envelope(body_r), body_r),
            "kickback": _evidence("kickback", kickback_envelope(body_k), body_k),
            "offset_mc": _evidence("offset_mc", offset_envelope(self.body), self.body),
            "transient_noise": _evidence("transient_noise", noise_envelope(body_n), body_n),
        }
        out = grade.grade(_spec([_row("5a")]), benches, self.dut)
        self.assertEqual(out["rows"][0]["target_verdict"], grade.PASS)
        # a Monte-Carlo bench short of its ratified N does not cover the grid
        short = dict(benches, transient_noise=_evidence(
            "transient_noise", noise_envelope(body_n, kplus=lambda *a: 70, n=79), body_n))
        out = grade.grade(_spec([_row("5a")]), short, self.dut)
        self.assertEqual(out["rows"][0]["target_verdict"], grade.INCOMPLETE)
        benches["kickback"] = _evidence("kickback", regeneration_envelope(body_k), body_k)
        benches["kickback"].envelopes[0][1]["corners"] = benches["kickback"].envelopes[0][1]["corners"][:20]
        out = grade.grade(_spec([_row("5a")]), benches, self.dut)
        self.assertEqual(out["rows"][0]["target_verdict"], grade.INCOMPLETE)


class RowsInventoryTests(unittest.TestCase):
    """rows.json must carry DR-0002's bounds exactly (no relaxation)."""

    def test_ratified_bounds(self):
        bounds = {r["id"]: (r["target"], r["stretch"]) for r in ROWS["rows"]}
        self.assertEqual(bounds["1"], ({"max": 15.0}, {"max": 8.0}))
        self.assertEqual(bounds["2"], ({"max": 1.0}, {"max": 0.6}))
        self.assertEqual(bounds["3a"], ({"max": 1.5}, {"max": 0.8}))
        self.assertEqual(bounds["3b"], ({"max": 250.0}, None))
        self.assertEqual(bounds["3c"], ({"max": 2.0}, None))
        self.assertEqual(bounds["4a"], ({"max": 25.0}, {"max": 8.0}))
        self.assertEqual(bounds["4b"], ({"max": 100.0}, {"max": 30.0}))
        self.assertEqual(bounds["4c"], (None, None))
        self.assertEqual(bounds["5b"], (None, {"max": 20.0}))

    def test_request_limits_are_targets_only(self):
        for row in ROWS["rows"]:
            ev = row["evidence"]
            if ev["kind"] != "klt_sim":
                continue
            if ev["reduction"] == "mc_probit_slope_grid_mean":
                # A bound on a population statistic must never be imposed
                # on each 0/1 trial: the outcome probes carry no limits.
                for name in (ev["plus"], ev["minus"], ev["zero"]):
                    self.assertIsNone(BENCHES[ev["bench"]].measurement(name).limits, name)
                continue
            meas = BENCHES[ev["bench"]].measurement(ev["measurement"])
            target = row["target"]
            if target is None:
                self.assertIsNone(meas.limits, row["id"])
            elif row["id"] != "1":
                self.assertEqual(meas.limits, target, row["id"])
            else:  # per-draw offset: +/- the 3-sigma Target, window k = 3
                self.assertEqual(meas.limits, {"min": -15.0, "max": 15.0})
                self.assertEqual(meas.k_sigma, 3.0)


class NonFiniteEvidenceTests(unittest.TestCase):
    """Issue #101: NaN / +-inf / non-numeric evidence is never a usable value."""

    BAD = (float("nan"), float("inf"), float("-inf"), "garbage", "nan")

    def setUp(self):
        self.dut = grade.load_dut_reference()
        self.reg_body = _body("regeneration")
        self.mc_body = _body("offset_mc")
        self.noise_body = _body("transient_noise")

    def _reg(self, env, rows=None):
        return grade.grade(_spec(rows or [_row("3a")]),
                           {"regeneration": _evidence("regeneration", env, self.reg_body)},
                           self.dut)

    @staticmethod
    def _set(corner, name, value):
        for m in corner["measurements"]:
            if m["name"] == name:
                m["value"] = value

    def test_all_nan_grid_is_not_pass(self):
        for bad in self.BAD:
            env = regeneration_envelope(self.reg_body)
            for c in env["corners"]:
                self._set(c, "td_od50_ns", bad)
            row = self._reg(env)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.INCOMPLETE, bad)
            self.assertEqual(row["target"]["points_valid"], 0, bad)
            self.assertEqual(row["stretch_verdict"], grade.INCOMPLETE, bad)

    def test_negative_infinity_does_not_pass_upper_bound(self):
        env = regeneration_envelope(self.reg_body)
        self._set(env["corners"][0], "td_od50_ns", float("-inf"))
        row = self._reg(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertEqual(row["target"]["points_valid"], 44)
        self.assertEqual(row["target"]["points_expected"], 45)
        self.assertIn("not finite", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_invalid_point_does_not_hide_a_real_miss(self):
        env = regeneration_envelope(self.reg_body, td50=lambda p, v, t: 2.0 if p == "ff" else 0.7)
        self._set(env["corners"][0], "td_od50_ns", float("nan"))
        row = self._reg(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.FAIL)
        self.assertEqual(row["target"]["points_valid"], 44)
        self.assertEqual(len(row["target"]["points_missing_or_invalid"]), 1)

    def test_finite_campaign_unchanged(self):
        row = self._reg(regeneration_envelope(self.reg_body))["rows"][0]
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertEqual(row["target"]["points_valid"], 45)

    def test_nonfinite_probes_and_gates_invalidate_point(self):
        for name in ("vdd_meas", "dout_od50_end", "dout_od50_first"):
            for bad in self.BAD:
                env = regeneration_envelope(self.reg_body)
                self._set(env["corners"][3], name, bad)
                row = self._reg(env)["rows"][0]
                self.assertEqual(row["target_verdict"], grade.INCOMPLETE, (name, bad))
                self.assertEqual(row["target"]["points_valid"], 44, (name, bad))
        env = regeneration_envelope(self.reg_body)
        self._set(env["corners"][3], BENCHES["regeneration"].probes["temperature"], float("nan"))
        self.assertEqual(self._reg(env)["rows"][0]["target"]["points_valid"], 44)

    def test_nonfinite_corner_metadata_is_a_missing_point_not_an_exception(self):
        env = regeneration_envelope(self.reg_body)
        env["corners"][0]["temperature_c"] = float("nan")
        row = self._reg(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)

    def test_grade_values_rejects_nonfinite_directly(self):
        key = ("tt", 1.2, 27.0)
        for bad in (float("nan"), float("-inf"), float("inf")):
            out = grade.grade_values([grade.CornerValue(key, bad, "x")], {"max": 1.0})
            self.assertEqual(out["verdict"], grade.INCOMPLETE)

    def test_mc_nonfinite_stddev_is_not_a_value(self):
        for bad in self.BAD:
            env = offset_envelope(self.mc_body)
            env["measurements"][0]["monte_carlo"]["by_corner"][0]["stddev"] = bad
            row = grade.grade(_spec([_row("1")]),
                              {"offset_mc": _evidence("offset_mc", env, self.mc_body)},
                              self.dut)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.INCOMPLETE, bad)
            self.assertEqual(row["target"]["points_valid"], 44, bad)

    def test_mc_nonfinite_mean_or_n_is_not_a_value(self):
        for field in ("mean", "n"):
            env = offset_envelope(self.mc_body)
            env["measurements"][0]["monte_carlo"]["by_corner"][0][field] = float("nan")
            row = grade.grade(_spec([_row("1")]),
                              {"offset_mc": _evidence("offset_mc", env, self.mc_body)},
                              self.dut)["rows"][0]
            self.assertNotEqual(row["target_verdict"], grade.PASS, field)
            self.assertEqual(row["target"]["points_valid"], 44, field)

    def _noise(self, env):
        return grade.grade(_spec([_row("2")]),
                           {"transient_noise": _evidence("transient_noise", env, self.noise_body)},
                           self.dut)["rows"][0]

    def test_grid_mean_nonfinite_population_statistic_is_incomplete(self):
        for field in ("mean", "n"):
            for bad in (float("nan"), float("inf"), float("-inf")):
                env = noise_envelope(self.noise_body)
                for m in env["measurements"]:
                    if m["name"] == "hit_plus":
                        m["monte_carlo"]["by_corner"][0][field] = bad
                row = self._noise(env)
                self.assertEqual(row["target_verdict"], grade.INCOMPLETE, (field, bad))
                self.assertEqual(row["target"]["points_valid"], 44, (field, bad))
                self.assertNotIn("grid_mean", row["target"])

    def test_grid_mean_reducer_rejects_nonfinite_sigma(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            details = [{"point": f"p{i}", "corner_id": f"c{i}", "sigma": 1.0, "problem": None}
                       for i in range(3)]
            details[1]["sigma"] = bad
            out = grade.grade_grid_mean(details, {"max": 5.0})
            self.assertEqual(out["verdict"], grade.INCOMPLETE, bad)
            self.assertEqual(out["points_valid"], 2)
            self.assertNotIn("grid_mean", out)
            single = [{"point": "p", "corner_id": "c", "sigma": bad, "problem": None}]
            self.assertEqual(grade.grade_grid_mean(single, {"max": 5.0})["verdict"], grade.INCOMPLETE)

    def test_noise_independence_probe_nan_is_not_a_draw(self):
        env = noise_envelope(self.noise_body)
        for m in env["corners"][0]["measurements"]:
            if m["name"] == "vn0_a":
                m["value"] = float("nan")
        self.assertEqual(self._noise(env)["target_verdict"], grade.INCOMPLETE)

    def test_report_json_is_strict(self):
        env = regeneration_envelope(self.reg_body)
        self._set(env["corners"][0], "td_od50_ns", float("nan"))
        self._set(env["corners"][1], "td_od50_ns", float("-inf"))
        text = grade.dumps_strict(self._reg(env))
        for token in ("NaN", "Infinity"):
            self.assertNotIn(token, text)
        json.loads(text, parse_constant=lambda c: self.fail(f"non-standard constant {c}"))
        # even if a non-finite float leaks into a report, serialisation is strict
        text = grade.dumps_strict({"x": float("nan"), "y": [float("inf")]})
        self.assertEqual(json.loads(text), {"x": None, "y": [None]})

    def test_noise_report_json_is_strict(self):
        env = noise_envelope(self.noise_body)
        for m in env["measurements"]:
            if m["name"] == "hit_zero":
                m["monte_carlo"]["by_corner"][0]["mean"] = float("nan")
        text = grade.dumps_strict(self._noise(env))
        json.loads(text, parse_constant=lambda c: self.fail(f"non-standard constant {c}"))


class DuplicateEvidenceTests(unittest.TestCase):
    """Issue #102: a repeated PVT point or population summary is ambiguous
    evidence -- diagnosed, never selected by envelope order."""

    P0, V0, T0 = PROCESSES[0], SUPPLIES_V[0], TEMPERATURES_C[0]

    def setUp(self):
        self.dut = grade.load_dut_reference()
        self.body = _body("regeneration")

    def _bench(self, envs, name="regeneration", body=None):
        return grade.BenchEvidence(name=name, envelopes=envs, body_text=body or self.body)

    def _grade(self, envs, rows=None):
        return grade.grade(_spec(rows or [_row("3a")]),
                           {"regeneration": self._bench(envs)}, self.dut)

    def _partial(self, td50, only=None):
        """An envelope holding only the given process (or everything)."""
        env = regeneration_envelope(self.body, td50=td50)
        if only is not None:
            env["corners"] = [c for c in env["corners"] if c["process"] == f"mos_{only}"
                              or c["process"] == only]
            env["corner_count"] = len(env["corners"])
        return env

    def _point_env(self, value):
        """Envelope with only the (P0, V0, T0) point, at td_od50_ns = value."""
        env = self._partial(lambda p, v, t: value)
        env["corners"] = [c for c in env["corners"]
                          if c["corner_id"].endswith(f"{self.V0:.3f}V/{self.T0:g}C")
                          and c["process"].endswith(self.P0)]
        env["corner_count"] = len(env["corners"])
        self.assertEqual(len(env["corners"]), 1)
        return env

    def _td_bound(self, envs):
        row = self._grade(envs)["rows"][0]
        return row

    def test_fail_then_pass_across_envelopes_never_selected(self):
        full = self._partial(lambda p, v, t: 0.7)
        bad = self._point_env(5.0)  # clearly failing duplicate of one point
        for envs in ([("a", full), ("b", bad)], [("b", bad), ("a", full)]):
            row = self._grade(envs)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
            self.assertEqual(row["target"]["points_valid"], 44)
            why = [m["why"] for m in row["target"]["points_missing_or_invalid"]]
            self.assertEqual(len(why), 1)
            self.assertIn("a:", why[0])
            self.assertIn("b:", why[0])

    def test_pass_then_fail_same_as_fail_then_pass(self):
        full = self._partial(lambda p, v, t: 0.7)
        bad = self._point_env(5.0)
        fwd = self._grade([("a", full), ("b", bad)])["rows"][0]
        rev = self._grade([("b", bad), ("a", full)])["rows"][0]
        self.assertEqual(fwd["target_verdict"], rev["target_verdict"])
        self.assertEqual(fwd["stretch_verdict"], rev["stretch_verdict"])
        self.assertEqual(sorted(fwd["notes"]), sorted(rev["notes"]))
        self.assertTrue(any("ambiguous duplicate" in n for n in fwd["notes"]))

    def test_duplicate_within_one_envelope_is_diagnosed(self):
        env = self._partial(lambda p, v, t: 0.7)
        env["corners"].append(copy.deepcopy(env["corners"][0]))
        row = self._grade([("only", env)])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertTrue(any("ambiguous duplicate" in n for n in row["notes"]))
        self.assertIn("only:", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_identical_looking_duplicate_is_still_rejected(self):
        a = self._partial(lambda p, v, t: 0.7)
        b = self._point_env(0.7)
        row = self._grade([("a", a), ("b", b)])["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)

    def test_unambiguous_failure_still_fails_with_collision_present(self):
        full = self._partial(lambda p, v, t: 5.0 if p == "ss" else 0.7)
        dup = self._point_env(0.7)  # collides at the (non-failing) first point
        for envs in ([("a", full), ("b", dup)], [("b", dup), ("a", full)]):
            row = self._grade(envs)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.FAIL)
            self.assertTrue(any("ambiguous duplicate" in n for n in row["notes"]))

    def test_disjoint_process_partitions_grade_normally(self):
        parts = [(p, self._partial(lambda pp, v, t: 0.7, only=p)) for p in PROCESSES]
        for envs in (parts, parts[::-1]):
            row = self._grade(envs)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.PASS)
            self.assertEqual(row["target"]["points_valid"], 45)
            self.assertNotIn("notes", row)

    # -- population summaries ------------------------------------------------

    def _offset_grade(self, envs, rows=None):
        ev = grade.BenchEvidence(name="offset_mc", envelopes=envs, body_text=_body("offset_mc"))
        return grade.grade(_spec(rows or [_row("1")]), {"offset_mc": ev}, self.dut)

    def test_duplicate_offset_summary_cannot_change_statistic(self):
        body = _body("offset_mc")
        good = offset_envelope(body, stddev=lambda p, v, t: 2.5)
        other = offset_envelope(body, stddev=lambda p, v, t: 9.0)  # would FAIL if picked
        # Keep only the summaries (drop the sample corners) in the second envelope.
        other["corners"] = []
        summaries = []
        for envs in ([("a", good), ("b", other)], [("b", other), ("a", good)]):
            row = self._offset_grade(envs)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
            self.assertEqual(row["target"]["points_valid"], 0)
            self.assertTrue(all("duplicate population summary" in m["why"]
                                for m in row["target"]["points_missing_or_invalid"]))
            summaries.append(sorted(row["notes"]))
        self.assertEqual(summaries[0], summaries[1])

    def test_offset_partitions_with_distinct_summaries_grade(self):
        body = _body("offset_mc")
        env = offset_envelope(body)
        halves = []
        for keep in (lambda p: p == PROCESSES[0], lambda p: p != PROCESSES[0]):
            e = copy.deepcopy(env)
            e["corners"] = [c for c in e["corners"] if keep(c["process"].split("_")[1])]
            e["measurements"][0]["monte_carlo"]["by_corner"] = [
                b for b in e["measurements"][0]["monte_carlo"]["by_corner"]
                if keep(b["corner_id"].split("/")[0].split("_")[1])]
            halves.append(e)
        row = self._offset_grade([("a", halves[0]), ("b", halves[1])])["rows"][0]
        self.assertEqual(row["target"]["points_valid"], 45)

    def test_duplicate_noise_summary_is_incomplete_in_either_order(self):
        body = _body("transient_noise")
        a = noise_envelope(body)
        b = noise_envelope(body, kplus=lambda p, v, t: 50)
        b["corners"] = []
        out = []
        for envs in ([("a", a), ("b", b)], [("b", b), ("a", a)]):
            ev = grade.BenchEvidence(name="transient_noise", envelopes=envs, body_text=body)
            row = grade.grade(_spec([_row("2")]), {"transient_noise": ev}, self.dut)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
            self.assertEqual(row["target"]["points_valid"], 0)
            self.assertTrue(all("duplicate population summary" in (d["problem"] or "")
                                for d in row["monte_carlo_per_point"]))
            out.append(sorted(row["notes"]))
        self.assertEqual(out[0], out[1])

class CampaignChainTests(unittest.TestCase):
    """Saved request/invocation provenance at the loading boundary (issue #107)."""

    SRC = build.EXPERIMENT_DIR / "campaigns" / "20261009-d73a9ac"
    SPLIT = "offset_mc.mos_tt_mismatch"

    def setUp(self):
        import shutil
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        for f in self.SRC.iterdir():
            if f.is_file() and f.suffix in (".json", ".spice") and f.name not in (
                    "grading.json",):
                shutil.copy(f, self.dir / f.name)

    def _load(self, bench="offset_mc"):
        return grade.load_campaign(self.dir)[bench]

    def _edit_invocation(self, tag, **changes):
        path = self.dir / f"{tag}.invocation.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data), encoding="utf-8")

    def _edit_request(self, tag, mutate):
        path = self.dir / f"{tag}.request.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _assert_rejected(self, bench, needle):
        ev = self._load(bench)
        self.assertTrue(any(needle in p for p in ev.chain_problems), ev.chain_problems)
        return ev

    def test_intact_chain_reports_checked_hashes(self):
        for bench in BENCHES:
            ev = self._load(bench)
            self.assertEqual(ev.chain_problems, [], bench)
            for tag, _ in ev.envelopes:
                checked = ev.chain_checked[tag]
                self.assertEqual(checked["request_sha256"], checked["invocation_request_sha256"])
                self.assertEqual(checked["envelope_sha256"], ev.envelope_files[tag])

    def test_mutated_request_is_rejected_with_unchanged_body(self):
        body_before = (self.dir / "offset_mc.body.spice").read_bytes()
        path = self.dir / f"{self.SPLIT}.request.json"
        path.write_bytes(path.read_bytes() + b" ")  # whitespace only: bytes, not semantics
        self._assert_rejected("offset_mc", f"{self.SPLIT}: request_sha256 mismatch")
        self.assertEqual(body_before, (self.dir / "offset_mc.body.spice").read_bytes())

    def test_substituted_envelope_with_stale_invocation_hash(self):
        path = self.dir / f"{self.SPLIT}.envelope.json"
        path.write_bytes(path.read_bytes() + b"\n")
        self._assert_rejected("offset_mc", f"{self.SPLIT}: envelope_sha256 mismatch")

    def test_bad_invocation_hash_fields(self):
        for bad in ("nothex", "A" * 64, None):
            self._edit_invocation(self.SPLIT, request_sha256=bad)
            self._assert_rejected("offset_mc", "request_sha256 is missing or not")
        self._edit_invocation(self.SPLIT, envelope_sha256=5)
        self._assert_rejected("offset_mc", "envelope_sha256 is missing or not")

    def test_missing_and_malformed_companions(self):
        (self.dir / "regeneration.invocation.json").unlink()
        self._assert_rejected("regeneration", "invocation regeneration.invocation.json is missing")
        (self.dir / "regeneration.request.json").unlink()
        self._assert_rejected("regeneration", "request regeneration.request.json is missing")
        (self.dir / "kickback.invocation.json").write_text("{not json", encoding="utf-8")
        self._assert_rejected("kickback", "is not valid JSON")
        (self.dir / "kickback.request.json").write_text("[]", encoding="utf-8")
        self._assert_rejected("kickback", "is not a JSON object")
        (self.dir / "transient_noise.mos_tt.envelope.json").write_text("oops", encoding="utf-8")
        ev = self._load("transient_noise")
        self.assertTrue(any("envelope" in p and "not valid JSON" in p for p in ev.chain_problems))

    def test_semantic_request_mismatches(self):
        self._edit_request("regeneration", lambda d: d.update(netlist="other.body.spice"))
        self._assert_rejected("regeneration", "request names body 'other.body.spice'")

    def _resign(self, tag):
        self._edit_invocation(tag, request_sha256=hashlib.sha256(
            (self.dir / f"{tag}.request.json").read_bytes()).hexdigest())

    def test_wrong_grid_and_run_count_even_when_rehashed(self):
        self._edit_request(self.SPLIT, lambda d: d["corners"].update(temperature_c=[27]))
        self._resign(self.SPLIT)
        self._assert_rejected("offset_mc", "request corners")
        self.setUp()
        self._edit_request(self.SPLIT, lambda d: d["monte_carlo"].update(n=5))
        self._resign(self.SPLIT)
        self._assert_rejected("offset_mc", "request monte_carlo")

    def test_split_request_must_match_its_own_slice(self):
        other = "offset_mc.mos_ss_mismatch"
        data = (self.dir / f"{other}.request.json").read_bytes()
        (self.dir / f"{self.SPLIT}.request.json").write_bytes(data)
        self._resign(self.SPLIT)
        self._assert_rejected("offset_mc", "request corners")

    def test_rejected_chain_blocks_met_rows_and_is_reported(self):
        (self.dir / "regeneration.request.json").write_bytes(b"{}")
        benches = grade.load_campaign(self.dir)
        result = grade.grade(_spec([_row("3a")]), benches, grade.load_dut_reference())
        row = result["rows"][0]
        self.assertEqual(row["target_verdict"], grade.REJECTED_EVIDENCE)
        self.assertFalse(result["t1_item5"]["all_target_rows_pass"])
        self.assertTrue(result["benches"]["regeneration"]["chain_problems"])
        self.assertIn("rejected evidence", grade.render_markdown(result))

    def test_in_memory_evidence_needs_no_companions(self):
        body = _body("regeneration")
        ev = _evidence("regeneration", regeneration_envelope(body), body)
        self.assertEqual(ev.chain_problems, [])
        row = grade.grade(_spec([_row("3a")]), {"regeneration": ev},
                          grade.load_dut_reference())["rows"][0]
        self.assertNotEqual(row["target_verdict"], grade.REJECTED_EVIDENCE)


class MeasurementUniquenessTests(unittest.TestCase):
    """Issue #150: a measurement name repeated within ONE corner is ambiguous
    evidence. The point is rejected whatever the copies' order or values
    (never first, last or worst), and a malformed measurement entry is a
    diagnosed invalid point, never an unhandled exception."""

    DUP = "duplicate measurement name(s)"

    def setUp(self):
        self.dut = grade.load_dut_reference()
        self.body = _body("regeneration")

    def _grade(self, env, rows=None, name="regeneration", body=None):
        body = body or self.body
        return grade.grade(_spec(rows or [_row("3a")]), {name: _evidence(name, env, body)}, self.dut)

    @staticmethod
    def _dup(corner, name, front=False, **override):
        """Add a second ``name`` entry (with ``override``) before or after the original."""
        ms = corner["measurements"]
        orig = next(m for m in ms if m["name"] == name)
        copy_ = dict(orig, **override)
        if front:
            ms.insert(0, copy_)
        else:
            ms.append(copy_)

    def _both_orders(self, name, corner_index=0, envelope=None, **override):
        """Two envelopes whose corner ``corner_index`` carries the original and
        an overridden copy of ``name``, in either list order."""
        out = []
        for front in (False, True):
            env = (envelope or (lambda: regeneration_envelope(self.body)))()
            self._dup(env["corners"][corner_index], name, front=front, **override)
            out.append(env)
        return out

    def _assert_rejected(self, row, name, points_valid=44):
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertNotEqual(row["stretch_verdict"], grade.PASS)
        self.assertEqual(row["target"]["points_valid"], points_valid)
        why = row["target"]["points_missing_or_invalid"][0]["why"]
        self.assertIn(self.DUP, why)
        self.assertIn(f"{name} (x2)", why)
        self.assertIn("no value selected", why)

    # -- the validated lookup itself ------------------------------------------

    def test_measurement_index_unique_and_scoped(self):
        corner = {"measurements": [{"name": "a", "value": 1}, {"name": "b", "value": 2},
                                   {"name": "a", "value": 1}]}
        index, bad = grade.measurement_index(corner)
        self.assertIsNone(index)
        self.assertIn("a (x2)", bad)
        index, bad = grade.measurement_index(corner, unique={"b"})
        self.assertIsNone(bad)  # scoped check (issue #122 screening policy)
        index, bad = grade.measurement_index({"measurements": None})
        self.assertEqual((index, bad), ({}, None))
        index, bad = grade.measurement_index({"measurements": [{"name": "a"}, {"name": "b"}]})
        self.assertEqual(sorted(index), ["a", "b"])

    # -- deterministic per-corner grading -------------------------------------

    def test_duplicate_scored_measurement_rejected_in_either_order(self):
        # First-wins used to grade the failing 5.0 or passing 0.7 by list order.
        rows = [self._grade(env)["rows"][0]
                for env in self._both_orders("td_od50_ns", value=5.0)]
        for row in rows:
            self._assert_rejected(row, "td_od50_ns")
        self.assertEqual(rows[0]["target"], rows[1]["target"])
        self.assertEqual(rows[0]["stretch"], rows[1]["stretch"])

    def test_identical_duplicate_scored_measurement_still_rejected(self):
        env = regeneration_envelope(self.body)
        self._dup(env["corners"][0], "td_od50_ns")  # exact copy, agreeing value
        self._assert_rejected(self._grade(env)["rows"][0], "td_od50_ns")

    def test_duplicate_supply_probe_rejected_in_either_order(self):
        # One copy matches the corner, the other says the supply never applied.
        for env in self._both_orders("vdd_meas", value=1.5):
            self._assert_rejected(self._grade(env)["rows"][0], "vdd_meas")
        env = regeneration_envelope(self.body)
        self._dup(env["corners"][0], "vdda_meas")  # agreeing copies
        self._assert_rejected(self._grade(env)["rows"][0], "vdda_meas")

    def test_duplicate_temperature_probe_rejected_in_either_order(self):
        for env in self._both_orders("temp_meas", value=999.0):
            self._assert_rejected(self._grade(env)["rows"][0], "temp_meas")
        env = regeneration_envelope(self.body)
        self._dup(env["corners"][0], "temp_meas")
        self._assert_rejected(self._grade(env)["rows"][0], "temp_meas")

    def test_duplicate_validity_gate_rejected_in_either_order(self):
        self.assertIn("dout_od50_end", _row("3a")["evidence"]["gates"])
        for env in self._both_orders("dout_od50_end", value=0.0, status="fail"):
            self._assert_rejected(self._grade(env)["rows"][0], "dout_od50_end")
        env = regeneration_envelope(self.body)
        self._dup(env["corners"][0], "dout_od50_end")
        self._assert_rejected(self._grade(env)["rows"][0], "dout_od50_end")

    def test_duplicate_unrelated_measurement_still_rejects_the_point(self):
        # The corner record is ambiguous as a whole: uniqueness is checked
        # before any lookup is built, not only for the names a row consumes.
        env = regeneration_envelope(self.body)
        self._dup(env["corners"][0], "p_avg_uw")
        self._assert_rejected(self._grade(env)["rows"][0], "p_avg_uw")

    def test_duplicate_cannot_hide_a_real_miss(self):
        env = regeneration_envelope(self.body, td50=lambda p, v, t: 2.0 if p == "ff" else 0.7)
        self._dup(env["corners"][0], "td_od50_ns")
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.FAIL)

    def test_unique_valid_evidence_keeps_its_verdict(self):
        env = regeneration_envelope(self.body)
        row = self._grade(env)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.PASS)
        self.assertEqual(row["target"]["points_valid"], 45)
        # reordering a unique list changes nothing
        for c in env["corners"]:
            c["measurements"].reverse()
        self.assertEqual(self._grade(env)["rows"][0]["target"], row["target"])
        failing = regeneration_envelope(self.body, td50=lambda p, v, t: 5.0)
        self.assertEqual(self._grade(failing)["rows"][0]["target_verdict"], grade.FAIL)

    def test_full_grid_pass_impossible_with_one_rejected_point(self):
        for corner_index in (0, 22, 44):
            env = regeneration_envelope(self.body)
            self._dup(env["corners"][corner_index], "td_od50_ns")
            out = self._grade(env)
            self.assertEqual(out["rows"][0]["target_verdict"], grade.INCOMPLETE)
            self.assertFalse(out["t1_item5"]["all_target_rows_pass"])
            self.assertEqual(out["t1_item5"]["blocking_sub_bounds"][0]["target_verdict"],
                             grade.INCOMPLETE)

    def test_malformed_entries_are_diagnosed_not_raised(self):
        cases = {
            "not a list": lambda c: c.__setitem__("measurements", {"td_od50_ns": 0.7}),
            "non-object entry": lambda c: c["measurements"].append("td_od50_ns=0.7"),
            "missing name": lambda c: c["measurements"].append({"value": 0.7}),
            "non-string name": lambda c: c["measurements"].append({"name": 7, "value": 0.7}),
            "empty name": lambda c: c["measurements"].append({"name": "", "value": 0.7}),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                env = regeneration_envelope(self.body)
                mutate(env["corners"][0])
                row = self._grade(env)["rows"][0]
                self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
                self.assertEqual(row["target"]["points_valid"], 44)
                self.assertIn("malformed measurement",
                              row["target"]["points_missing_or_invalid"][0]["why"])
                grade.dumps_strict(self._grade(env))  # serialisable report

    def test_coverage_row_rejects_duplicate_probe(self):
        # The coverage caller grades per_corner_values on the supply probe.
        body_k, body_o, body_n = _body("kickback"), _body("offset_mc"), _body("transient_noise")
        benches = {
            "kickback": _evidence("kickback", kickback_envelope(body_k), body_k),
            "offset_mc": _evidence("offset_mc", offset_envelope(body_o), body_o),
            "transient_noise": _evidence("transient_noise", noise_envelope(body_n), body_n),
        }
        for front in (False, True):
            env = regeneration_envelope(self.body)
            self._dup(env["corners"][7], "vdd_meas", front=front, value=1.5)
            benches["regeneration"] = _evidence("regeneration", env, self.body)
            row = grade.grade(_spec([_row("5a")]), benches, self.dut)["rows"][0]
            self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
            self.assertTrue(any(self.DUP in p for p in row["coverage_problems"]))

    # -- statistical paths ----------------------------------------------------

    def test_offset_mc_duplicate_gate_or_probe_in_a_sample_rejects_the_point(self):
        body = _body("offset_mc")
        for name, override in (("lowcount", {"value": 0.0, "status": "fail"}),
                               ("lowcount", {}), ("vdd_meas", {"value": 1.5})):
            for front in (False, True):
                with self.subTest(name=name, override=override, front=front):
                    env = offset_envelope(body)
                    self._dup(env["corners"][5], name, front=front, **override)
                    row = self._grade(env, rows=[_row("1")], name="offset_mc", body=body)["rows"][0]
                    self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
                    self.assertEqual(row["target"]["points_valid"], 44)
                    self.assertIn(self.DUP, row["target"]["points_missing_or_invalid"][0]["why"])

    def test_offset_mc_malformed_sample_entry_is_diagnosed(self):
        body = _body("offset_mc")
        env = offset_envelope(body)
        env["corners"][5]["measurements"].append(["lowcount", 16.0])
        env["measurements"].append("not a summary")
        row = self._grade(env, rows=[_row("1")], name="offset_mc", body=body)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertIn("malformed measurement", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_noise_duplicate_outcome_or_independence_probe_rejects_the_point(self):
        body = _body("transient_noise")
        for name, override in (("hit_plus", {"value": 0.0}), ("vn0_a", {"value": 123.0}),
                               ("vn0_a", {})):
            for front in (False, True):
                with self.subTest(name=name, override=override, front=front):
                    env = noise_envelope(body)
                    self._dup(env["corners"][3], name, front=front, **override)
                    row = self._grade(env, rows=[_row("2")], name="transient_noise",
                                      body=body)["rows"][0]
                    self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
                    self.assertEqual(row["target"]["points_valid"], 44)
                    self.assertIn(self.DUP, row["target"]["points_missing_or_invalid"][0]["why"])

    def test_noise_malformed_sample_entry_is_diagnosed(self):
        body = _body("transient_noise")
        env = noise_envelope(body)
        env["corners"][3]["measurements"].append({"value": 1.0})
        row = self._grade(env, rows=[_row("2")], name="transient_noise", body=body)["rows"][0]
        self.assertEqual(row["target_verdict"], grade.INCOMPLETE)
        self.assertIn("malformed measurement", row["target"]["points_missing_or_invalid"][0]["why"])

    def test_mc_coverage_rejects_duplicate_probe(self):
        body = _body("offset_mc")
        env = offset_envelope(body)
        self._dup(env["corners"][0], "temp_meas")
        vals = grade.mc_points_exercised(_evidence("offset_mc", env, body), GRID, 60)
        bad = [v for v in vals if v.value is None]
        self.assertEqual(len(bad), 1)
        self.assertIn(self.DUP, bad[0].problem)


if __name__ == "__main__":
    unittest.main()

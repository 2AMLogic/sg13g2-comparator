"""Regression tests for the issue #498 PMOS load-width study helpers
(stdlib only, no PDK, no ngspice, writes nothing outside a temp dir).

Synthetic transient-noise Monte-Carlo envelopes in klt sim's own response
shape (screening grid: one process per envelope, 1.08/1.32 V x -40/27/125 C)
stand in for fleet output, so the derived-request contract, the Row 2
screen statistic (computed by the full-grid grader path) and the declared
advance/eliminate rule are each exercised in isolation. The control test
reads the committed archived grading record the study compares against.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from statistics import NormalDist

from kltsim import build, grade, loadwidth, sizesweep
from kltsim.benches import BENCHES, TRANSIENT_NOISE
from kltsim.tests.test_grade import _corner, _probe_values

GRADE_PATH = (build.EXPERIMENT_DIR / "campaigns" / loadwidth.CONTROL_CAMPAIGN
              / f"full_{loadwidth.CONTROL_NAME}" / "grading.json")


def _tn_screen_envelope(body: str, section: str, n=80, kplus=65, kminus=15, kzero=40,
                        drop=(), mutate=None):
    """One process's screening-grid transient-noise MC envelope: per point
    (2 supplies x 3 temperatures), ``n`` one-trial samples with unique raw
    noise draws and klt-style by_corner means for the three rungs."""
    bench = TRANSIENT_NOISE
    process = section[len("mos_"):]
    corners = []
    by_corner = {"hit_plus": [], "hit_minus": [], "hit_zero": []}
    draw = 0
    for supply in sizesweep.SCREEN_SUPPLIES_V:
        for temp in sizesweep.SCREEN_TEMPERATURES_C:
            if (process, supply, temp) in drop:
                continue
            counts = {"hit_plus": kplus if not callable(kplus) else kplus(process, supply, temp),
                      "hit_minus": kminus if not callable(kminus) else kminus(process, supply, temp),
                      "hit_zero": kzero if not callable(kzero) else kzero(process, supply, temp)}
            for k in range(n):
                draw += 1
                vals = _probe_values(bench, supply, temp)
                vals.update({"vn0_a": draw * 1e-6, "vn0_b": -draw * 1e-6, "vn1_a": draw * 2e-6,
                             "res_zero": 0.5, "res_plus": 0.5, "res_minus": 0.5})
                for name, ones in counts.items():
                    vals[name] = 1.0 if k < ones else 0.0
                corners.append(_corner(bench, process, supply, temp, vals, sample=k))
            base = corners[-1]["corner_id"].rsplit("/mc", 1)[0]
            for name, ones in counts.items():
                by_corner[name].append({"corner_id": base, "n": n, "errored": 0,
                                        "mean": ones / n, "stddev": None})
    envelope = {"schema_version": 3, "status": "pass", "corner_count": len(corners),
                "provenance": {"input": {"content_hash":
                                         "sha256:" + hashlib.sha256(body.encode()).hexdigest(),
                                         "role": "netlist"}},
                "environment": {"netlist_source": "schematic"},
                "measurements": [{"name": name, "unit": "1",
                                  "monte_carlo": {"by_corner": entries}}
                                 for name, entries in by_corner.items()],
                "corners": corners}
    if mutate:
        mutate(envelope)
    return envelope


def _write_tn_screen_evidence(sub: Path, planned: list[tuple[Path, bytes]], **kw):
    """Write the three derived requests (from ``plan_scr_inputs`` bytes), the
    shared body, plus matching envelopes and invocations into ``sub``."""
    body = next(data for path, data in planned
                if path.name == "transient_noise.body.spice").decode("utf-8")
    body_path = sub / "transient_noise.body.spice"
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_text(body, encoding="utf-8")
    for path, data in planned:
        if not path.name.startswith("transient_noise.mos_") or not path.name.endswith(
                ".request.json"):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        tag = path.name[: -len(".request.json")]
        section = tag.split(".", 1)[1]
        envelope = _tn_screen_envelope(body, section, **kw)
        env_bytes = (json.dumps(envelope, indent=2) + "\n").encode("utf-8")
        (path.parent / f"{tag}.envelope.json").write_bytes(env_bytes)
        (path.parent / f"{tag}.invocation.json").write_text(json.dumps({
            "tag": tag,
            "request_sha256": hashlib.sha256(data).hexdigest(),
            "envelope_sha256": hashlib.sha256(env_bytes).hexdigest()}), encoding="utf-8")


class ScreenRequestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_derived_requests_cover_18_points_exactly_once(self):
        planned = loadwidth.plan_scr_inputs(self.root, "w8", "8u")
        seen = {}
        for path, data in planned:
            if not path.name.startswith("transient_noise.mos_"):
                continue
            request = json.loads(data)
            self.assertEqual(request["backend"], "batch")
            self.assertEqual(len(request["corners"]["process"]), 1)
            self.assertEqual(request["monte_carlo"], TRANSIENT_NOISE.monte_carlo)
            for supply in request["corners"]["supply_v"]["vsup"]:
                for temp in request["corners"]["temperature_c"]:
                    key = sizesweep._pt(request["corners"]["process"][0], supply, temp)
                    seen[key] = seen.get(key, 0) + 1
        self.assertEqual(seen, {key: 1 for key in sizesweep.EXPECTED_POINTS})

    def test_derived_requests_pass_the_chain_semantics_check(self):
        planned = loadwidth.plan_scr_inputs(self.root, "w4", "4u")
        for path, data in planned:
            name = path.name
            if name.startswith("transient_noise.mos_") and name.endswith(".request.json"):
                tag = name[: -len(".request.json")]
                section = tag.split(".", 1)[1]
                problems = grade.check_request_semantics(
                    TRANSIENT_NOISE, tag, json.loads(data),
                    corners=loadwidth.tn_screen_corners(section))
                self.assertEqual(problems, [])

    def test_fast_bench_requests_use_the_standard_screen_grid(self):
        planned = loadwidth.plan_scr_inputs(self.root, "w10", "10u")
        for path, data in planned:
            name = path.name
            if name in ("kickback.request.json", "regeneration.request.json"):
                request = json.loads(data)
                self.assertEqual(request["corners"],
                                 sizesweep.screen_corners(BENCHES[name[: -len(".request.json")]]))

    def test_bodies_carry_the_candidate_geometry(self):
        planned = loadwidth.plan_scr_inputs(self.root, "w12", "12u")
        for bench_name in ("kickback", "regeneration", "transient_noise"):
            body = next(data for path, data in planned
                        if path.name == f"{bench_name}.body.spice").decode("utf-8")
            geometry = build.extract_geometry(body)
            self.assertEqual(geometry, loadwidth.candidate_geometry("12u"), bench_name)
            self.assertIn("dut_ib=1e-05", body)

    def test_candidate_identity_pins_xm3_xm4_at_6u(self):
        geometry = loadwidth.candidate_geometry("8u")
        self.assertEqual(geometry["XM3.w"], "6u")
        self.assertEqual(geometry["XM4.w"], "6u")
        self.assertEqual((geometry["XM5.w"], geometry["XM6.w"]), ("8u", "8u"))


class ScreenRow2Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.sub = self.root / "scr_w8"
        planned = loadwidth.plan_scr_inputs(self.root, "w8", "8u")
        _write_tn_screen_evidence(self.sub, planned)

    def test_complete_screen_gives_the_probit_mean(self):
        result = loadwidth.screen_row2(self.sub)
        self.assertEqual(result["evidence_problems"], [])
        self.assertEqual(result["dut_problems"], [])
        stat = result["statistic"]
        self.assertEqual((stat["points_valid"], stat["points_expected"]), (18, 18))
        p_plus, p_minus = 65 / 80, 15 / 80
        want = 2.0 * 1.0 / (NormalDist().inv_cdf(p_plus) - NormalDist().inv_cdf(p_minus))
        self.assertAlmostEqual(stat["grid_mean"], want, places=9)

    def test_dropped_point_leaves_the_statistic_incomplete(self):
        for tag in ("transient_noise.mos_ff",):
            path = self.sub / f"{tag}.envelope.json"
            envelope = json.loads(path.read_text(encoding="utf-8"))
            keep = [c for c in envelope["corners"] if "1.080V/125C" not in c["corner_id"]]
            envelope["corners"] = keep
            for m in envelope["measurements"]:
                m["monte_carlo"]["by_corner"] = [e for e in m["monte_carlo"]["by_corner"]
                                                 if "1.080V/125C" not in e["corner_id"]]
            env_bytes = (json.dumps(envelope, indent=2) + "\n").encode("utf-8")
            path.write_bytes(env_bytes)
            inv = self.sub / f"{tag}.invocation.json"
            record = json.loads(inv.read_text(encoding="utf-8"))
            record["envelope_sha256"] = hashlib.sha256(env_bytes).hexdigest()
            inv.write_text(json.dumps(record), encoding="utf-8")
        result = loadwidth.screen_row2(self.sub)
        stat = result["statistic"]
        self.assertEqual(stat["points_valid"], 17)
        self.assertEqual(stat["verdict"], grade.INCOMPLETE)
        self.assertIn("partial_mean_ungraded", stat)

    def test_tampered_body_rejects_the_dut(self):
        body_path = self.sub / "transient_noise.body.spice"
        text = body_path.read_text(encoding="utf-8").replace("w=8u l=0.34u", "w=9u l=0.34u", 1)
        body_path.write_text(text, encoding="utf-8")
        result = loadwidth.screen_row2(self.sub)
        self.assertTrue(result["dut_problems"])

    def test_missing_envelope_is_reported_not_raised(self):
        (self.sub / "transient_noise.mos_ss.envelope.json").unlink()
        result = loadwidth.screen_row2(self.sub)
        self.assertTrue(any("mos_ss" in p for p in result["evidence_problems"]))
        self.assertIsNone(result["statistic"])


class ControlTests(unittest.TestCase):
    def test_archived_control_screen_mean_matches_the_issue_figure(self):
        # Issue #498's verified correction: the control's 18-point mean is
        # 1.053 mV rms at the 36.27 nV/rtHz injection (45-point mean 1.096).
        control = loadwidth.control_screen_row2(build.EXPERIMENT_DIR / "campaigns")
        self.assertEqual((control["points_selected"], control["points_valid"]), (18, 18))
        self.assertAlmostEqual(control["screen_mean"], 1.0526, delta=1e-3)
        self.assertAlmostEqual(control["grid45_mean"], 1.0963, delta=1e-3)
        self.assertEqual(control["identity"], loadwidth.candidate_identity("6u"))


class DensityTests(unittest.TestCase):
    def test_load_density_validates_the_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "density.json"
            path.write_text(json.dumps({"widths": {"w8": {"points": {
                "tt": {"white_out_v_rthz": 5e-8, "gain_dc_v_per_v": 1.4,
                       "density_nv_rthz": 35.7}}}}}), encoding="utf-8")
            data = loadwidth.load_density(path)
            self.assertEqual(data["widths"]["w8"]["points"]["tt"]["density_nv_rthz"], 35.7)
            path.write_text(json.dumps({"widths": {"w8": {"points": {
                "tt": {"white_out_v_rthz": 5e-8}}}}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                loadwidth.load_density(path)


class GateTests(unittest.TestCase):
    ALL = ("td50_worst", "tau_worst", "td01_worst", "qkick_worst", "qkick_binding",
           "sigdep_worst")

    def _row(self, metrics):
        cells = {}
        for name in self.ALL:
            value = metrics.get(name, 1.0)  # absent = available and passing
            cells[name] = {"available": value is not None, "value": value,
                           "valid": 18 if value is not None else 0, "expected": 18,
                           "point": "ff_125c_1.32v", "required_gates": [],
                           "rejections": []}
        return {"metrics": cells}

    def test_measured_breach_eliminates_and_unavailability_does_not(self):
        row = self._row({"td01_worst": 2.1, "qkick_binding": 24.0, "tau_worst": None})
        breaches, unavailable = loadwidth._fast_gates(row)
        self.assertEqual(len(breaches), 1)
        self.assertIn("3c", breaches[0])
        self.assertEqual(unavailable, ["tau_worst: unavailable (0/18 valid)"])

    def test_width_tiebreak_reads_the_geometry_dict(self):
        row = {"geometry": loadwidth.candidate_geometry("10u")}
        self.assertEqual(loadwidth._width_um(row), 10.0)
        self.assertEqual(loadwidth._width_um({"geometry": {}}), 0.0)

    def test_tt_density_missing_sorts_last(self):
        density = {"points": {"tt": {"density_nv_rthz": 33.76}}}
        self.assertEqual(loadwidth._tt_density(density), 33.76)
        self.assertEqual(loadwidth._tt_density({}), float("inf"))


if __name__ == "__main__":
    unittest.main()

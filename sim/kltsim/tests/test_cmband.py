"""Common-mode-band offset characterization tests (issue #79). Stdlib only,
no PDK, no ngspice, writes nothing outside a temporary directory.

Covers: condition selection, the body transform (exactly one common-mode
source rewritten, the condition recorded, the rest of the #62 offset body
untouched), request metadata, and the analysis rules (clipped / short /
collapsed populations rejected, the ratified per-point statistic, seed
pairing, paired deltas and nominal-reproduction matching).
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from kltsim import build, cmband, grade
from kltsim.benches import OFFSET_MC


def _env(section, points, *, seed_offset=0, extra_status=None, vcm=0.6):
    """A synthetic klt sim Monte-Carlo envelope.

    ``points`` maps (supply, temp) -> list of per-sample vos_mv values. The
    lowcount gate value is derived from vos the way the bench does."""
    corners = []
    by_corner = []
    for corner_index, ((supply, temp), values) in enumerate(points.items()):
        base = f"{section}/{supply:.3f}V/{temp:g}C"
        for i, vos in enumerate(values):
            lowcount = (vos / 1e3 + 0.048) / 0.003 + 0.5
            gate_ok = 0.5 < lowcount < 32.5
            status = "pass" if gate_ok else "fail"
            if extra_status and (corner_index, i) in extra_status:
                status = extra_status[(corner_index, i)]
            corners.append({
                "corner_id": f"{base}/mc{i}",
                "process": section,
                "supply_v": {"vsup": supply},
                "temperature_c": temp,
                "status": status,
                "runtime_s": 2.5,
                "measurements": [
                    {"name": "vdd_meas", "value": supply, "unit": "V", "status": "pass"},
                    {"name": "temp_meas", "value": float(temp), "unit": "C", "status": "pass"},
                    {"name": "lowcount", "value": lowcount, "unit": "levels",
                     "status": "pass" if gate_ok else "fail"},
                    {"name": "vos_mv", "value": vos, "unit": "mV", "status": "pass"},
                    {"name": "vcm_meas", "value": vcm, "unit": "V", "status": "pass"},
                ],
                "diagnostics": [],
                "monte_carlo": {"sample_index": i, "seed": 1000 * corner_index + i + seed_offset},
            })
        n = len(values)
        mean = sum(values) / n
        s = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
        by_corner.append({"corner_id": base, "n": n, "errored": 0, "mean": mean, "stddev": s})
    return {
        "status": "pass",
        "provenance": {"input": {"content_hash": "sha256:x"}},
        "environment": {"netlist_source": "schematic", "remote": {"job_id": "j"}},
        "measurements": [{"name": "vos_mv", "unit": "mV",
                          "monte_carlo": {"by_corner": by_corner}}],
        "corners": corners,
    }


def _population(n=60, scale=3.0, shift=0.0):
    # deterministic, symmetric-ish population inside the +/-48 mV window
    return [shift + scale * math.sin(1.7 * k + 0.3) for k in range(n)]


class ConditionSelection(unittest.TestCase):
    def test_three_conditions_symmetric_band(self):
        deltas = {c.name: c.delta_v for c in cmband.CONDITIONS}
        self.assertEqual(deltas, {"vcm-m050": -0.05, "vcm-nom": 0.0, "vcm-p050": 0.05})
        self.assertEqual(cmband.NOMINAL, "vcm-nom")

    def test_unknown_condition_refused(self):
        with self.assertRaises(cmband.CmBandError):
            cmband.condition("vcm-p100")


class BodyTransform(unittest.TestCase):
    def setUp(self):
        self.base = build.compose_body(OFFSET_MC, build.BATCH_OSDI_DIR)

    def test_exactly_one_cm_source_rewritten(self):
        for cond in cmband.CONDITIONS:
            body = cmband.compose_cm_body(cond, build.BATCH_OSDI_DIR)
            self.assertNotIn(cmband.VCM_LINE + "\n", body)
            self.assertEqual(body.count(cmband.VCM_LINE_CM), 1)
            self.assertIn(f".param vcm_delta={cond.delta_v!r}\n", body)
            self.assertIn(f"condition={cond.name}", body.splitlines()[0])

    def test_rest_of_offset_body_untouched(self):
        body = cmband.compose_cm_body(cmband.condition("vcm-p050"), build.BATCH_OSDI_DIR)
        # Strip the transform and its header; what remains is the #62 body
        # from its third line on, byte for byte.
        base_tail = self.base.split("\n", 2)[2]
        undone = cmband.undo_transform(body)
        self.assertEqual(undone.split("\n", 2)[2], base_tail)

    def test_dut_block_still_verifiable(self):
        body = cmband.compose_cm_body(cmband.condition("vcm-m050"), build.BATCH_OSDI_DIR)
        path, declared, embedded = build.extract_dut_block(body)
        self.assertEqual(path, "design/comparator.spice")
        self.assertEqual(declared, build.sha256_bytes(embedded.encode("utf-8")))

    def test_missing_cm_line_refused(self):
        with self.assertRaises(cmband.CmBandError):
            cmband.apply_transform("no common-mode source here\n", cmband.condition("vcm-nom"))


class RequestMetadata(unittest.TestCase):
    def test_request_records_condition_and_keeps_basis(self):
        cond = cmband.condition("vcm-m050")
        req = cmband.compose_cm_request(cond, "offset_cm.body.spice", "mos_ss_mismatch")
        self.assertEqual(req["_condition"]["name"], "vcm-m050")
        self.assertAlmostEqual(req["_condition"]["vcm_v"], 0.55)
        self.assertEqual(req["monte_carlo"], OFFSET_MC.monte_carlo)
        self.assertEqual(req["corners"]["process"], ["mos_ss_mismatch"])
        self.assertEqual(req["backend"], "batch")
        names = [m["name"] for m in req["measurements"]]
        self.assertEqual(names, [m.name for m in OFFSET_MC.measurements] + ["vcm_meas"])
        # the offset measurements themselves are the #62 bench's, verbatim
        self.assertEqual(req["measurements"][:-1],
                         [m.request_entry() for m in OFFSET_MC.measurements])

    def test_write_condition_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            body, requests = cmband.write_condition_inputs(cmband.condition("vcm-p050"), Path(tmp))
            self.assertEqual(len(requests), 5)
            self.assertTrue(body.read_text().startswith("* offset_cm"))


class Statistics(unittest.TestCase):
    def test_ratified_statistic_matches_grade_module(self):
        values = _population()
        pop = cmband.population_stats(values)
        n = len(values)
        mean = sum(values) / n
        s = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
        self.assertAlmostEqual(pop["three_sigma_mv"],
                               grade.three_sigma_dr_basis(n, s, 3.0), places=9)

    def test_clipped_population_rejected(self):
        values = _population()
        values[5] = 49.0  # beyond the +48 mV staircase: lowcount gate fails
        env = _env("mos_tt_mismatch", {(1.2, 27): values})
        pts = cmband.load_points([env])
        point = pts[("tt", 1.2, 27.0)]
        stats = cmband.point_stats(point, expected_n=60)
        self.assertEqual(stats["clipped"], 1)
        self.assertIsNone(stats["three_sigma_mv"])
        self.assertIn("clipped", stats["rejected"])

    def test_short_population_rejected(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population(n=59)})
        stats = cmband.point_stats(cmband.load_points([env])[("tt", 1.2, 27.0)], expected_n=60)
        self.assertIn("N = 59", stats["rejected"])

    def test_errored_draw_rejects_but_keeps_informational_partial(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()},
                   extra_status={(0, 12): "error"})
        point = cmband.load_points([env])[("tt", 1.2, 27.0)]
        stats = cmband.point_stats(point)
        self.assertIn("untrusted", stats["rejected"])
        self.assertIsNone(stats["three_sigma_mv"])
        self.assertEqual(stats["n_partial"], 59)
        self.assertIsNotNone(stats["three_sigma_partial_mv"])

    def test_clipped_population_has_no_partial(self):
        values = _population()
        values[3] = -49.0
        point = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): values})])[("tt", 1.2, 27.0)]
        self.assertIsNone(cmband.point_stats(point)["three_sigma_partial_mv"])

    def test_collapsed_population_rejected(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): [1.5] * 60})
        stats = cmband.point_stats(cmband.load_points([env])[("tt", 1.2, 27.0)], expected_n=60)
        self.assertIn("zero spread", stats["rejected"])

    def test_paired_delta(self):
        nom = _population()
        shifted = [v + 0.5 for v in nom]
        pts_nom = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): nom})])
        pts_cm = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): shifted})])
        key = ("tt", 1.2, 27.0)
        pair = cmband.paired(pts_cm[key], pts_nom[key])
        self.assertTrue(pair["seeds_paired"])
        self.assertAlmostEqual(pair["delta_mean_mv"], 0.5, places=9)
        self.assertAlmostEqual(pair["delta_sd_mv"], 0.0, places=9)
        self.assertAlmostEqual(pair["ratio_3sigma"], 1.0, places=9)
        self.assertAlmostEqual(pair["corr"], 1.0, places=9)

    def test_unpaired_seeds_detected(self):
        pts_a = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): _population()})])
        pts_b = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): _population()},
                                         seed_offset=7)])
        key = ("tt", 1.2, 27.0)
        self.assertFalse(cmband.paired(pts_a[key], pts_b[key])["seeds_paired"])

    def test_reproduction_match(self):
        a = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): _population()})])
        b = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): _population()})])
        rep = cmband.reproduction(a, b)
        self.assertEqual(rep["samples_compared"], 60)
        self.assertEqual(rep["identical"], 60)
        self.assertEqual(rep["max_abs_diff_mv"], 0.0)


class ConditionProbe(unittest.TestCase):
    def test_wrong_common_mode_untrusted(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()}, vcm=0.6)
        pts = cmband.load_points([env], vcm_v=0.65)
        stats = cmband.point_stats(pts[("tt", 1.2, 27.0)])
        self.assertIn("vcm_meas", stats["rejected"])
        ok = cmband.load_points([env], vcm_v=0.6)
        self.assertIsNone(cmband.point_stats(ok[("tt", 1.2, 27.0)])["rejected"])


class Report(unittest.TestCase):
    def test_compare_series_end_to_end(self):
        """Three synthetic conditions, one grid point each, through the full
        comparison + markdown render."""
        with tempfile.TemporaryDirectory() as tmp:
            series = Path(tmp)
            for cond, shift, vcm in (("vcm-m050", -0.4, 0.55), ("vcm-nom", 0.0, 0.6),
                                     ("vcm-p050", 0.4, 0.65)):
                d = series / cond
                d.mkdir()
                env = _env("mos_tt_mismatch", {(1.2, 27): _population(shift=shift)}, vcm=vcm)
                (d / "offset_cm.mos_tt_mismatch.envelope.json").write_text(json.dumps(env))
            result = cmband.compare_series(series, grid=(("tt",), (1.2,), (27.0,)),
                                           reference_campaign=None)
            self.assertEqual(result["conditions"]["vcm-nom"]["points_valid"], 1)
            row = result["points"][0]
            self.assertAlmostEqual(row["paired"]["vcm-p050"]["delta_mean_mv"], 0.4, places=9)
            md = cmband.render_markdown(result)
            self.assertIn("characterization", md.lower())
            self.assertIn("vcm-p050", md)


if __name__ == "__main__":
    unittest.main()

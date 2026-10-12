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


class MeasurementUniqueness(unittest.TestCase):
    """Issue #150: a repeated or malformed measurement entry in one sample
    makes that sample untrusted; no copy is selected by list order."""

    def test_duplicate_measurement_rejects_point_in_either_order(self):
        for name in ("vos_mv", "lowcount", "vdd_meas"):
            for front in (False, True):
                with self.subTest(name=name, front=front):
                    env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
                    ms = env["corners"][4]["measurements"]
                    orig = next(m for m in ms if m["name"] == name)
                    ms.insert(0 if front else len(ms), dict(orig))
                    pts = cmband.load_points([env], vcm_v=0.6)
                    rejected = cmband.point_stats(pts[("tt", 1.2, 27.0)])["rejected"]
                    self.assertIn(f"duplicate measurement name(s) {name} (x2)", rejected)

    def test_malformed_entry_is_diagnosed_not_raised(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        env["corners"][4]["measurements"].append("vos_mv")
        pts = cmband.load_points([env], vcm_v=0.6)
        self.assertIn("malformed measurement",
                      cmband.point_stats(pts[("tt", 1.2, 27.0)])["rejected"])


KEY = ("tt", 1.2, 27.0)


def _measurement(env, corner, name):
    return next(m for m in env["corners"][corner]["measurements"] if m["name"] == name)


def _pts(env, vcm_v=0.6):
    return cmband.load_points([env], vcm_v=vcm_v)[KEY]


class NumericEvidence(unittest.TestCase):
    """Issue #250: malformed vos_mv / vcm_meas values are named untrusted
    draws -- never a crash, a NaN statistic or a trusted sigma."""

    BAD_VALUES = (float("nan"), float("inf"), float("-inf"), True, False, "abc", "", [1.0], {})

    def _assert_untrusted(self, env, needle=None):
        pts = _pts(env)
        stats = cmband.point_stats(pts)
        self.assertIsNone(stats["three_sigma_mv"])
        self.assertIsNone(stats["sigma_corr_mv"])
        self.assertIn("untrusted", stats["rejected"])
        if needle:
            self.assertIn(needle, stats["rejected"])
        # strict JSON never fails on the per-point statistics
        grade.dumps_strict(stats)
        for s in pts:
            self.assertTrue(s["vos_mv"] is None or math.isfinite(s["vos_mv"]))
        return pts, stats

    def test_bad_offset_values_untrusted(self):
        for bad in self.BAD_VALUES:
            with self.subTest(bad=bad):
                env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
                _measurement(env, 7, "vos_mv")["value"] = bad
                pts, _ = self._assert_untrusted(env, "mc7")
                self.assertIsNone(pts[7]["vos_mv"])

    def test_bad_probe_values_untrusted(self):
        for bad in self.BAD_VALUES:
            with self.subTest(bad=bad):
                env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
                _measurement(env, 7, "vcm_meas")["value"] = bad
                self._assert_untrusted(env, "vcm_meas")

    def test_nan_probe_does_not_bypass_tolerance(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        _measurement(env, 3, "vcm_meas")["value"] = float("nan")
        self._assert_untrusted(env, "not finite")

    def test_bad_lowcount_untrusted(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        _measurement(env, 2, "lowcount")["value"] = float("nan")
        self._assert_untrusted(env, "lowcount")

    def test_wrong_dimension_or_missing_unit_untrusted(self):
        for name, unit in (("vos_mv", "s"), ("vos_mv", None), ("vos_mv", "furlongs"),
                           ("vcm_meas", "A"), ("vcm_meas", None), ("vcm_meas", 1)):
            with self.subTest(name=name, unit=unit):
                env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
                _measurement(env, 9, name)["unit"] = unit
                self._assert_untrusted(env, name)

    def test_compatible_units_normalize(self):
        base = cmband.point_stats(_pts(_env("mos_tt_mismatch", {(1.2, 27): _population()})))
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        for i, corner in enumerate(env["corners"]):
            vos = _measurement(env, i, "vos_mv")
            if i % 2:
                vos["value"], vos["unit"] = vos["value"] / 1e3, "V"
            else:
                vos["value"], vos["unit"] = vos["value"] * 1e3, "uV"
            vcm = _measurement(env, i, "vcm_meas")
            vcm["value"], vcm["unit"] = 600.0, "mV"
        pts = _pts(env)
        self.assertTrue(all(s["problem"] is None for s in pts))
        for s, v in zip(pts, _population()):
            self.assertAlmostEqual(s["vos_mv"], v, places=9)
        stats = cmband.point_stats(pts)
        self.assertIsNone(stats["rejected"])
        self.assertAlmostEqual(stats["three_sigma_mv"], base["three_sigma_mv"], places=9)

    def test_controls_negative_ignores_nonfinite(self):
        env = _env("mos_tt", {(1.2, 27): [1.5] * 4})
        _measurement(env, 0, "vos_mv")["value"] = float("nan")
        vals = [s["vos_mv"] for s in cmband.load_points([env])[KEY] if s["vos_mv"] is not None]
        self.assertEqual(vals, [1.5] * 3)


class DrawIdentity(unittest.TestCase):
    """Issue #250: a population is one set of unique, valid draw identities."""

    def _dup_env(self):
        # sample 41 replaced by a second copy of sample 17: still 60 records
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        env["corners"][41] = json.loads(json.dumps(env["corners"][17]))
        return env

    def test_duplicate_index_rejects_sixty_record_population(self):
        env = self._dup_env()
        pts = _pts(env)
        self.assertEqual(len(pts), 60)
        stats = cmband.point_stats(pts)
        self.assertIn("duplicate sample index(es) 17 (x2)", stats["rejected"])
        self.assertIsNone(stats["three_sigma_mv"])
        self.assertIsNone(stats["three_sigma_partial_mv"])

    def test_duplicate_index_rejection_invariant_under_order(self):
        reference = None
        for order in range(4):
            env = self._dup_env()
            corners = env["corners"]
            if order == 1:
                corners.reverse()
            elif order == 2:
                corners[:] = corners[30:] + corners[:30]
            # order 3: split across two envelopes, second one first
            envs = [env] if order < 3 else [
                dict(env, corners=corners[30:]), dict(env, corners=corners[:30])]
            with self.subTest(order=order):
                stats = cmband.point_stats(cmband.load_points(envs, vcm_v=0.6)[KEY])
                if reference is None:
                    reference = stats
                self.assertEqual(stats, reference)

    def test_duplicate_index_with_distinct_seed_still_rejected(self):
        env = self._dup_env()
        env["corners"][41]["monte_carlo"]["seed"] = 999999
        stats = cmband.point_stats(_pts(env))
        self.assertIn("duplicate sample index", stats["rejected"])

    def test_repeated_seed_rejected(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        env["corners"][5]["monte_carlo"]["seed"] = env["corners"][6]["monte_carlo"]["seed"]
        stats = cmband.point_stats(_pts(env))
        self.assertIn("seed(s) reported by more than one draw", stats["rejected"])

    def test_invalid_index_untrusted(self):
        for bad in (None, -1, True, 3.0, "3"):
            with self.subTest(bad=bad):
                env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
                env["corners"][3]["monte_carlo"]["sample_index"] = bad
                stats = cmband.point_stats(_pts(env))  # sorting never raises
                self.assertIn("sample_index", stats["rejected"])
                self.assertIsNone(stats["three_sigma_mv"])

    def test_invalid_or_absent_seed_untrusted(self):
        for bad in (None, True, -5, "7", 1.0):
            with self.subTest(bad=bad):
                env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
                if bad is None:
                    del env["corners"][3]["monte_carlo"]["seed"]
                else:
                    env["corners"][3]["monte_carlo"]["seed"] = bad
                stats = cmband.point_stats(_pts(env))
                self.assertIn("monte_carlo.seed", stats["rejected"])

    def test_indices_outside_basis_rejected(self):
        env = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        env["corners"][59]["monte_carlo"]["sample_index"] = 75
        stats = cmband.point_stats(_pts(env))
        self.assertIn("sample indices are not 0..59", stats["rejected"])
        self.assertIsNone(stats["three_sigma_mv"])

    def test_short_population_message_unchanged(self):
        stats = cmband.point_stats(_pts(_env("mos_tt_mismatch", {(1.2, 27): _population(n=59)})))
        self.assertEqual(stats["rejected"], "N = 59, ratified basis is N = 60")
        self.assertEqual(stats["n_partial"], 59)


class Pairing(unittest.TestCase):
    """Issue #250: only complete trusted populations with matching identities
    and valid, equal seeds are paired; every refusal says why."""

    def _pair(self, mutate_cm=None, mutate_nom=None):
        nom = _env("mos_tt_mismatch", {(1.2, 27): _population()})
        cm = _env("mos_tt_mismatch", {(1.2, 27): [v + 0.5 for v in _population()]})
        if mutate_cm:
            mutate_cm(cm)
        if mutate_nom:
            mutate_nom(nom)
        return cmband.paired(_pts(cm), _pts(nom))

    def _assert_unpaired(self, pair, needle):
        self.assertIsNone(pair["ratio_3sigma"])
        self.assertIsNone(pair["delta_mean_mv"])
        self.assertIn(needle, pair["pair_rejected"])

    def test_valid_pair_has_no_rejection(self):
        pair = self._pair()
        self.assertTrue(pair["seeds_paired"])
        self.assertIsNone(pair["pair_rejected"])
        self.assertEqual(pair["n_pairs"], 60)

    def test_absent_seeds_never_pair(self):
        def drop(env):
            for c in env["corners"]:
                c["monte_carlo"].pop("seed")
        pair = self._pair(drop, drop)
        self.assertFalse(pair["seeds_paired"])
        self._assert_unpaired(pair, "monte_carlo.seed")

    def test_absent_seeds_never_pair_at_identity_level(self):
        a = [{"sample_index": k, "seed": None, "vos_mv": 1.0 + k, "clipped": False,
              "problem": None, "corner_id": f"c/mc{k}", "runtime_s": None} for k in range(3)]
        self.assertFalse(cmband.paired(a, [dict(s) for s in a])["seeds_paired"])

    def test_duplicate_index_never_paired(self):
        def dup(env):
            env["corners"][41] = json.loads(json.dumps(env["corners"][17]))
        for side in ("cm", "nom"):
            with self.subTest(side=side):
                pair = self._pair(dup if side == "cm" else None, dup if side == "nom" else None)
                self.assertFalse(pair["seeds_paired"])
                self._assert_unpaired(pair, "duplicate sample index")

    def test_seed_mismatch_reason(self):
        def reseed(env):
            env["corners"][4]["monte_carlo"]["seed"] = 777777
        pair = self._pair(reseed)
        self.assertFalse(pair["seeds_paired"])
        self._assert_unpaired(pair, "sample 4 is not the same mismatch draw")

    def test_untrusted_draw_blocks_pair(self):
        def nan(env):
            _measurement(env, 8, "vos_mv")["value"] = float("nan")
        self._assert_unpaired(self._pair(None, nan), "nominal population rejected")


class Reproduction(unittest.TestCase):
    """Issue #250: reproduction accounts for every expected draw on both
    sides; the verdict is separate from the surviving-draw comparison."""

    def _sides(self):
        a = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): _population()})])
        b = cmband.load_points([_env("mos_tt_mismatch", {(1.2, 27): _population()})])
        return a, b

    def test_complete_reproduction(self):
        rep = cmband.reproduction(*self._sides(), labels=("nom", "ref"))
        self.assertEqual(rep["verdict"], cmband.REPRODUCED)
        self.assertTrue(rep["complete"])
        self.assertEqual(rep["expected_draws"], 60)
        self.assertEqual(rep["unaccounted"], [])
        json.loads(grade.dumps_strict(rep))

    def _assert_incomplete(self, rep, side, index, kind):
        self.assertEqual(rep["verdict"], cmband.REPRO_INCOMPLETE)
        self.assertFalse(rep["complete"])
        hits = [u for u in rep["unaccounted"]
                if u["side"] == side and u["sample_index"] == index and u["kind"] == kind]
        self.assertTrue(hits, rep["unaccounted"])
        # the surviving draws still compare, informationally
        self.assertEqual(rep["identical"], rep["samples_compared"])
        self.assertEqual(rep["samples_compared"], 59)

    def test_dropped_draw_either_side(self):
        for side in (0, 1):
            with self.subTest(side=side):
                sides = list(self._sides())
                sides[side][KEY] = [s for s in sides[side][KEY] if s["sample_index"] != 13]
                rep = cmband.reproduction(*sides, labels=("nom", "ref"))
                self._assert_incomplete(rep, ("nom", "ref")[side], 13, "missing")
                self.assertEqual(rep["missing_draws"], 1)

    def test_nulled_offset_either_side(self):
        for side in (0, 1):
            with self.subTest(side=side):
                sides = list(self._sides())
                sides[side][KEY][13]["vos_mv"] = None
                rep = cmband.reproduction(*sides, labels=("nom", "ref"))
                self._assert_incomplete(rep, ("nom", "ref")[side], 13, "rejected")

    def test_untrusted_draw_either_side(self):
        for side in (0, 1):
            with self.subTest(side=side):
                envs = [_env("mos_tt_mismatch", {(1.2, 27): _population()}) for _ in range(2)]
                envs[side]["corners"][13]["status"] = "error"
                a, b = (cmband.load_points([e]) for e in envs)
                rep = cmband.reproduction(a, b, labels=("nom", "ref"))
                self._assert_incomplete(rep, ("nom", "ref")[side], 13, "rejected")
                self.assertEqual(rep["rejected_draws"], 1)

    def test_both_sides_missing_same_draw(self):
        a, b = self._sides()
        for side in (a, b):
            side[KEY] = [s for s in side[KEY] if s["sample_index"] != 59]
        rep = cmband.reproduction(a, b)
        self.assertEqual(rep["verdict"], cmband.REPRO_INCOMPLETE)
        self.assertEqual(rep["missing_draws"], 2)

    def test_duplicate_index_reported_not_compared(self):
        a, b = self._sides()
        a[KEY][41] = dict(a[KEY][17])
        rep = cmband.reproduction(a, b)
        self.assertEqual(rep["verdict"], cmband.REPRO_INCOMPLETE)
        reasons = [u["reason"] for u in rep["unaccounted"]]
        self.assertTrue(any("reported 2 times" in r for r in reasons), reasons)

    def test_unmatched_point(self):
        a, b = self._sides()
        b[("ff", 1.2, 27.0)] = list(b[KEY])
        rep = cmband.reproduction(a, b, labels=("nom", "ref"))
        self.assertEqual(rep["verdict"], cmband.REPRO_INCOMPLETE)
        self.assertEqual(rep["points_unmatched"], 1)
        self.assertEqual(rep["unaccounted"][0]["side"], "nom")

    def test_value_difference_is_not_reproduced(self):
        a, b = self._sides()
        b[KEY][3]["vos_mv"] += 3.0
        rep = cmband.reproduction(a, b)
        self.assertTrue(rep["complete"])
        self.assertEqual(rep["verdict"], cmband.NOT_REPRODUCED)
        self.assertEqual(rep["identical"], 59)

    def test_markdown_states_verdict(self):
        a, b = self._sides()
        a[KEY] = a[KEY][:-1]
        rep = cmband.reproduction(a, b, labels=("vcm-nom", "reference"))
        self.assertIn("INCOMPLETE", cmband._repro_verdict(rep))
        self.assertIn("sample 59", cmband._repro_verdict(rep))
        self.assertIn("not recorded", cmband._repro_verdict({}))


class ReproductionEmptyAndCounts(unittest.TestCase):
    """Issue #252: zero-draw comparisons are INCOMPLETE; rejected draws are
    counted per sample record."""

    PT = ("tt", 1.2, 27.0)

    @staticmethod
    def _s(index, seed=1, vos=1.0):
        return {"sample_index": index, "seed": seed, "vos_mv": vos, "problem": None}

    def _assert_empty(self, rep):
        self.assertEqual(rep["verdict"], cmband.REPRO_INCOMPLETE)
        self.assertFalse(rep["complete"])
        self.assertEqual(rep["expected_draws"], 0)
        self.assertTrue(rep["empty_comparison"])
        self.assertIn("no draws to compare", rep["empty_reason"])

    def test_empty_mappings_incomplete(self):
        self._assert_empty(cmband.reproduction({}, {}))

    def test_shared_empty_point_incomplete(self):
        for n in (None, 0):
            rep = cmband.reproduction({self.PT: []}, {self.PT: []}, expected_n=n)
            self._assert_empty(rep)
            self.assertEqual(rep["points_compared"], 1)

    def test_nonempty_still_reproduced(self):
        pts = {self.PT: [self._s(i) for i in range(3)]}
        rep = cmband.reproduction(pts, pts, expected_n=3)
        self.assertEqual(rep["verdict"], cmband.REPRODUCED)
        self.assertFalse(rep["empty_comparison"])

    def test_repeated_invalid_indices_counted_per_record(self):
        a = {self.PT: [self._s(None), self._s(None), self._s(None)]}
        b = {self.PT: [self._s(None)]}
        rep = cmband.reproduction(a, b, expected_n=0)
        self.assertEqual(rep["rejected_draws"], 4)
        self.assertEqual(rep["missing_draws"], 0)
        self.assertEqual(rep["verdict"], cmband.REPRO_INCOMPLETE)

    def test_duplicate_valid_indices_all_copies_counted(self):
        for copies in (2, 3):
            base = [self._s(0)] * copies + [self._s(1)]
            for order in (base, base[::-1]):
                rep = cmband.reproduction({self.PT: order}, {self.PT: [self._s(0), self._s(1)]},
                                          expected_n=2)
                self.assertEqual(rep["rejected_draws"], copies)
                self.assertEqual(rep["missing_draws"], 0)  # not double-counted
                self.assertEqual(rep["verdict"], cmband.REPRO_INCOMPLETE)

    def test_both_sides_counted_and_list_bounded(self):
        n = cmband.REPRO_LIST_MAX + 7
        a = {self.PT: [self._s(None) for _ in range(n)]}
        b = {self.PT: [self._s(None) for _ in range(n)]}
        rep = cmband.reproduction(a, b, expected_n=0)
        self.assertEqual(rep["rejected_draws"], 2 * n)
        self.assertEqual(len(rep["unaccounted"]), cmband.REPRO_LIST_MAX)
        self.assertTrue(rep["unaccounted_truncated"])

    def test_identity_map_compat(self):
        out, bad = cmband._identity_map([self._s(None), self._s(None), self._s(0)])
        self.assertEqual(sorted(out), [0])
        self.assertEqual(list(bad), ["None"])

    def test_empty_repeat_control_renders_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            env = _env("mos_tt_mismatch", {(1.2, 27): _population(n=2)})
            env["corners"] = [c for c in env["corners"]]
            for c in env["corners"]:
                c.pop("monte_carlo", None)
            (d / "repeat.vcm-nom.a.envelope.json").write_text(json.dumps(env))
            ctl = cmband._controls(d, {"vcm-nom": {}})
            self.assertEqual(len(ctl["repeat"]), 1)
            rep = ctl["repeat"][0]
            self._assert_empty(rep)
            line = cmband._repro_verdict(rep)
            self.assertTrue(line.startswith("INCOMPLETE"))
            self.assertIn("no draws to compare", line)


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

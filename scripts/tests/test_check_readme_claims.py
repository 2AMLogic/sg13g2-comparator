"""Negative controls for scripts/check_readme_claims.py (issue #174).

Stdlib only. The positive case runs the real README against the real
committed report; negative cases mutate a copy of one or the other.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_readme_claims.py"
spec = importlib.util.spec_from_file_location("check_readme_claims", SCRIPT)
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

README = chk.DEFAULT_README.read_text(encoding="utf-8")
REPORT = chk.load_report(chk.DEFAULT_REPORT)


NOISE = json.loads(chk.NOISE_PATH.read_text(encoding="utf-8"))
OFFSET = json.loads(chk.OFFSET_PATH.read_text(encoding="utf-8"))


def _run(readme_text, report, noise=None, offset=None, raw_noise=None, raw_offset=None):
    """Run main() on temp copies; `noise`/`offset` default to the committed sources."""
    with tempfile.TemporaryDirectory() as td:
        rp, jp = Path(td, "README.md"), Path(td, "report.json")
        np_, op = Path(td, "noise_full.json"), Path(td, "offset.json")
        rp.write_text(readme_text, encoding="utf-8")
        jp.write_text(json.dumps(report), encoding="utf-8")
        np_.write_text(raw_noise if raw_noise is not None else json.dumps(noise or NOISE),
                       encoding="utf-8")
        op.write_text(raw_offset if raw_offset is not None else json.dumps(offset or OFFSET),
                      encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = chk.main(["--readme", str(rp), "--report", str(jp),
                             "--noise-full", str(np_), "--offset-record", str(op)])
    return code, out.getvalue(), err.getvalue()


def _clone(x):
    return json.loads(json.dumps(x))


class ReadmeClaims(unittest.TestCase):
    def test_committed_readme_matches_committed_report(self):
        code, out, err = _run(README, REPORT)
        self.assertEqual(code, 0, err)
        self.assertIn(f"checked {len(chk.CLAIMS)}/{len(chk.CLAIMS)}", out)

    def test_unmapped_claims_are_reported_not_passed(self):
        _, out, _ = _run(README, REPORT)
        self.assertIn("UNCHECKED count in row 'Offset sigma'", out)

    def test_mutated_readme_count_fails_with_both_values(self):
        mutated = README.replace("39/45 points over 25 fC", "38/45 points over 25 fC")
        self.assertNotEqual(mutated, README)
        code, _, err = _run(mutated, REPORT)
        self.assertEqual(code, 1)
        self.assertIn("README says 38", err)
        self.assertIn("report (4a/target/points_failing) says 39", err)

    def test_mutated_readme_value_fails(self):
        mutated = README.replace("binding point `ff_125c_1.32v` (31.46 fC;",
                                 "binding point `ff_125c_1.32v` (30.46 fC;")
        self.assertNotEqual(mutated, README)
        code, _, err = _run(mutated, REPORT)
        self.assertEqual(code, 1)
        self.assertIn("README says 30.46, report", err)
        self.assertIn("says 31.46", err)

    def test_mutated_report_fails(self):
        report = json.loads(json.dumps(REPORT))
        row = next(r for r in report["rows"] if r["id"] == "3b")
        row["target"]["range"]["max"]["value"] = 170.0
        code, _, err = _run(README, report)
        self.assertEqual(code, 1)
        self.assertIn("tau max ps", err)

    def test_pattern_that_stops_matching_fails_loudly(self):
        code, _, err = _run(README.replace("fC/side**", "fC per side**"), REPORT)
        self.assertEqual(code, 1)
        self.assertIn("no longer matches", err)

    def test_rounding_is_half_up_at_readme_precision(self):
        self.assertEqual(chk._round_to(167.256, "167.3"), "167.3")
        self.assertEqual(chk._round_to(0.8125, "0.813"), "0.813")
        self.assertEqual(chk._round_to(7.0, "7"), "7")

    def test_missing_report_row_fails(self):
        report = json.loads(json.dumps(REPORT))
        report["rows"] = [r for r in report["rows"] if r["id"] != "4a"]
        code, _, err = _run(README, report)
        self.assertEqual(code, 1)
        self.assertIn("no row id '4a'", err)


NOISE_ID, OFFSET_ID = "noise-full-issue81", "offset-whole-latch-ea40b57"


def _mutate_readme(old, new):
    mutated = README.replace(old, new)
    assert mutated != README, old
    return mutated


class SourceRegistry(unittest.TestCase):
    """Issue #193: claims verified against their own evidence populations."""

    def test_all_registered_claims_pass_on_committed_state(self):
        code, out, err = _run(README, REPORT)
        self.assertEqual(code, 0, err)
        n = len(chk.SOURCE_CLAIMS)
        self.assertIn(f"checked {n}/{n} source-registry README claims against "
                      f"{NOISE_ID}, {OFFSET_ID}", out)
        # the aggregate-report mappings are unchanged and still reported
        self.assertIn(f"checked {len(chk.CLAIMS)}/{len(chk.CLAIMS)} allowlisted", out)

    def test_every_source_claim_names_a_registered_source(self):
        for c in chk.SOURCE_CLAIMS:
            self.assertIn(c[1], chk.SOURCES, c[0])
        self.assertEqual(len({c[0] for c in chk.SOURCE_CLAIMS}), len(chk.SOURCE_CLAIMS))

    def test_unmapped_populations_stay_unchecked(self):
        _, out, _ = _run(README, REPORT)
        self.assertIn("UNCHECKED count in row 'Offset sigma': 13 of 45", out)  # front-end record
        self.assertIn("UNCHECKED count in row 'Input-referred noise': 45/45", out)  # historical

    def test_readme_noise_mean_mutation_names_claim_source_and_value(self):
        code, _, err = _run(_mutate_readme("grid-wide mean 1.305 mV rms",
                                           "grid-wide mean 1.205 mV rms"), REPORT)
        self.assertEqual(code, 1)
        self.assertIn("noise(#81): grid mean mV rms: README says 1.205", err)
        self.assertIn(f"source {NOISE_ID}", err)
        self.assertIn("says 1.305", err)

    def test_readme_noise_valid_point_count_mutation_fails(self):
        code, _, err = _run(_mutate_readme("**45/45 valid points, grid-wide mean",
                                           "**44/45 valid points, grid-wide mean"), REPORT)
        self.assertEqual(code, 1)
        self.assertIn("noise(#81): valid points: README says 44", err)
        self.assertIn("says 45", err)

    def test_readme_noise_min_max_and_n_mutations_fail(self):
        for old, new, label in (("(min 0.910 … max 1.773 mV)", "(min 0.911 … max 1.773 mV)", "min"),
                                ("(min 0.910 … max 1.773 mV)", "(min 0.910 … max 1.774 mV)", "max"),
                                ("N = 80 trials per rung (3 rungs)", "N = 60 trials per rung (3 rungs)", "N")):
            with self.subTest(label):
                code, _, err = _run(_mutate_readme(old, new), REPORT)
                self.assertEqual(code, 1)
                self.assertIn(f"source {NOISE_ID}", err)

    def test_historical_noise_figures_do_not_satisfy_the_current_claim(self):
        # Historical 1.335 mV in place of the current 1.305 must not slip by.
        code, _, err = _run(_mutate_readme("grid-wide mean 1.305 mV rms",
                                           "grid-wide mean 1.335 mV rms"), REPORT)
        self.assertEqual(code, 1)
        self.assertIn("README says 1.335", err)

    def test_readme_offset_mutations_fail_with_expected_value(self):
        cases = (
            ("Target MET at 45/45 points on the whole latch", "Target MET at 44/45 points on the whole latch",
             "Target met points: README says 44"),
            ("Stretch NOT MET at 27/45.** Whole latch", "Stretch NOT MET at 26/45.** Whole latch",
             "Stretch missed points: README says 26"),
            ("3σ 7.456 mV (`tt_mismatch_27c_1.32v`)", "3σ 7.457 mV (`tt_mismatch_27c_1.32v`)",
             "3 sigma min mV: README says 7.457"),
            ("**10.537 mV** (`tt_mismatch_125c_1.08v`)", "**10.538 mV** (`tt_mismatch_125c_1.08v`)",
             "3 sigma max mV: README says 10.538"),
            ("**10.537 mV** (`tt_mismatch_125c_1.08v`), mean 8.404 mV",
             "**10.537 mV** (`tt_mismatch_125c_1.08v`), mean 8.405 mV", "3 sigma mean mV: README says 8.405"),
            ("**10.537 mV** (`tt_mismatch_125c_1.08v`)", "**10.537 mV** (`tt_mismatch_125c_1.20v`)",
             "3 sigma max point: README says tt_mismatch_125c_1.20v"),
            ("N = 60 draws per point, seed `20260916`", "N = 200 draws per point, seed `20260916`",
             "N draws per point: README says 200"),
            ("Stretch at 27/45. Record [`20260917-060858-ea40b57`]", "Stretch at 27/45. Record [`20260916-125444-4d0cf7c`]",
             "cited record id: README says 20260916-125444-4d0cf7c"),
        )
        for old, new, expect in cases:
            with self.subTest(expect):
                code, _, err = _run(_mutate_readme(old, new), REPORT)
                self.assertEqual(code, 1)
                self.assertIn(expect, err)
                self.assertIn(f"source {OFFSET_ID}", err)

    def test_front_end_offset_figures_cannot_satisfy_whole_latch_claim(self):
        # 11.61 is the front-end-only minimum; the whole-latch claim must not take it.
        code, _, err = _run(_mutate_readme("3σ 7.456 mV (`tt_mismatch_27c_1.32v`)",
                                           "3σ 11.61 mV (`tt_mismatch_27c_1.32v`)"), REPORT)
        self.assertEqual(code, 1)
        self.assertIn("README says 11.61", err)

    def test_changed_readme_structure_fails_loudly(self):
        code, _, err = _run(README.replace("valid points, grid-wide mean", "valid points, mean"), REPORT)
        self.assertEqual(code, 1)
        self.assertIn("no longer matches", err)
        self.assertIn(f"[source {NOISE_ID}]", err)


class PvtPopulationIdentity(unittest.TestCase):
    """Issue #217: a registered source must carry the complete physical PVT
    population -- the 5-process x 3-temperature x 3-supply grid behind every
    N/45 claim -- not merely 45 entries with arbitrary identifiers."""

    # ---- noise source (points[].point, no physical metadata) ----

    def test_noise_all_entries_same_point_id_fails(self):
        noise = _clone(NOISE)
        for p in noise["points"]:
            p["point"] = "tt_27c_1.20v"
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 1)
        self.assertIn(f"source {NOISE_ID}", err)
        self.assertIn("'tt_27c_1.20v' appears at points 0 and 1", err)
        self.assertIn("cannot be verified", err)  # fails before the claim can pass

    def test_noise_duplicate_point_id_fails(self):
        noise = _clone(NOISE)
        noise["points"][0]["point"] = noise["points"][1]["point"]
        self.assertNotEqual(noise["points"][0]["point"], NOISE["points"][0]["point"])
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 1)
        self.assertIn(f"source {NOISE_ID}", err)
        self.assertIn("duplicate identities are not distinct physical corners", err)

    def test_noise_replaced_corner_reports_unknown_and_missing(self):
        noise = _clone(NOISE)
        noise["points"][0]["point"] = "tt_-40c_1.44v"  # plausible corner, off-grid supply
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 1)
        self.assertIn(f"source {NOISE_ID}", err)
        self.assertIn("unknown point 'tt_-40c_1.44v'", err)
        self.assertIn("missing point 'tt_-40c_1.08v'", err)

    def test_noise_permuted_grid_passes(self):
        noise = _clone(NOISE)
        noise["points"].reverse()
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 0, err)

    # ---- offset source (points[].corner_id + corner/temp_c/vdd metadata) ----

    def test_offset_arbitrary_distinct_ids_fail_despite_consistent_summary(self):
        off = _clone(OFFSET)
        orig_ids = [p["corner_id"] for p in OFFSET["points"]]
        summ = off["summary"]["vos_3sig_mv"]
        for i, p in enumerate(off["points"]):
            p["corner_id"] = f"unrecognized_{i}"
        summ["at_min"] = f"unrecognized_{orig_ids.index(summ['at_min'])}"
        summ["at_max"] = f"unrecognized_{orig_ids.index(summ['at_max'])}"
        code, _, err = _run(README, REPORT, offset=off)
        self.assertEqual(code, 1)
        self.assertIn(f"source {OFFSET_ID}", err)
        self.assertIn("unknown corner_id 'unrecognized_0'", err)
        self.assertIn("cannot be verified", err)

    def test_offset_duplicate_corner_id_fails(self):
        off = _clone(OFFSET)
        off["points"][0]["corner_id"] = off["points"][1]["corner_id"]
        code, _, err = _run(README, REPORT, offset=off)
        self.assertEqual(code, 1)
        self.assertIn(f"source {OFFSET_ID}", err)
        self.assertIn("appears at points 0 and 1", err)

    def test_offset_consistent_substitution_of_a_different_corner_fails(self):
        # Even a corner whose *metadata* is updated to match must not slip in:
        # the grid contract is on the population, not the formatting.
        off = _clone(OFFSET)
        donor = next(p for p in off["points"] if p["corner_id"] == "fs_mismatch_-40c_1.08v")
        victim = off["points"][0]
        self.assertEqual(victim["corner_id"], "tt_mismatch_-40c_1.08v")
        victim.update(corner=donor["corner"], temp_c=donor["temp_c"],
                      vdd=donor["vdd"], corner_id=donor["corner_id"])
        code, _, err = _run(README, REPORT, offset=off)
        self.assertEqual(code, 1)
        self.assertIn(f"source {OFFSET_ID}", err)
        self.assertIn("duplicate identities are not distinct physical corners", err)
        self.assertIn("'fs_mismatch_-40c_1.08v'", err)

    def test_offset_metadata_identifier_disagreement_fails(self):
        off = _clone(OFFSET)
        off["points"][0]["temp_c"] = -39.0  # corner_id still says tt_mismatch_-40c_1.08v
        code, _, err = _run(README, REPORT, offset=off)
        self.assertEqual(code, 1)
        self.assertIn(f"source {OFFSET_ID}", err)
        self.assertIn("'tt_mismatch_-40c_1.08v' disagrees with its physical metadata", err)

    def test_offset_permuted_grid_passes(self):
        off = _clone(OFFSET)
        off["points"].reverse()
        code, _, err = _run(README, REPORT, offset=off)
        self.assertEqual(code, 0, err)

    def test_source_value_mutations_fail_naming_source(self):
        # A consistently changed campaign (summary follows the points) is a
        # different population: the README claim must fail against it.
        noise = _clone(NOISE)
        for pt in noise["points"]:
            pt["both"]["sigma"] *= 1.1
        sig = [pt["both"]["sigma"] for pt in noise["points"]]
        noise["configs"]["both"].update(grid_mean=sum(sig) / 45, min=min(sig), max=max(sig))
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 1)
        self.assertIn(f"source {NOISE_ID}", err)
        self.assertIn("noise(#81): grid mean mV rms: README says 1.305", err)
        self.assertIn("says 1.435", err)
        offset = _clone(OFFSET)
        offset["points"][0]["measurements"]["vos_3sig_mv"] = 16.0  # now a Target miss
        v3 = [pt["measurements"]["vos_3sig_mv"] for pt in offset["points"]]
        offset["summary"]["vos_3sig_mv"].update(
            max=16.0, mean=sum(v3) / 45, at_max=offset["points"][0]["corner_id"])
        code, _, err = _run(README, REPORT, offset=offset)
        self.assertEqual(code, 1)
        self.assertIn("Target met points: README says 45", err)
        self.assertIn(f"source {OFFSET_ID}", err)
        self.assertIn("says 44", err)

    def test_inconsistent_source_summary_is_rejected(self):
        noise = _clone(NOISE)
        noise["configs"]["both"]["grid_mean"] = 1.4
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 1)
        self.assertIn(f"source {NOISE_ID}", err)
        self.assertIn("disagree with the per-point sigmas", err)
        noise = _clone(NOISE)
        noise["configs"]["both"]["points_valid"] = 44
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 1)
        self.assertIn("points_valid 44", err)
        offset = _clone(OFFSET)
        offset["summary"]["vos_3sig_mv"]["max"] = 10.6
        code, _, err = _run(README, REPORT, offset=offset)
        self.assertEqual(code, 1)
        self.assertIn(f"source {OFFSET_ID}", err)
        self.assertIn("disagree with the per-point values", err)

    def test_different_population_cannot_match_by_coincidence(self):
        for mut, label in (
            (lambda d: d.update(campaign="20261009-other"), "campaign"),
            (lambda d: d.update(expected_n=60), "expected_n"),
            (lambda d: d["points"].pop(), "point count"),
            (lambda d: d["points"][3]["both"].update(n=60), "per-point n"),
        ):
            with self.subTest("noise " + label):
                noise = _clone(NOISE)
                mut(noise)
                code, _, err = _run(README, REPORT, noise=noise)
                self.assertEqual(code, 1)
                self.assertIn(f"source {NOISE_ID}", err)
        for mut, label in (
            (lambda d: d.update(record_id="20260916-125444-4d0cf7c"), "record id"),
            (lambda d: d["testbench"].update(name="comparator-offset-mc"), "bench"),
            (lambda d: d["points"].pop(), "point count"),
            (lambda d: d["points"][0]["measurements"].update(n_samples=200.0), "N per point"),
            (lambda d: d["points"][0].update(status="rejected"), "status"),
        ):
            with self.subTest("offset " + label):
                offset = _clone(OFFSET)
                mut(offset)
                code, _, err = _run(README, REPORT, offset=offset)
                self.assertEqual(code, 1)
                self.assertIn(f"source {OFFSET_ID}", err)

    def test_missing_malformed_or_restructured_sources_fail_clearly(self):
        for kind, raw in (("empty", ""), ("not json", "{oops"), ("array", "[]"), ("object", "{}")):
            with self.subTest("noise " + kind):
                code, _, err = _run(README, REPORT, raw_noise=raw)
                self.assertEqual(code, 1)
                self.assertIn(f"source {NOISE_ID}", err)
                self.assertIn("unavailable", err)
            with self.subTest("offset " + kind):
                code, _, err = _run(README, REPORT, raw_offset=raw)
                self.assertEqual(code, 1)
                self.assertIn(f"source {OFFSET_ID}", err)
        noise = _clone(NOISE)
        del noise["configs"]["both"]["grid_mean"]
        code, _, err = _run(README, REPORT, noise=noise)
        self.assertEqual(code, 1)
        self.assertIn("missing field configs.both.grid_mean", err)
        offset = _clone(OFFSET)
        del offset["summary"]["vos_3sig_mv"]
        code, _, err = _run(README, REPORT, offset=offset)
        self.assertEqual(code, 1)
        self.assertIn("missing field summary.vos_3sig_mv", err)

    def test_missing_source_file_fails_clearly(self):
        sources = chk.load_sources({NOISE_ID: Path("/nonexistent/noise_full.json")})
        self.assertIsInstance(sources[NOISE_ID], chk.SourceError)
        self.assertIn("/nonexistent/noise_full.json", str(sources[NOISE_ID]))
        self.assertIn("cannot read", str(sources[NOISE_ID]))

    def test_aggregate_check_without_sources_is_unchanged(self):
        failures, checked, _, src = chk.check(README, REPORT)
        self.assertEqual((failures, checked, src), ([], len(chk.CLAIMS), 0))


if __name__ == "__main__":
    unittest.main()

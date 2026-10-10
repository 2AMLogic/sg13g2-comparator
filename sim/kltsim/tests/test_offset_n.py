"""Tests for the declared offset draw count (issue #167). Stdlib only, engine-free.

A larger offset campaign (N = 200 per PVT point) is an explicit, recorded,
offset-only request. These tests pin: the historical defaults are unchanged,
an undeclared / wrong / invalid N is rejected before submission or at load,
populations must be exactly the declared N, and the offset-only yield index
carries its declaration without touching the historical one.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kltsim import benches, cli, declared_n, estimate, grade
from kltsim import yield_reports as yr
from kltsim.tests.test_grade import GRID
from kltsim.tests.test_yield_reports import offset_bench


class ValidateOffsetN(unittest.TestCase):
    def test_accepts_a_reasonable_count(self):
        for n in (2, 60, 183, 200, benches.OFFSET_MC_N_MAX):
            self.assertEqual(benches.validate_offset_n(n), n)

    def test_rejects_invalid_counts(self):
        for bad in (0, 1, -5, benches.OFFSET_MC_N_MAX + 1, True, 60.0, "200", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                benches.validate_offset_n(bad)

    def test_default_bench_is_the_unchanged_object(self):
        self.assertIs(benches.offset_mc_with_n(None), benches.OFFSET_MC)
        self.assertIs(benches.offset_mc_with_n(benches.OFFSET_MC_N), benches.OFFSET_MC)
        self.assertEqual(benches.OFFSET_MC.monte_carlo["n"], 60)

    def test_larger_bench_changes_only_n_and_prose(self):
        big = benches.offset_mc_with_n(200)
        self.assertEqual(big.monte_carlo["n"], 200)
        want = dict(benches.OFFSET_MC.monte_carlo, n=200)
        self.assertEqual(big.monte_carlo, want)
        for field in ("measurements", "analysis", "process_sections", "supply_keys", "probes"):
            self.assertEqual(getattr(big, field), getattr(benches.OFFSET_MC, field))
        self.assertIn("N = 200", big.description)
        self.assertEqual(benches.OFFSET_MC.monte_carlo["n"], 60)  # original untouched


class BuildOption(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def build(self, *extra, campaign="c"):
        err = io.StringIO()
        with mock.patch.object(cli, "CAMPAIGNS_DIR", self.root), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            try:
                code = cli.main(["build", "--campaign", campaign, *extra])
            except SystemExit as exc:  # argparse rejection
                code = exc.code
        return code, err.getvalue()

    def requests(self, campaign="c"):
        return sorted((self.root / campaign).glob("offset_mc.*.request.json"))

    def test_default_build_is_historical(self):
        code, _ = self.build("--bench", "offset_mc")
        self.assertEqual(code, 0)
        reqs = self.requests()
        self.assertEqual(len(reqs), 5)
        for path in reqs:
            self.assertEqual(json.loads(path.read_text())["monte_carlo"]["n"], 60)

    def test_declared_n_is_recorded_in_every_request(self):
        code, _ = self.build("--bench", "offset_mc", "--offset-n", "200")
        self.assertEqual(code, 0)
        reqs = self.requests()
        self.assertEqual(len(reqs), 5)
        for path in reqs:
            mc = json.loads(path.read_text())["monte_carlo"]
            self.assertEqual((mc["n"], mc["seed"], mc["vary"]), (200, 20260916, "mismatch"))

    def test_declared_default_n_is_byte_identical_to_the_default_build(self):
        self.build("--bench", "offset_mc", campaign="a")
        self.build("--bench", "offset_mc", "--offset-n", "60", campaign="b")
        for pa in self.requests("a"):
            self.assertEqual(pa.read_bytes(), (self.root / "b" / pa.name).read_bytes())

    def test_invalid_counts_are_rejected_before_anything_is_written(self):
        for bad in ("0", "1", "-3", "1001", "2.5", "many"):
            code, _ = self.build("--bench", "offset_mc", "--offset-n", bad, campaign="bad" + bad)
            self.assertNotEqual(code, 0, bad)
            self.assertFalse((self.root / ("bad" + bad)).exists(), bad)

    def test_requires_offset_bench_only(self):
        for extra in ((), ("--bench", "offset_mc", "--bench", "transient_noise"),
                      ("--bench", "transient_noise")):
            code, err = self.build(*extra, "--offset-n", "200")
            self.assertEqual(code, 2, extra)
            self.assertIn("--offset-n requires --bench offset_mc", err)
            self.assertFalse((self.root / "c").exists())


def _write_chain(directory: Path, tag: str):
    """A minimal envelope + invocation whose hashes match the saved request."""
    env = b"{}\n"
    (directory / f"{tag}.envelope.json").write_bytes(env)
    (directory / f"{tag}.invocation.json").write_text(json.dumps({
        "tag": tag,
        "request_sha256": hashlib.sha256((directory / f"{tag}.request.json").read_bytes()).hexdigest(),
        "envelope_sha256": hashlib.sha256(env).hexdigest(),
    }))


class DeclaredNAtTheLoadingBoundary(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        bench = benches.offset_mc_with_n(200)
        _, _, files = __import__("kltsim.build", fromlist=["x"]).plan_bench_inputs(
            bench, self.dir, target="batch")
        for path, data in files:
            path.write_bytes(data)
        for tag in ("offset_mc.mos_tt_mismatch",):
            _write_chain(self.dir, tag)

    def problems(self, n):
        return declared_n.load_campaign(self.dir, n, bench_names=("offset_mc",))["offset_mc"].chain_problems

    def test_declared_n_matches_the_saved_request(self):
        self.assertEqual(self.problems(200), [])

    def test_undeclared_n_is_rejected(self):
        problems = self.problems(None)
        self.assertTrue(any("monte_carlo" in p for p in problems), problems)

    def test_wrong_declared_n_is_rejected(self):
        for wrong in (60, 199, 201):
            problems = self.problems(wrong)
            self.assertTrue(any("monte_carlo" in p for p in problems), (wrong, problems))

    def test_grade_rows_use_the_declared_n_and_nothing_else_changes(self):
        rows = json.loads((grade.build_mod.EXPERIMENT_DIR / "rows.json").read_text())
        same = declared_n.with_offset_n(rows, None)
        self.assertIs(same, rows)
        spec = declared_n.with_offset_n(rows, 200)
        offset = [r for r in spec["rows"] if r["evidence"].get("bench") == "offset_mc"
                  and r["evidence"].get("expected_n")]
        self.assertTrue(offset and all(r["evidence"]["expected_n"] == 200 for r in offset))
        other = [r for r in spec["rows"] if r not in offset]
        orig = [r for r in rows["rows"] if r["id"] in {o["id"] for o in other}]
        self.assertEqual(other, orig)
        self.assertEqual(rows["rows"][0]["evidence"].get("expected_n") in (60, None), True)
        with self.assertRaises(ValueError):
            declared_n.with_offset_n(rows, 1)


class PopulationsAreExactlyTheDeclaredN(unittest.TestCase):
    def test_larger_population_is_complete_and_unpooled(self):
        pops = yr.collect_populations(offset_bench(n=200), "vos_mv", "mV", GRID, 200)
        self.assertEqual(len(pops), 45)
        for pop in pops.values():
            self.assertEqual((pop.attempted, len(pop.values)), (200, 200))
            self.assertEqual(pop.seeds, [1000 + k for k in range(200)])

    def test_historical_count_against_larger_declaration_is_rejected(self):
        with self.assertRaises(yr.YieldInputError) as cm:
            yr.collect_populations(offset_bench(n=60), "vos_mv", "mV", GRID, 200)
        self.assertIn("N = 200", str(cm.exception))

    def test_larger_count_against_historical_declaration_is_rejected(self):
        with self.assertRaises(yr.YieldInputError):
            yr.collect_populations(offset_bench(n=200), "vos_mv", "mV", GRID, 60)

    def test_missing_population_is_rejected(self):
        drop = {("tt", 1.2, 27)}
        with self.assertRaises(yr.YieldInputError) as cm:
            yr.collect_populations(offset_bench(n=200, drop=drop), "vos_mv", "mV", GRID, 200)
        self.assertIn("no Monte-Carlo population", str(cm.exception))

    def test_one_draw_short_is_rejected(self):
        with self.assertRaises(yr.YieldInputError) as cm:
            yr.collect_populations(offset_bench(n=199), "vos_mv", "mV", GRID, 200)
        self.assertIn("199 draws", str(cm.exception))


class SelectionAndSource(unittest.TestCase):
    def test_selection_validation(self):
        self.assertEqual(yr.validate_selection(None, yr.ROWS_BOTH), (None, yr.ROWS_BOTH))
        self.assertEqual(yr.validate_selection(60, yr.ROWS_BOTH), (None, yr.ROWS_BOTH))
        self.assertEqual(yr.validate_selection(200, yr.ROWS_OFFSET), (200, yr.ROWS_OFFSET))
        for bad in ((1, yr.ROWS_BOTH), (True, yr.ROWS_BOTH), (200, ("2",)), (200, ())):
            with self.assertRaises(yr.YieldInputError, msg=repr(bad)):
                yr.validate_selection(*bad)

    def test_wrong_n_against_the_historical_source_is_rejected(self):
        with self.assertRaises(yr.YieldInputError) as cm:
            yr.derive_inputs(yr.REPO_ROOT / yr.SOURCE_CAMPAIGN, 200, yr.ROWS_OFFSET)
        self.assertIn("rejected evidence", str(cm.exception))

    def test_offset_only_reads_no_noise_evidence(self):
        derived = yr.derive_inputs(yr.REPO_ROOT / yr.SOURCE_CAMPAIGN, None, yr.ROWS_OFFSET)
        self.assertIsNone(derived["noise_doc"])
        self.assertEqual(set(derived["benches"]), {"offset_mc"})
        both = yr.derive_inputs(yr.REPO_ROOT / yr.SOURCE_CAMPAIGN)
        self.assertEqual(yr.dumps(derived["offset_doc"]), yr.dumps(both["offset_doc"]))

    def test_historical_index_is_reproduced_byte_for_byte(self):
        cid = yr.DEFAULT_CAMPAIGN_ID
        out = yr.REPO_ROOT / yr.OUT_ROOT / cid
        committed = json.loads((out / "index.json").read_text())
        derived = yr.derive_inputs(yr.REPO_ROOT / yr.SOURCE_CAMPAIGN)
        raw = {k: (out / f"{k}.yield.json").read_bytes() for k in ("offset", "noise")}
        reports = {k: json.loads(v) for k, v in raw.items()}
        tool = committed["tool"]
        index = yr.build_index(cid, yr.SOURCE_CAMPAIGN, derived, reports, raw,
                               tool["klt_version_reported"], yr.load_pin(), tool["command"])
        self.assertEqual(yr.dumps(index), (out / "index.json").read_text())
        self.assertNotIn("declared", index)

    def test_offset_only_index_carries_its_declaration(self):
        cid = yr.DEFAULT_CAMPAIGN_ID
        out = yr.REPO_ROOT / yr.OUT_ROOT / cid
        derived = yr.derive_inputs(yr.REPO_ROOT / yr.SOURCE_CAMPAIGN, None, yr.ROWS_OFFSET)
        raw = {"offset": (out / "offset.yield.json").read_bytes()}
        tool = json.loads((out / "index.json").read_text())["tool"]
        index = yr.build_index(cid, yr.SOURCE_CAMPAIGN, derived, {"offset": json.loads(raw["offset"])},
                               raw, tool["klt_version_reported"], yr.load_pin(), tool["command"])
        self.assertEqual([r["row_id"] for r in index["rows"]], ["1"])
        d = index["declared"]
        self.assertEqual((d["rows"], d["attempted_per_population"]), (["1"], [60]))
        self.assertEqual(len(d["points_reporting_insufficient_or_no_verdict"]), 45)
        self.assertEqual(d["max_required_n_reported_by_engine"], 183)
        self.assertNotIn("row2_target_mv", index["ratified_summary"])
        self.assertIn("#82", index["source"]["realization_note"])


class CheckRejectsStaleDeclarations(unittest.TestCase):
    def test_wrong_cli_n_against_the_historical_campaign(self):
        problems = yr.check(yr.DEFAULT_CAMPAIGN_ID, offset_n=200)
        self.assertTrue(any("does not match the campaign's declared" in p for p in problems), problems)

    def test_stale_source_is_rejected(self):
        problems = yr.check(yr.DEFAULT_CAMPAIGN_ID, source_rel="sim/klt-corner-verification/campaigns/other")
        self.assertTrue(any("stale source" in p for p in problems), problems)

    def test_missing_campaign_is_a_problem_not_a_crash(self):
        self.assertTrue(yr.check("no-such-campaign"))

    def test_historical_campaign_still_checks_clean(self):
        self.assertEqual(yr.check(yr.DEFAULT_CAMPAIGN_ID), [])


class CommittedLargerCampaign(unittest.TestCase):
    campaign = grade.build_mod.EXPERIMENT_DIR / "campaigns" / "20261010-n200"

    def test_committed_grading_regenerates_from_the_declared_n(self):
        result = declared_n.grade_campaign(self.campaign, 200)
        self.assertEqual(result["declared_offset_n"], 200)
        committed = (self.campaign / "grading.json").read_text(encoding="utf-8")
        self.assertEqual(grade.dumps_strict(result, indent=2) + "\n", committed)
        row1 = next(r for r in result["rows"] if r["id"] == "1")
        self.assertEqual(row1["target_verdict"], "PASS")
        self.assertEqual(row1["target"]["points_valid"], 45)

    def test_committed_requests_carry_the_declared_n_and_nothing_else_differs(self):
        hist = grade.build_mod.EXPERIMENT_DIR / "campaigns" / "20261009-d73a9ac"
        for path in sorted(self.campaign.glob("offset_mc.*.request.json")):
            new = json.loads(path.read_text())
            old = json.loads((hist / path.name).read_text())
            self.assertEqual(new["monte_carlo"]["n"], 200)
            new["monte_carlo"]["n"] = old["monte_carlo"]["n"]
            new["_comment"], old["_comment"] = None, None
            self.assertEqual(new, old)

    def test_historical_load_is_the_unchanged_grade_path(self):
        a = declared_n.load_campaign(grade.build_mod.EXPERIMENT_DIR / "campaigns" / "20261009-d73a9ac",
                                     None, bench_names=("offset_mc",))["offset_mc"]
        self.assertEqual(a.chain_problems, [])
        wrong = declared_n.load_campaign(grade.build_mod.EXPERIMENT_DIR / "campaigns" / "20261009-d73a9ac",
                                         200, bench_names=("offset_mc",))["offset_mc"]
        self.assertTrue(wrong.chain_problems)


class SizeEstimate(unittest.TestCase):
    """Hermetic (no git): CI's sparse partial clone cannot list historical blobs."""

    REF = [("offset_mc.body.spice", 1_000), ("offset_mc.mos_tt_mismatch.request.json", 2_000),
           ("offset_mc.mos_tt_mismatch.invocation.json", 700),
           ("offset_mc.mos_tt_mismatch.envelope.json", 1_000_000),
           ("artifacts/offset_mc.mos_tt_mismatch/x/ngspice.log", 600_000),
           ("transient_noise.mos_tt.envelope.json", 9_000_000), ("grading.json", 80_000)]
    YIELD = [("y/offset.yield.json", 100_000), ("y/index.json", 50_000), ("y/noise.yield.json", 500_000)]
    BUDGET = {"new_unit_ceiling_bytes": 4_000_000, "total_ceiling_bytes": 100_000_000}

    def est(self, n, current=10_000_000):
        return estimate.estimate_from_sizes(n, "ref", "HEAD", self.REF, self.YIELD, self.BUDGET, current)

    def test_scales_per_sample_files_only_and_ignores_other_benches(self):
        a, b = self.est(60), self.est(120)
        fixed = 1_000 + 2_000 + 700
        self.assertEqual(a["campaign_unit_bytes"], fixed + 1_600_000 + estimate.GRADING_ALLOWANCE)
        self.assertEqual(b["campaign_unit_bytes"], fixed + 3_200_000 + estimate.GRADING_ALLOWANCE)
        self.assertEqual(b["yield_unit_bytes"], 2 * a["yield_unit_bytes"])  # noise report excluded
        self.assertEqual(a["yield_unit_bytes"], 150_000)

    def test_over_ceiling_requires_an_exception(self):
        self.assertTrue(self.est(60)["within_budget"])
        big = self.est(200)
        self.assertFalse(big["within_budget"])
        self.assertIn("campaign", big["units_over_ceiling"])
        self.assertIn("EXCEPTION REQUIRED", estimate.render(big))

    def test_total_ceiling_is_checked_separately(self):
        e = self.est(60, current=99_000_000)
        self.assertEqual(e["units_over_ceiling"], {})
        self.assertFalse(e["within_budget"])
        self.assertGreater(e["total_over_ceiling_bytes"], 0)

    def test_missing_reference_evidence_is_an_error(self):
        with self.assertRaises(estimate.EstimateError):
            estimate.estimate_from_sizes(200, "ref", "HEAD", [("grading.json", 1)], [], self.BUDGET, 0)

    def test_cli_rejects_invalid_n(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.cmd_estimate(argparse.Namespace(
                offset_n=1, reference_campaign="20261009-d73a9ac", tree="HEAD")), 2)


if __name__ == "__main__":
    unittest.main()

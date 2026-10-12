"""Tests for the `klt yield` evidence workflow (issue #63). Stdlib only.

Engine-free; runs in CI's kltsim unit-test step. The tests that execute the
pinned native `klt yield` engine are in ``engine_yield_reports.py`` (not
matched by CI's ``test_*.py`` discovery, which forbids skipped tests; run
explicitly, see sim/klt-yield/README.md).
"""

from __future__ import annotations

import copy
import json
import math
import statistics
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from kltsim import grade
from kltsim import yield_reports as yr
from kltsim.benches import BENCHES, PROCESSES, SUPPLIES_V, TEMPERATURES_C
from kltsim.tests.test_grade import GRID, _corner, _probe_values

POINTS = [(p, v, t) for p in PROCESSES for v in SUPPLIES_V for t in TEMPERATURES_C]


def _with_seed(corner, k):
    corner["monte_carlo"] = {"sample_index": k, "seed": 1000 + k}
    return corner


def offset_bench(n=60, vos=lambda p, v, t, k: ((k % 11) - 5) * 1.5, mutate=None, drop=(),
                 chain_problems=None):
    bench = BENCHES["offset_mc"]
    corners = []
    for (p, v, t) in POINTS:
        if (p, v, t) in drop:
            continue
        for k in range(n):
            vals = _probe_values(bench, v, t)
            vals.update({"lowcount": 16.0, "vos_mv": vos(p, v, t, k)})
            c = _with_seed(_corner(bench, p, v, t, vals, sample=k), k)
            if mutate:
                mutate(c, (p, v, t), k)
            corners.append(c)
    # one deterministic (non-sampled) corner per point that must be ignored
    for (p, v, t) in POINTS[:2]:
        vals = _probe_values(bench, v, t)
        vals.update({"lowcount": 16.0, "vos_mv": 999.0})
        corners.append(_corner(bench, p, v, t, vals))
    env = {"corners": corners, "measurements": []}
    return grade.BenchEvidence("offset_mc", [("offset_mc", env)], None,
                               chain_problems=list(chain_problems or []))


def noise_bench(n=80, kplus=60, kminus=20, kzero=40, mutate=None):
    bench = BENCHES["transient_noise"]
    corners, draw = [], 0
    for (p, v, t) in POINTS:
        for k in range(n):
            draw += 1
            vals = _probe_values(bench, v, t)
            vals.update({"vn0_a": draw * 1e-6, "vn0_b": -draw * 1e-6, "vn1_a": draw * 2e-6,
                         "res_zero": 0.5, "res_plus": 0.5, "res_minus": 0.5,
                         "hit_plus": 1.0 if k < kplus else 0.0,
                         "hit_minus": 1.0 if k < kminus else 0.0,
                         "hit_zero": 1.0 if k < kzero else 0.0})
            c = _with_seed(_corner(bench, p, v, t, vals, sample=k), k)
            if mutate:
                mutate(c, (p, v, t), k)
            corners.append(c)
    return grade.BenchEvidence("transient_noise", [("transient_noise", {"corners": corners})], None)


def _set_value(corner, name, value):
    for m in corner["measurements"]:
        if m["name"] == name:
            m["value"] = value


def collect_offset(bench, n=60):
    return yr.collect_populations(bench, "vos_mv", "mV", GRID, n)


class PopulationExtraction(unittest.TestCase):
    def test_groups_per_pvt_and_ignores_deterministic_corners(self):
        pops = collect_offset(offset_bench())
        self.assertEqual(len(pops), 45)
        self.assertEqual(len({p.corner_id for p in pops.values()}), 45)
        for pop in pops.values():
            self.assertEqual((pop.attempted, len(pop.values)), (60, 60))
            self.assertNotIn(999.0, pop.values)
            self.assertEqual(pop.value_indices, list(range(60)))
            self.assertEqual(pop.seeds, [1000 + k for k in range(60)])

    def test_populations_are_not_pooled(self):
        bench = offset_bench(vos=lambda p, v, t, k: {"tt": 1.0, "ff": 2.0}.get(p, 3.0))
        doc = yr.sample_set(collect_offset(bench), prefix="vos_mv", unit="mV",
                            limits_for={"min": -15.0, "max": 15.0})
        by_name = {m["name"]: m for m in doc["measurements"]}
        self.assertEqual(set(by_name["vos_mv@tt_27c_1.20v"]["samples"]), {1.0})
        self.assertEqual(set(by_name["vos_mv@ff_27c_1.20v"]["samples"]), {2.0})
        self.assertEqual(len(doc["measurements"]), 45)

    def test_exclusions_are_accounted_not_dropped(self):
        def mutate(c, pt, k):
            if pt == ("tt", 1.2, 27):
                if k == 0:
                    _set_value(c, "vos_mv", None)                 # no value
                if k == 1:
                    _set_value(c, "vos_mv", float("nan"))          # non-finite
                if k == 2:
                    _set_value(c, "vos_mv", float("inf"))
                if k == 3:
                    _set_value(c, "vdd_meas", 0.9)                 # supply probe mismatch
                if k == 4:
                    c["status"] = "error"
                if k == 5:
                    c["measurements"].append(dict(c["measurements"][0]))  # duplicate name
        pops = collect_offset(offset_bench(mutate=mutate))
        pop = pops["tt_27c_1.20v"]
        self.assertEqual(pop.attempted, 60)
        self.assertEqual(len(pop.values), 54)
        cats = {e["sample_index"]: e["category"] for e in pop.excluded}
        self.assertEqual(cats, {0: "errored", 1: "inconclusive", 2: "inconclusive",
                                3: "inconclusive", 4: "errored", 5: "inconclusive"})
        self.assertTrue(all(math.isfinite(v) for v in pop.values))
        doc = yr.sample_set({"x": pop}, prefix="vos_mv", unit="mV",
                            limits_for={"min": -15.0, "max": 15.0})
        m = doc["measurements"][0]
        self.assertEqual((len(m["samples"]), m["errored"], m["inconclusive"]), (54, 2, 4))

    def test_wrong_unit_is_not_consumed(self):
        def mutate(c, pt, k):
            if pt == ("ss", 1.08, -40) and k == 7:
                for m in c["measurements"]:
                    if m["name"] == "vos_mv":
                        m["unit"] = "ns"
        pop = collect_offset(offset_bench(mutate=mutate))["ss_-40c_1.08v"]
        self.assertEqual([e["sample_index"] for e in pop.excluded], [7])
        self.assertEqual(len(pop.values), 59)

    def test_duplicate_population_rejected(self):
        bench = offset_bench()
        env = copy.deepcopy(bench.envelopes[0][1])
        bench.envelopes.append(("again", env))   # same samples reported twice
        with self.assertRaises(yr.YieldInputError):
            collect_offset(bench)

    def test_missing_population_rejected(self):
        with self.assertRaises(yr.YieldInputError) as cm:
            collect_offset(offset_bench(drop={("tt", 1.2, 27)}))
        self.assertIn("tt_27c_1.20v", str(cm.exception))

    def test_wrong_sample_count_rejected(self):
        with self.assertRaises(yr.YieldInputError):
            collect_offset(offset_bench(n=59))

    def test_insufficient_usable_samples_rejected(self):
        def mutate(c, pt, k):
            if pt == ("fs", 1.32, 125) and k >= 1:
                _set_value(c, "vos_mv", None)
        with self.assertRaises(yr.YieldInputError) as cm:
            collect_offset(offset_bench(mutate=mutate))
        self.assertIn("usable", str(cm.exception))

    def test_chain_problem_rejects_the_whole_bench(self):
        with self.assertRaises(yr.YieldInputError):
            collect_offset(offset_bench(chain_problems=["offset_mc: request_sha256 mismatch"]))

    def test_outside_grid_corner_rejected(self):
        bench = offset_bench()
        stray = copy.deepcopy(bench.envelopes[0][1]["corners"][0])
        stray["supply_v"] = {"vsup": 1.5}
        bench.envelopes[0][1]["corners"].append(stray)
        with self.assertRaises(yr.YieldInputError):
            collect_offset(bench)

    def test_noise_binary_and_repeated_draws(self):
        def mutate(c, pt, k):
            if pt == ("tt", 1.2, 27) and k == 9:
                _set_value(c, "hit_plus", 0.5)         # not a 0/1 outcome
        bench = noise_bench(mutate=mutate)
        # make sample 1 repeat sample 0's draw
        by_id = {c["corner_id"]: c for c in bench.envelopes[0][1]["corners"]}
        base = "mos_tt/1.200V/27C"
        for name in ("vn0_a", "vn0_b", "vn1_a"):
            _set_value(by_id[f"{base}/mc1"], name, next(
                m["value"] for m in by_id[f"{base}/mc0"]["measurements"] if m["name"] == name))
        pop = yr.collect_populations(bench, "hit_plus", "1", GRID, 80, binary=True,
                                     independence=True)["tt_27c_1.20v"]
        idx = {e["sample_index"] for e in pop.excluded}
        self.assertEqual(idx, {0, 1, 9})   # both copies of the repeated draw + the non-binary one


class DocumentsAndStatistics(unittest.TestCase):
    def test_control_is_over_limit_and_shifted_by_construction(self):
        limits = {"min": -15.0, "max": 15.0}
        self.assertEqual(yr.control_shift(limits), 30.0)
        # a draw exactly on the lower limit would land on the upper one: refused
        edge = collect_offset(offset_bench(vos=lambda p, v, t, k: -15.0 if k == 0 else 14.0))
        with self.assertRaises(yr.YieldInputError):
            yr.sample_set(edge, prefix="vos_mv", unit="mV", limits_for=limits, with_control=True)
        pops = collect_offset(offset_bench(vos=lambda p, v, t, k: -14.9 if k == 0 else 14.9))
        doc = yr.sample_set(pops, prefix="vos_mv", unit="mV", limits_for=limits, with_control=True)
        for m in doc["measurements"]:
            ctl = m["negative_control"]["samples"]
            self.assertEqual(len(ctl), len(m["samples"]))
            self.assertTrue(all(not -15.0 <= x <= 15.0 for x in ctl))
            for c, x in zip(ctl, m["samples"]):
                self.assertAlmostEqual(c - x, 30.0)

    def test_derived_documents_are_deterministic(self):
        a = yr.dumps(yr.sample_set(collect_offset(offset_bench()), prefix="vos_mv", unit="mV",
                                   limits_for={"min": -15.0, "max": 15.0}, with_control=True))
        b = yr.dumps(yr.sample_set(collect_offset(offset_bench()), prefix="vos_mv", unit="mV",
                                   limits_for={"min": -15.0, "max": 15.0}, with_control=True))
        self.assertEqual(a, b)
        self.assertNotIn("NaN", a)

    def test_ratified_offset_statistic_matches_grader_reduction(self):
        pops = collect_offset(offset_bench(vos=lambda p, v, t, k: ((k % 7) - 3) * 3.0))
        pop = pops["tt_27c_1.20v"]
        mine = yr.ratified_offset_3sigma(pop, 3.0)
        s = statistics.stdev(pop.values)
        self.assertAlmostEqual(mine, grade.three_sigma_dr_basis(60, s, 3.0))
        # the ratified statistic is not the raw per-draw yield and not 3 x Bessel sigma
        self.assertLess(mine, 3.0 * s)

    def test_ratified_noise_statistic_matches_grader_formula_and_saturation(self):
        pops = {n: yr.collect_populations(noise_bench(), n, "1", GRID, 80, binary=True)
                for n in ("hit_plus", "hit_minus")}
        r = yr.ratified_noise_sigma(pops["hit_plus"]["tt_27c_1.20v"],
                                    pops["hit_minus"]["tt_27c_1.20v"], 1.0)
        self.assertAlmostEqual(r["sigma_mv"], grade.probit_slope_sigma(0.75, 0.25, 1.0))
        sat = {n: yr.collect_populations(noise_bench(kplus=80), n, "1", GRID, 80, binary=True)
               for n in ("hit_plus", "hit_minus")}
        r = yr.ratified_noise_sigma(sat["hit_plus"]["tt_27c_1.20v"],
                                    sat["hit_minus"]["tt_27c_1.20v"], 1.0)
        self.assertIsNone(r["sigma_mv"])
        self.assertIn("saturated", r["problem"])


FAKE_ERR = ("import json,sys\n"
            "a=sys.argv[1:]\n"
            "if a==['--version']: print('klt ' + %r)\n"
            "else: print(json.dumps({'schema_version':1,'error':{'command':'yield','message':"
            "'the klt_yield_native extension is not installed'}})); sys.exit(1)\n")


class EngineFailuresAreNeverResults(unittest.TestCase):
    pin = yr.load_pin()

    def test_missing_executable(self):
        with self.assertRaises(yr.EngineError):
            yr.engine_preflight(["/nonexistent/klt"], self.pin)

    def test_missing_native_extension(self):
        cmd = [sys.executable, "-c", FAKE_ERR % self.pin["klt_version"]]
        with self.assertRaises(yr.EngineError) as cm:
            yr.engine_preflight(cmd, self.pin)
        self.assertIn("not installed", str(cm.exception))
        with self.assertRaises(yr.EngineError):
            yr.run_yield(cmd, "sim/klt-yield/README.md")

    def test_wrong_version_refused(self):
        cmd = [sys.executable, "-c", FAKE_ERR % "9.9.9"]
        with self.assertRaises(yr.EngineError) as cm:
            yr.engine_preflight(cmd, self.pin)
        self.assertIn("pin", str(cm.exception))

    def test_generate_leaves_nothing_when_engine_missing(self):
        out = yr.REPO_ROOT / yr.OUT_ROOT / "unit-test-never-written"
        with self.assertRaises(yr.EngineError):
            yr.generate("unit-test-never-written", ["/nonexistent/klt"])
        self.assertFalse(out.exists())


class CommittedCampaign(unittest.TestCase):
    """Properties of the committed evidence, engine-free."""

    cid = yr.DEFAULT_CAMPAIGN_ID

    @classmethod
    def setUpClass(cls):
        cls.dir = yr.REPO_ROOT / yr.OUT_ROOT / cls.cid
        cls.index = json.loads((cls.dir / "index.json").read_text(encoding="utf-8"))

    def test_check_passes_on_committed_tree(self):
        self.assertEqual(yr.check(self.cid), [])

    def test_historical_campaign_is_superseded_not_broken(self):
        """Item 6 now cites the later N = 200 campaign; the historical one still
        checks clean on its own and is simply not the cited campaign."""
        self.assertEqual(yr.check(self.cid), [])
        problems = yr.check(self.cid, require_cited=True)
        self.assertTrue(any("manifest item 6 cites" in p for p in problems), problems)

    def test_every_point_accounted_and_controls_detected(self):
        off = self.index["rows"][0]
        self.assertEqual(len(off["populations"]), 45)
        for p in off["populations"]:
            self.assertEqual((p["attempted"], p["usable"], p["errored"], p["inconclusive"]),
                             (60, 60, 0, 0))
            self.assertEqual(len(p["sample_seeds"]), 60)
            self.assertEqual(p["yield"]["negative_control_verdict"], "detected")
            self.assertTrue(p["ratified_statistic"]["agrees_with_grader"])
            self.assertEqual(p["yield"]["confidence"], 0.95)
        noise = self.index["rows"][1]
        self.assertFalse(noise["citable_for_item6"])
        self.assertEqual(len(noise["populations"]), 45)

    def test_zero_failures_are_never_reported_as_proof(self):
        report = json.loads((self.dir / "offset.yield.json").read_text())
        for m in report["measurements"]:
            self.assertEqual(m["yield"]["empirical"]["estimate"], 1.0)
            self.assertLess(m["yield"]["empirical"]["confidence_interval"]["low"], 1.0)
            self.assertTrue(any("not \"100% yield\"" in w for w in m["warnings"]))
            self.assertEqual(m["sample_size"]["verdict"], "insufficient")

    def test_smoke_control_is_labelled_injection_only(self):
        c = self.index["mismatch_off_smoke_control"]
        self.assertEqual(c["mismatch_off"]["stddev_mv"], 0.0)
        self.assertGreater(c["mismatch_on"]["stddev_mv"], 0.0)
        self.assertTrue(c["mismatch_off_inside_limits"])
        self.assertIn("not a known-bad yield control", c["reading"])

    def test_source_campaign_bytes_match_the_chain(self):
        # the source envelopes analysed are the ones the invocation records hash
        src = yr.REPO_ROOT / yr.SOURCE_CAMPAIGN
        benches = grade.load_campaign(src, bench_names=("offset_mc", "transient_noise"))
        for b in benches.values():
            self.assertEqual(b.chain_problems, [])
            self.assertEqual(len(b.envelopes), 5)


class CitedLargerCampaign(unittest.TestCase):
    """Issue #167: the campaign item 6 cites (N = 200 per PVT point, offset only)."""

    cid = "20261010-n200"
    source = "sim/klt-corner-verification/campaigns/20261010-n200"

    @classmethod
    def setUpClass(cls):
        cls.dir = yr.REPO_ROOT / yr.OUT_ROOT / cls.cid
        cls.index = json.loads((cls.dir / "index.json").read_text(encoding="utf-8"))

    def check(self, **kw):
        return yr.check(self.cid, self.source, require_cited=True, **kw)

    def test_check_passes_and_item_six_cites_it(self):
        self.assertEqual(self.check(offset_n=200), [])

    def test_undeclared_or_wrong_n_is_rejected(self):
        for wrong in (60, 199, 183):
            problems = self.check(offset_n=wrong)
            self.assertTrue(any("does not match the campaign's declared" in p for p in problems),
                            (wrong, problems))

    def test_stale_source_is_rejected(self):
        problems = yr.check(self.cid, yr.SOURCE_CAMPAIGN, require_cited=True)
        self.assertTrue(problems)
        self.assertTrue(any("stale source" in p for p in problems), problems)

    def test_stale_manifest_pin_is_rejected(self):
        manifest = json.loads((yr.REPO_ROOT / "manifests/sg13g2-comparator.json").read_text())
        manifest["evidence"]["6"]["content_hash"] = "sha256:" + "0" * 64
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.json"
            path.write_text(json.dumps(manifest))
            problems = self.check(manifest_path=str(path))
        self.assertTrue(any("content_hash" in p for p in problems), problems)

    def test_manifest_repointed_at_the_wrong_report_is_rejected(self):
        manifest = json.loads((yr.REPO_ROOT / "manifests/sg13g2-comparator.json").read_text())
        manifest["evidence"]["6"]["file"] = "sim/klt-yield/campaigns/20261010-d73a9ac/offset.yield.json"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.json"
            path.write_text(json.dumps(manifest))
            problems = self.check(manifest_path=str(path))
        self.assertTrue(any("manifest item 6 cites" in p for p in problems), problems)

    def test_uncited_item_six_is_rejected(self):
        manifest = json.loads((yr.REPO_ROOT / "manifests/sg13g2-comparator.json").read_text())
        del manifest["evidence"]["6"]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.json"
            path.write_text(json.dumps(manifest))
            problems = self.check(manifest_path=str(path))
        self.assertTrue(any("cites no item 6" in p for p in problems))

    def test_every_population_is_exactly_200_and_adequate(self):
        d = self.index["declared"]
        self.assertEqual((d["offset_n"], d["rows"], d["attempted_per_population"]), (200, ["1"], [200]))
        self.assertEqual(d["points_reporting_insufficient_or_no_verdict"], [])
        self.assertEqual(self.index["source"]["campaign"], self.source)
        self.assertEqual([r["row_id"] for r in self.index["rows"]], ["1"])
        pops = self.index["rows"][0]["populations"]
        self.assertEqual(len(pops), 45)
        for p in pops:
            self.assertEqual((p["attempted"], p["usable"], p["errored"], p["inconclusive"], p["excluded"]),
                             (200, 200, 0, 0, []))
            self.assertEqual(len(p["sample_seeds"]), 200)
            self.assertEqual(len(set(p["sample_seeds"])), 200)
            self.assertEqual(p["yield"]["n"], 200)
            self.assertEqual(p["yield"]["sample_size_verdict"], "sufficient")
            self.assertEqual(p["yield"]["negative_control_verdict"], "detected")
            self.assertTrue(p["ratified_statistic"]["agrees_with_grader"])

    def test_yield_and_ratified_statistics_stay_separate_and_failures_disclosed(self):
        summary = self.index["ratified_summary"]
        self.assertLessEqual(summary["row1_worst_3sigma_mv"], summary["row1_target_mv"])
        self.assertEqual(summary["row1_target_mv"], 15.0)
        self.assertIn("points_with_observed_target_failures", self.index["declared"])
        for p in self.index["rows"][0]["populations"]:
            self.assertNotEqual(p["yield"]["empirical_estimate"], p["ratified_statistic"]["value_mv"])
            if p["yield"]["empirical_estimate"] == 1.0:
                self.assertLess(p["yield"]["ci_low"], 1.0)  # zero failures are a bound, not proof

    def test_issue_82_warning_and_preflight_are_retained(self):
        self.assertIn("#82", self.index["source"]["realization_note"])
        pre = self.index["mismatch_off_smoke_control"]["preflight"]
        self.assertTrue(pre["mismatch_seeds_distinct"] and pre["mismatch_on_spread_nonzero"]
                        and pre["mismatch_off_spread_zero"])
        self.assertIn("preflight", self.index["mismatch_off_smoke_control"]["path"])

    def test_report_names_the_samples_the_manifest_pins(self):
        manifest = json.loads((yr.REPO_ROOT / "manifests/sg13g2-comparator.json").read_text())
        cite = manifest["evidence"]["6"]
        report = json.loads((yr.REPO_ROOT / cite["file"]).read_text())
        self.assertEqual(report["samples"], self.index["rows"][0]["samples"])
        self.assertEqual(cite["content_hash"], "sha256:" + yr.sha256_file(yr.REPO_ROOT / report["samples"]))

    def test_frozen_signoff_report_agrees_with_the_citation(self):
        frozen = json.loads((yr.REPO_ROOT / "manifests/t1-signoff-report.json").read_text())
        item = next(i for i in frozen["items"] if i["id"] == 6)
        manifest = json.loads((yr.REPO_ROOT / "manifests/sg13g2-comparator.json").read_text())
        cite = manifest["evidence"]["6"]
        self.assertEqual((item["citation"]["file"], item["citation"]["content_hash"]),
                         (cite["file"], cite["content_hash"]))
        self.assertEqual(item["citation"]["yield_campaign"]["sample_size"], "sufficient")
        others = {i["id"]: i["status"] for i in frozen["items"] if i["id"] != 6}
        self.assertIn("unmet", others.values())  # other T1 failures remain visible


class IndexMutationMixin:
    """Issue #255: the engine-free `check` re-derives the index (yield and
    interval numbers, ratified statistics, population identity/completeness,
    declared block, summary, settings) and re-renders the Markdown instead of
    trusting the saved claims. Each test copies the committed campaign to a
    temp directory and mutates exactly one index.md/index.json field; sample
    and report bytes stay untouched so the existing hash checks still pass and
    only the re-derivation can catch the mutation. Row-1 mutations live here;
    concrete TestCase subclasses point ``cid`` at a campaign (a mixin, so
    unittest never collects this class by itself — CI forbids skips, and the
    offset-only campaign must not inherit noise-row tests)."""

    cid = yr.DEFAULT_CAMPAIGN_ID

    def check(self) -> list[str]:
        return yr.check(self.cid)

    def mutated_problems(self, mutate=None, mutate_md=None) -> list[str]:
        real_dir = yr.REPO_ROOT / yr.OUT_ROOT / self.cid
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shutil.copytree(real_dir, root / self.cid)
            if mutate:
                index = json.loads((root / self.cid / "index.json").read_text(encoding="utf-8"))
                mutate(index)
                (root / self.cid / "index.json").write_text(yr.dumps(index), encoding="utf-8")
            if mutate_md:
                mutate_md(root / self.cid / "index.md")
            saved_out_root, yr.OUT_ROOT = yr.OUT_ROOT, str(root)
            try:
                problems = self.check()
            finally:
                yr.OUT_ROOT = saved_out_root
        if not problems:
            raise AssertionError("the mutation was not reported")
        return problems

    def assert_diff_names(self, fragment: str, problems: list[str]):
        self.assertTrue(any(fragment in p for p in problems), (fragment, problems))

    def test_yield_empirical_estimate(self):
        def m(index):
            p = index["rows"][0]["populations"][3]
            p["yield"]["empirical_estimate"] -= 0.05
        self.assert_diff_names("populations[3].yield.empirical_estimate",
                               self.mutated_problems(m))

    def test_confidence_interval(self):
        def m(index):
            p = index["rows"][0]["populations"][7]
            p["yield"]["ci_low"] -= 0.05
        self.assert_diff_names("populations[7].yield.ci_low", self.mutated_problems(m))

    def test_ratified_value_mv_cannot_be_concealed_by_the_flag(self):
        # the stored boolean stays true; the recomputed number still disagrees
        def m(index):
            p = index["rows"][0]["populations"][11]
            p["ratified_statistic"]["value_mv"] *= 0.5
            p["ratified_statistic"]["agrees_with_grader"] = True
        problems = self.mutated_problems(m)
        self.assert_diff_names("populations[11].ratified_statistic.value_mv", problems)

    def test_population_source_corner(self):
        def m(index):
            index["rows"][0]["populations"][5]["source_corner"] = "mos_tt/1.200V/27C"
        self.assert_diff_names("populations[5].source_corner", self.mutated_problems(m))

    def test_population_sample_seeds(self):
        def m(index):
            index["rows"][0]["populations"][9]["sample_seeds"][0] += 1
        self.assert_diff_names("populations[9].sample_seeds[0]", self.mutated_problems(m))

    def test_population_usable_count(self):
        def m(index):
            index["rows"][0]["populations"][13]["usable"] -= 1
        self.assert_diff_names("populations[13].usable", self.mutated_problems(m))

    def test_population_excluded_list(self):
        def m(index):
            index["rows"][0]["populations"][13]["excluded"] = [
                {"sample_index": 0, "category": "errored", "reason": "tampered"}]
        self.assert_diff_names("populations[13].excluded", self.mutated_problems(m))

    def test_ratified_summary(self):
        def m(index):
            index["ratified_summary"]["row1_worst_3sigma_mv"] *= 0.9
        self.assert_diff_names("ratified_summary.row1_worst_3sigma_mv",
                               self.mutated_problems(m))

    def test_report_settings(self):
        def m(index):
            index["rows"][0]["settings"]["measurement_count"] += 1
        self.assert_diff_names("rows[0].settings.measurement_count",
                               self.mutated_problems(m))

    def test_markdown_text(self):
        def md(path):
            path.write_text(path.read_text(encoding="utf-8") + "<!-- tampered -->\n",
                            encoding="utf-8")
        self.assert_diff_names("index.md does not match render_index_md",
                               self.mutated_problems(mutate_md=md))


class HistoricalIndexMutations(IndexMutationMixin, unittest.TestCase):
    """The N = 60 rows 1+2 campaign (no declared block): the inherited row-1
    mutations plus the noise-row ones only this shape has."""

    cid = yr.DEFAULT_CAMPAIGN_ID

    def test_noise_rung_interval(self):
        def m(index):
            index["rows"][1]["populations"][5]["rungs"]["hit_plus"]["yield"]["ci_high"] -= 0.05
        self.assert_diff_names("rungs.hit_plus.yield.ci_high", self.mutated_problems(m))

    def test_noise_ratified_sigma(self):
        def m(index):
            rs = index["rows"][1]["populations"][5]["ratified_statistic"]
            rs["sigma_mv"] *= 0.9
            rs["agrees_with_grader"] = True
        self.assert_diff_names("populations[5].ratified_statistic.sigma_mv",
                               self.mutated_problems(m))

    def test_noise_grid_mean_summary(self):
        def m(index):
            index["ratified_summary"]["row2_grid_mean_sigma_mv"] *= 0.9
        self.assert_diff_names("ratified_summary.row2_grid_mean_sigma_mv",
                               self.mutated_problems(m))


class CitedN200IndexMutations(IndexMutationMixin, unittest.TestCase):
    """The cited N = 200 offset-only campaign: the inherited row-1 mutations
    plus declared-block mutations unique to a declared campaign."""

    cid = "20261010-n200"
    source = "sim/klt-corner-verification/campaigns/20261010-n200"

    def check(self) -> list[str]:
        return yr.check(self.cid, self.source, require_cited=True, offset_n=200)

    def test_declared_max_required_n(self):
        def m(index):
            index["declared"]["max_required_n_reported_by_engine"] = 42
        self.assert_diff_names("declared.max_required_n_reported_by_engine",
                               self.mutated_problems(m))

    def test_declared_hidden_target_failure(self):
        def m(index):
            index["declared"]["points_with_observed_target_failures"] = ["tt_27c_1.20v"]
        self.assert_diff_names("declared.points_with_observed_target_failures",
                               self.mutated_problems(m))

    def test_declared_offset_n(self):
        def m(index):
            index["declared"]["offset_n"] = 199
        problems = self.mutated_problems(m)
        self.assert_diff_names("does not match the campaign's declared", problems)


if __name__ == "__main__":
    unittest.main()

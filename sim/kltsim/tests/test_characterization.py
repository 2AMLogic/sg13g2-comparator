"""T1 item 8 characterization aggregation tests (issue #64). Stdlib only, no
PDK, no ngspice, no klt, nothing under the real ``sim/`` is written.

Three groups: the committed artifacts against the committed campaign grader;
negative controls on synthetic evidence in klt sim's response shape (none may
become PASS); freshness controls on a temporary copy of the indexed sources
(a changed source, index, envelope or manifest pin must be rejected).
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kltsim import build, characterization as ch, grade
from kltsim.tests import test_grade as tg

ROOT = build.REPO_ROOT
CAMPAIGN = build.EXPERIMENT_DIR / "campaigns" / ch.DEFAULT_CAMPAIGN
OUT = ch.default_out_dir(ch.DEFAULT_CAMPAIGN)
MANIFEST = ROOT / "manifests" / "sg13g2-comparator.json"
GRADING = json.loads((CAMPAIGN / "grading.json").read_text(encoding="utf-8"))
ROWS = tg.ROWS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CommittedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fresh = ch.build_artifacts(CAMPAIGN, OUT)
        cls.report = json.loads(cls.fresh[ch.REPORT_JSON_NAME])

    def test_generation_is_deterministic(self):
        again = ch.build_artifacts(CAMPAIGN, OUT)
        self.assertEqual(self.fresh, again)

    def test_committed_files_equal_a_fresh_regeneration(self):
        for name, data in self.fresh.items():
            self.assertEqual((OUT / name).read_bytes(), data, name)
        self.assertEqual(ch.check(CAMPAIGN, OUT, manifest=MANIFEST), [])

    def test_every_dr0002_subbound_is_present_with_unit_and_sources(self):
        ids = [r["id"] for r in ROWS["rows"]]
        self.assertEqual([r["id"] for r in self.report["rows"]], ids)
        self.assertEqual(ids, ["1", "2", "3a", "3b", "3c", "4a", "4b", "4c", "5a", "5b"])
        for r, spec in zip(self.report["rows"], ROWS["rows"]):
            self.assertEqual(r["unit"], spec.get("unit"), r["id"])
            self.assertTrue(r["sub_bound"] and r["condition"] and r["statistical_basis"], r["id"])
            self.assertTrue(r["sources"], r["id"])
            for s in r["sources"]:
                self.assertEqual(len(s["sha256"]), 64)
                self.assertEqual(_sha(ROOT / s["path"]), s["sha256"], s["path"])
                self.assertFalse(Path(s["path"]).is_absolute())
            if r["evidence_kind"] == "klt_sim":
                self.assertTrue(any(s["role"] == "envelope" for s in r["sources"]), r["id"])

    def test_verdicts_and_values_equal_the_campaign_grader(self):
        for r, g in zip(self.report["rows"], GRADING["rows"]):
            self.assertEqual(r["target"]["verdict"], g["target_verdict"], r["id"])
            self.assertEqual(r["stretch"]["verdict"], g["stretch_verdict"], r["id"])
            self.assertEqual(r["target"]["bound"], g["target_bound"], r["id"])
            self.assertEqual(r["stretch"]["bound"], g["stretch_bound"], r["id"])
            for col in ("target", "stretch"):
                gc = g.get(col) or {}
                for key in ("range", "binding", "grid_mean", "points_valid", "points_expected"):
                    if key in gc:
                        self.assertEqual(r[col][key], gc[key], (r["id"], col, key))

    def test_known_failures_and_distinct_verdicts_are_retained(self):
        by = {r["id"]: r for r in self.report["rows"]}
        self.assertEqual(by["2"]["target"]["verdict"], grade.FAIL)
        self.assertEqual(by["4a"]["target"]["verdict"], grade.FAIL)
        self.assertEqual(by["4a"]["target"]["points_failing"], 39)
        self.assertEqual(by["1"]["target"]["verdict"], grade.PASS)
        self.assertEqual(by["1"]["stretch"]["verdict"], grade.FAIL)  # separate outcomes
        self.assertEqual(by["4c"]["report_verdict"], grade.REPORTED)
        self.assertEqual(by["4c"]["target"]["verdict"], grade.NOT_SPECIFIED)
        self.assertEqual(by["5b"]["target"]["verdict"], grade.NOT_SPECIFIED)
        self.assertEqual(by["5b"]["stretch"]["verdict"], grade.FAIL)
        self.assertEqual(self.report["status"], "fail")
        self.assertEqual([b["id"] for b in self.report["target_compliance"]["blocking"]], ["2", "4a"])

    def test_offset_uncertainty_82_stays_visible(self):
        text = (OUT / ch.REPORT_MD_NAME).read_text(encoding="utf-8")
        self.assertIn("#82", text)
        self.assertIn("UNRESOLVED", text)
        row1 = next(r for r in self.report["rows"] if r["id"] == "1")
        self.assertTrue(any("#82" in n for n in row1["notes"]))
        self.assertAlmostEqual(row1["derived"]["grid_mean_of_per_point_3sigma"], 9.51, places=2)

    def test_populations_are_stated(self):
        by = {r["id"]: r for r in self.report["rows"]}
        self.assertEqual(by["1"]["population"]["n_per_point_expected"], 60)
        self.assertEqual(by["1"]["population"]["n_per_point_min"], 60)
        self.assertEqual(by["2"]["population"]["n_per_point_expected"], 80)
        self.assertIsNone(by["3a"]["population"])

    def test_envelope_and_manifest_pin(self):
        env = json.loads((OUT / ch.ENVELOPE_NAME).read_text(encoding="utf-8"))
        self.assertEqual((env["schema_version"], env["kind"], env["t1_item"]), (1, "generic", 8))
        self.assertEqual(env["status"], "fail")
        pin = "sha256:" + _sha(OUT / ch.INDEX_NAME)
        self.assertEqual(env["provenance"]["input"]["content_hash"], pin)
        cited = json.loads(MANIFEST.read_text(encoding="utf-8"))["evidence"]["8"]
        self.assertEqual(cited, {"file": f"{OUT.relative_to(ROOT).as_posix()}/envelope.json",
                                 "content_hash": pin})

    def test_index_binds_dut_spec_bounds_and_sources(self):
        index = json.loads((OUT / ch.INDEX_NAME).read_text(encoding="utf-8"))
        self.assertEqual(index["dut"], GRADING["dut"])
        self.assertEqual(index["dut"]["sha256"], _sha(ROOT / "design/comparator.spice"))
        self.assertEqual([b["id"] for b in index["spec_bounds"]], [r["id"] for r in ROWS["rows"]])
        paths = {s["path"] for s in index["sources"]}
        for need in ("sim/klt-corner-verification/rows.json", "sim/dut.json", "design/comparator.spice",
                     "sim/kltsim/grade.py", ROWS["spec_source"]):
            self.assertIn(need, paths)
        self.assertEqual(ch.verify_index(index), [])

    def test_no_campaign_file_is_written(self):
        before = {p: p.stat().st_mtime_ns for p in CAMPAIGN.glob("*.json")}
        ch.build_artifacts(CAMPAIGN, OUT)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in CAMPAIGN.glob("*.json")})


class SyntheticNegativeControls(unittest.TestCase):
    """Bad evidence may be graded FAIL/INCOMPLETE/..., never PASS."""

    def setUp(self):
        self.dut = grade.load_dut_reference()
        self.reg_body = tg._body("regeneration")
        self.mc_body = tg._body("offset_mc")

    def _report(self, rows, benches):
        spec = tg._spec(rows)
        graded = grade.grade(spec, benches, self.dut)
        graded["campaign"] = "synthetic"
        return ch.build_report(graded, spec, {"sources": []}, "0" * 64, "x/input-index.json")

    def _reg(self, env, body=None, rows=None):
        body = body or self.reg_body
        return self._report(rows or [tg._row("3a")],
                            {"regeneration": tg._evidence("regeneration", env, body)})

    def test_positive_control_complete_evidence_passes(self):
        rep = self._reg(tg.regeneration_envelope(self.reg_body))
        self.assertEqual(rep["status"], "pass")
        self.assertEqual(rep["rows"][0]["target"]["verdict"], grade.PASS)

    def _assert_not_pass(self, rep, verdict=None):
        self.assertEqual(rep["status"], "fail")
        self.assertNotEqual(rep["rows"][0]["target"]["verdict"], grade.PASS)
        if verdict:
            self.assertEqual(rep["rows"][0]["target"]["verdict"], verdict)
        self.assertFalse(rep["target_compliance"]["all_bounded_targets_pass"])

    def test_missing_pvt_point(self):
        env = tg.regeneration_envelope(self.reg_body, drop={("ss", 1.08, -40)})
        self._assert_not_pass(self._reg(env), grade.INCOMPLETE)

    def test_errored_pvt_point(self):
        env = tg.regeneration_envelope(self.reg_body)
        env["corners"][3]["status"] = "error"
        self._assert_not_pass(self._reg(env))

    def test_non_finite_measurement(self):
        for bad in (float("nan"), float("inf"), "garbage"):
            env = tg.regeneration_envelope(self.reg_body)
            for m in env["corners"][5]["measurements"]:
                if m["name"] == "td_od50_ns":
                    m["value"] = bad
            self._assert_not_pass(self._reg(env), grade.INCOMPLETE)

    def test_wrong_dut(self):
        edited = self.reg_body.replace("w=12u l=0.34u", "w=24u l=0.34u", 1)
        self.assertNotEqual(edited, self.reg_body)
        self._assert_not_pass(self._reg(tg.regeneration_envelope(edited), body=edited),
                              grade.INVALID_DUT)

    def test_mismatched_source_digest(self):
        env = tg.regeneration_envelope(self.reg_body + "* trailing edit\n")
        self._assert_not_pass(self._reg(env), grade.INVALID_DUT)

    def test_inadequate_monte_carlo_population(self):
        env = tg.offset_envelope(self.mc_body, n=30)
        rep = self._report([tg._row("1")], {"offset_mc": tg._evidence("offset_mc", env, self.mc_body)})
        self._assert_not_pass(rep)

    def test_reduced_model_evidence_is_a_gap_not_a_pass(self):
        row = copy.deepcopy(tg._row("3a"))
        row["evidence"] = {"kind": "gap", "reason": "reduced analog-model estimate only",
                           "tool_gap": "none", "retained_record": {
                               "path": "x", "recorded_value": "0.5 ns", "recorded_verdict_target": "MET",
                               "recorded_verdict_stretch": "MET"}}
        rep = self._report([row], {})
        self._assert_not_pass(rep, grade.GAP)
        self.assertEqual(rep["rows"][0]["stretch"]["verdict"], grade.GAP)

    def test_absent_bench_is_incomplete(self):
        self._assert_not_pass(self._report([tg._row("3a")], {}), grade.INCOMPLETE)

    def test_no_bounded_target_is_refused(self):
        with self.assertRaises(ch.CharacterizationError):
            self._report([tg._row("5b")],
                         {"regeneration": tg._evidence(
                             "regeneration", tg.regeneration_envelope(self.reg_body), self.reg_body)})


class ValidateGradingTests(unittest.TestCase):
    """Forged or inconsistent grading results are refused, not summarised."""

    def setUp(self):
        self.g = copy.deepcopy(GRADING)

    def _refused(self):
        with self.assertRaises(ch.CharacterizationError):
            ch.validate_grading(self.g, ROWS)

    def test_pristine_is_accepted(self):
        ch.validate_grading(self.g, ROWS)

    def test_pass_without_full_coverage(self):
        self.g["rows"][2]["target"]["points_valid"] = 44
        self._refused()

    def test_pass_with_failing_points(self):
        self.g["rows"][2]["target"]["points_failing"] = 1
        self._refused()

    def test_pass_on_short_monte_carlo_population(self):
        self.g["rows"][0]["monte_carlo_per_point"][4]["n"] = 59
        self._refused()

    def test_non_finite_value(self):
        self.g["rows"][2]["target"]["binding"]["value"] = float("nan")
        self._refused()

    def test_unknown_verdict(self):
        self.g["rows"][3]["target_verdict"] = "OK"
        self._refused()

    def test_missing_row(self):
        del self.g["rows"][4]
        self._refused()

    def test_collapsed_grid(self):
        self.g["grid_points"] = 1
        self._refused()


class FreshnessTests(unittest.TestCase):
    """check() on a temporary copy of exactly the indexed inputs."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        index = json.loads((OUT / ch.INDEX_NAME).read_text(encoding="utf-8"))
        rels = {s["path"] for s in index["sources"]}
        rels |= {f"{OUT.relative_to(ROOT).as_posix()}/{n}" for n in ch.ARTIFACT_NAMES}
        rels.add("manifests/sg13g2-comparator.json")
        for rel in rels:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, dst)
        self.campaign = self.root / CAMPAIGN.relative_to(ROOT)
        self.out = self.root / OUT.relative_to(ROOT)
        self.manifest = self.root / "manifests/sg13g2-comparator.json"

    def _check(self):
        return ch.check(self.campaign, self.out, root=self.root, manifest=self.manifest)

    def test_pristine_copy_is_fresh(self):
        self.assertEqual(self._check(), [])

    def test_changed_indexed_source_is_rejected(self):
        for rel in ("sim/klt-corner-verification/campaigns/20261009-d73a9ac/kickback.envelope.json",
                    "sim/klt-corner-verification/rows.json", "design/comparator.spice",
                    "sim/comparator-transient-noise/records/20260921-154729-41cbc7f.md"):
            path = self.root / rel
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            problems = self._check()
            self.assertTrue(any(rel in p and "stale or tampered" in p for p in problems), (rel, problems))
            path.write_bytes(original)
        self.assertEqual(self._check(), [])

    def test_missing_indexed_source_is_rejected(self):
        (self.campaign / "attempts.jsonl").unlink()
        self.assertTrue(any("attempts.jsonl" in p and "missing" in p for p in self._check()))

    def test_tampered_index_breaks_the_envelope_hash(self):
        path = self.out / ch.INDEX_NAME
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertTrue(any("content_hash" in p for p in self._check()))

    def test_envelope_hash_mismatch_is_rejected(self):
        path = self.out / ch.ENVELOPE_NAME
        env = json.loads(path.read_text(encoding="utf-8"))
        env["provenance"]["input"]["content_hash"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertTrue(any("content_hash" in p for p in self._check()))

    def test_hand_edited_report_is_stale(self):
        path = self.out / ch.REPORT_JSON_NAME
        path.write_text(path.read_text(encoding="utf-8").replace('"fail"', '"pass"', 1), encoding="utf-8")
        self.assertTrue(any(ch.REPORT_JSON_NAME in p and "differs" in p for p in self._check()))

    def test_self_reported_pass_envelope_is_stale(self):
        path = self.out / ch.ENVELOPE_NAME
        env = json.loads(path.read_text(encoding="utf-8"))
        env["status"] = "pass"
        path.write_text(json.dumps(env, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertTrue(any(ch.ENVELOPE_NAME in p and "differs" in p for p in self._check()))

    def test_manifest_pin_mismatch(self):
        m = json.loads(self.manifest.read_text(encoding="utf-8"))
        m["evidence"]["8"]["content_hash"] = "sha256:" + "1" * 64
        self.manifest.write_text(json.dumps(m), encoding="utf-8")
        self.assertTrue(any("manifest item 8" in p for p in self._check()))
        del m["evidence"]["8"]
        self.manifest.write_text(json.dumps(m), encoding="utf-8")
        self.assertTrue(any("manifest item 8" in p for p in self._check()))

    def test_missing_artifact(self):
        (self.out / ch.REPORT_MD_NAME).unlink()
        self.assertTrue(any(ch.REPORT_MD_NAME in p for p in self._check()))

    def test_stale_committed_grading_is_refused(self):
        path = self.campaign / "grading.json"
        g = json.loads(path.read_text(encoding="utf-8"))
        g["rows"][3]["target_verdict"] = "FAIL"
        path.write_text(json.dumps(g), encoding="utf-8")
        # grading.json is itself indexed, so the freshness check names it first;
        # a direct build must refuse too.
        self.assertTrue(self._check())
        with self.assertRaises(ch.CharacterizationError):
            ch.build_artifacts(self.campaign, self.out, root=self.root)

    def test_campaign_selection_is_explicit(self):
        with self.assertRaises(ch.CharacterizationError):
            ch.build_artifacts(self.root / "no-such-campaign", self.out, root=self.root)


if __name__ == "__main__":
    unittest.main()

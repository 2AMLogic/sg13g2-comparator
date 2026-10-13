"""Stdlib-only tests for the issue #81 noise-split arithmetic."""

import json
import math
import tempfile
import unittest
from pathlib import Path
from statistics import NormalDist
from unittest import mock

from kltsim import cli
from kltsim import noise_full as nf


class SigmaSeTest(unittest.TestCase):
    def test_sigma_recovers_known_slope(self):
        nd = NormalDist()
        sigma = 1.3  # mV
        od = 1.0
        p_plus, p_minus = nd.cdf(od / sigma), nd.cdf(-od / sigma)
        s, se = nf.sigma_se(p_plus, p_minus, 80, od)
        self.assertAlmostEqual(s, sigma, places=9)
        # ~13 % per-corner scatter at N = 80 near this operating point
        self.assertTrue(0.05 < se / s < 0.25, se / s)

    def test_se_shrinks_with_n(self):
        _, se80 = nf.sigma_se(0.78, 0.22, 80, 1.0)
        _, se320 = nf.sigma_se(0.78, 0.22, 320, 1.0)
        self.assertAlmostEqual(se80 / se320, 2.0, places=9)

    def test_unordered_rungs_rejected(self):
        with self.assertRaises(ValueError):
            nf.sigma_se(0.3, 0.7, 80, 1.0)


class QuadratureTest(unittest.TestCase):
    def test_independent_sources_close_exactly(self):
        s = nf.quadrature_split(1.2, 0.5, math.hypot(1.2, 0.5))
        self.assertAlmostEqual(s["closure"], 1.0)
        self.assertAlmostEqual(s["internal_increment"], 0.5)
        self.assertFalse(s["internal_increment_negative"])

    def test_total_below_front_end_is_scatter_not_negative(self):
        s = nf.quadrature_split(1.2, 0.5, 1.1)
        self.assertEqual(s["internal_increment"], 0.0)
        self.assertTrue(s["internal_increment_negative"])

    def test_split_without_internal_term_has_no_closure(self):
        s = nf.quadrature_split(1.2, None, 1.3)
        self.assertIsNone(s["closure"])
        self.assertIsNone(s["internal_alone"])


class SaturationAndControlTest(unittest.TestCase):
    def test_upper_bound_matches_rule_of_three(self):
        # 80/80 high => p >= 0.05**(1/80) = 0.9632 at 95 %  => z = 1.79
        ub = nf.sigma_upper_bound_95(80, 1.0)
        self.assertAlmostEqual(ub, 1.0 / NormalDist().inv_cdf(0.05 ** (1 / 80)))
        self.assertTrue(0.5 < ub < 0.6)

    def test_upper_bound_tightens_with_n(self):
        self.assertLess(nf.sigma_upper_bound_95(800, 1.0), nf.sigma_upper_bound_95(80, 1.0))

    def test_two_proportion_z(self):
        self.assertEqual(nf.two_proportion_z(1.0, 1.0, 80), 0.0)
        self.assertEqual(nf.two_proportion_z(0.5, 0.5, 80), 0.0)
        self.assertGreater(nf.two_proportion_z(0.9, 0.7, 80), 2.0)
        self.assertLess(nf.two_proportion_z(0.7, 0.9, 80), -2.0)


class IdentityTest(unittest.TestCase):
    """`noise-full --identity` writes a NEW campaign directory, never over the source."""

    def _run(self, root, *extra):
        result = {"configs": {}}
        with mock.patch.object(cli, "CAMPAIGNS_DIR", root), \
                mock.patch.object(cli.noise_full_mod, "analyse", lambda d: dict(result)), \
                mock.patch.object(cli.noise_full_mod, "render_markdown", lambda r: "md\n"):
            return cli.main(["noise-full", "--campaign", "src", *extra])

    def test_identity_leaves_source_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "noise_full.json").write_text("old\n")
            self.assertEqual(self._run(root, "--identity", "new"), 0)
            self.assertEqual((root / "src" / "noise_full.json").read_text(), "old\n")
            out = json.loads((root / "new" / "noise_full.json").read_text())
            self.assertEqual((out["campaign"], out["source_campaign"]), ("new", "src"))
            self.assertTrue((root / "new" / "noise_full.md").exists())

    def test_identity_refuses_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "new").mkdir()
            (root / "new" / "noise_full.json").write_text("kept\n")
            self.assertEqual(self._run(root, "--identity", "new"), 2)
            self.assertEqual((root / "new" / "noise_full.json").read_text(), "kept\n")

    def test_identity_refuses_existing_markdown_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "new").mkdir()
            (root / "new" / "noise_full.md").write_text("kept\n")
            self.assertEqual(self._run(root, "--identity", "new"), 2)
            self.assertEqual((root / "new" / "noise_full.md").read_text(), "kept\n")
            self.assertFalse((root / "new" / "noise_full.json").exists())


if __name__ == "__main__":
    unittest.main()


def _pt(name, sigma, se, shared=0):
    return {"point": name, "sigma": sigma, "sigma_se": se, "problem": None,
            "samples_sharing_a_draw_with_another_point": shared}


class GridUncertaintyTest(unittest.TestCase):
    def test_conservative_bound_formula_unequal_errors(self):
        ind, corr = nf.grid_mean_se_bounds([0.1, 0.2, 0.3])
        self.assertAlmostEqual(ind, math.sqrt(0.14) / 3)
        self.assertAlmostEqual(corr, 0.2)
        self.assertGreaterEqual(corr, ind)

    def test_independent_fixture_has_no_shared_draws(self):
        c = nf._summarise([_pt("a", 1.0, 0.1), _pt("b", 1.2, 0.3)], [])
        self.assertEqual((c["shared_draw_samples"], c["shared_draw_points"]), (0, 0))
        self.assertEqual(c["grader_notes"], [])
        self.assertAlmostEqual(c["grid_mean_se"], math.hypot(0.1, 0.3) / 2)
        self.assertAlmostEqual(c["grid_mean_se_fully_correlated_bound"], 0.2)
        self.assertTrue(c["complete"])
        self.assertNotIn("partial", c)

    def test_shared_draw_notes_and_counts_survive(self):
        note = "5/160 samples repeat a raw noise draw also seen at ANOTHER grid point"
        c = nf._summarise([_pt("a", 1.0, 0.1, 3), _pt("b", 1.2, 0.3, 2), _pt("c", 1.1, 0.2)],
                          [note])
        self.assertEqual((c["shared_draw_samples"], c["shared_draw_points"]), (5, 2))
        self.assertEqual(c["grader_notes"], [note])

    def test_incomplete_grid_labelled_partial(self):
        bad = {"point": "c", "sigma": None, "problem": "saturated"}
        c = nf._summarise([_pt("a", 1.0, 0.1), _pt("b", 1.2, 0.3), bad], [])
        self.assertFalse(c["complete"])
        self.assertTrue(c["partial"])
        self.assertIn("PARTIAL", c["partial_label"])
        self.assertAlmostEqual(c["grid_mean_se_fully_correlated_bound"], 0.2)  # 2 included points

    def test_render_carries_disclosures(self):
        note = "2/80 samples repeat a raw noise draw also seen at ANOTHER grid point"
        bad = {"point": "c", "sigma": None, "problem": "saturated"}
        cfg = nf._summarise([_pt("a", 1.0, 0.1, 2), bad], [note])
        pts = [{"point": "a", "both": {"sigma": 1.0, "sigma_se": 0.1}},
               {"point": "c", "both": {"sigma": None, "problem": "saturated"}}]
        result = {"od_x_mv": 1.0, "expected_n": 80, "target_max_mv": 1.0, "stretch_max_mv": 0.6,
                  "configs": {"both": cfg}, "points": pts, "uncertainty_basis": nf.UNCERTAINTY_BASIS,
                  "as_measured": {"incomplete": True, "why": "x"}}
        md = nf.render_markdown(result)
        for text in ("independent points assumed", "fully correlated", "PARTIAL, ungraded",
                     "grader note: " + note, "2 (1 points)", "none certifies"):
            self.assertIn(text, md)


# --------------------------------------------------------------------------- #
# issue #236: provenance validation before the noise arithmetic
# --------------------------------------------------------------------------- #

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

from kltsim import build as build_mod
from kltsim import grade as grade_mod
from kltsim.benches import ALL_BENCHES


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_config(root: Path, bench_name: str, *, gz: bool = False) -> None:
    """A self-consistent tn_full_* campaign slice built with the real builders
    (no PDK, no ngspice): body + per-process request, invocation, envelope."""
    bench = ALL_BENCHES[bench_name]
    _, _, files = build_mod.plan_bench_inputs(bench, root, target="batch")
    for path, data in files:
        path.write_bytes(data)
    body_sha = _sha((root / f"{bench_name}.body.spice").read_bytes())
    for tag in build_mod.part_tags(bench):
        section = tag[len(bench_name) + 1:]
        env = {"provenance": {"input": {"content_hash": f"sha256:{body_sha}"}},
               "environment": {"netlist_source": "schematic"},
               "corners": [{"process": section, "corner_id": f"{section}_x/mc0"}]}
        raw = json.dumps(env, indent=2).encode("utf-8")
        if gz:
            (root / f"{tag}.envelope.json.gz").write_bytes(gzip.compress(raw, mtime=0))
        else:
            (root / f"{tag}.envelope.json").write_bytes(raw)
        inv = {"tag": tag, "envelope_sha256": _sha(raw),
               "request_sha256": _sha((root / f"{tag}.request.json").read_bytes())}
        (root / f"{tag}.invocation.json").write_text(json.dumps(inv), encoding="utf-8")


class ProvenanceValidationTest(unittest.TestCase):
    bench = "tn_full_both"

    @classmethod
    def setUpClass(cls):
        cls.dut = grade_mod.load_dut_reference()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def validate(self, bench=None):
        return nf.validate_config(self.root, bench or self.bench, self.dut)

    def assertRejected(self, text, bench=None):
        _, _, problems, prov = self.validate(bench)
        self.assertEqual(prov["status"], "rejected")
        self.assertTrue(any(text in p for p in problems), problems)

    def test_valid_plain_and_gzip_validate(self):
        for gz in (False, True):
            with self.subTest(gz=gz):
                self.setUp()
                _write_config(self.root, self.bench, gz=gz)
                envs, shas, problems, prov = self.validate()
                self.assertEqual(problems, [])
                self.assertEqual(prov["status"], "validated")
                self.assertEqual(len(envs), 5)
                tag = f"{self.bench}.mos_tt"
                self.assertEqual(prov["sources"][tag]["envelope_sha256"], shas[tag])
                for key in ("request_sha256", "invocation_request_sha256",
                            "invocation_envelope_sha256", "input_content_hash"):
                    self.assertIn(key, prov["sources"][tag])
                self.assertEqual(prov["sources"][tag]["envelope_file"].endswith(".gz"), gz)

    def test_every_tn_full_configuration_validates(self):
        for name in ("tn_full_fe", "tn_full_int_probed", "tn_full_both", "tn_full_zero",
                     "tn_full_int_x4", "tn_full_int_x8"):
            with self.subTest(bench=name):
                self.setUp()
                _write_config(self.root, name)
                self.assertEqual(self.validate(name)[2], [])

    def test_missing_body(self):
        _write_config(self.root, self.bench)
        (self.root / f"{self.bench}.body.spice").unlink()
        self.assertRejected("committed netlist body is missing")

    def test_missing_request(self):
        _write_config(self.root, self.bench)
        (self.root / f"{self.bench}.mos_tt.request.json").unlink()
        self.assertRejected(f"{self.bench}.mos_tt.request.json is missing")

    def test_missing_invocation(self):
        _write_config(self.root, self.bench)
        (self.root / f"{self.bench}.mos_ss.invocation.json").unlink()
        self.assertRejected(f"{self.bench}.mos_ss.invocation.json is missing")

    def test_missing_envelope_part(self):
        _write_config(self.root, self.bench)
        (self.root / f"{self.bench}.mos_ff.envelope.json").unlink()
        self.assertRejected("envelope")

    def test_envelopes_only_is_rejected(self):
        # The issue's reproduction: envelopes alone, no body/request/invocation.
        _write_config(self.root, self.bench, gz=True)
        for p in list(self.root.glob("*.body.spice")) + list(self.root.glob("*.request.json")) \
                + list(self.root.glob("*.invocation.json")):
            p.unlink()
        _, _, problems, prov = self.validate()
        self.assertEqual(prov["status"], "rejected")
        self.assertTrue(any("body is missing" in p for p in problems))
        self.assertTrue(any("request" in p and "missing" in p for p in problems))
        self.assertTrue(any("invocation" in p and "missing" in p for p in problems))

    def test_changed_request(self):
        _write_config(self.root, self.bench)
        path = self.root / f"{self.bench}.mos_tt.request.json"
        req = json.loads(path.read_text(encoding="utf-8"))
        req["monte_carlo"]["n"] = 7
        path.write_text(json.dumps(req), encoding="utf-8")
        _, _, problems, _ = self.validate()
        self.assertTrue(any("request_sha256 mismatch" in p for p in problems), problems)
        self.assertTrue(any("request monte_carlo" in p for p in problems), problems)

    def test_changed_envelope(self):
        _write_config(self.root, self.bench)
        path = self.root / f"{self.bench}.mos_tt.envelope.json"
        env = json.loads(path.read_text(encoding="utf-8"))
        env["tampered"] = True
        path.write_text(json.dumps(env), encoding="utf-8")
        self.assertRejected("envelope_sha256 mismatch")

    def test_changed_gzip_envelope_hashed_after_decompression(self):
        _write_config(self.root, self.bench, gz=True)
        path = self.root / f"{self.bench}.mos_tt.envelope.json.gz"
        env = json.loads(gzip.decompress(path.read_bytes()))
        env["tampered"] = True
        path.write_bytes(gzip.compress(json.dumps(env).encode("utf-8"), mtime=0))
        self.assertRejected("envelope_sha256 mismatch")

    def test_input_hash_mismatch(self):
        _write_config(self.root, self.bench)
        path = self.root / f"{self.bench}.mos_tt.envelope.json"
        env = json.loads(path.read_text(encoding="utf-8"))
        env["provenance"]["input"]["content_hash"] = "sha256:" + "0" * 64
        raw = json.dumps(env).encode("utf-8")
        path.write_bytes(raw)
        inv_path = self.root / f"{self.bench}.mos_tt.invocation.json"
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
        inv["envelope_sha256"] = _sha(raw)  # chain consistent: only the input hash is wrong
        inv_path.write_text(json.dumps(inv), encoding="utf-8")
        _, _, problems, _ = self.validate()
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("provenance.input.content_hash", problems[0])

    def test_substituted_dut(self):
        _write_config(self.root, self.bench)
        path = self.root / f"{self.bench}.body.spice"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(".subckt comparator ", ".subckt comparator  ", 1)
                        .replace("* ==== BEGIN DUT", "* ==== BEGIN DUT", 1), encoding="utf-8")
        # Body bytes changed => its hash no longer matches the envelopes either.
        _, _, problems, _ = self.validate()
        self.assertTrue(any("is not today's" in p or "declared sha256" in p for p in problems),
                        problems)
        self.assertTrue(any("content_hash" in p for p in problems), problems)

    def test_wrong_configuration_body(self):
        # A `fe` body filed as `both`: right measurements, wrong injection.
        _write_config(self.root, "tn_full_fe")
        _write_config(self.root, self.bench)
        body = self.root / f"{self.bench}.body.spice"
        body.write_bytes((self.root / "tn_full_fe.body.spice").read_bytes())
        _, _, problems, _ = self.validate()
        self.assertTrue(any("body header names" in p for p in problems), problems)
        self.assertTrue(any("internal-noise hook" in p for p in problems), problems)

    def test_wrong_scale_hook(self):
        _write_config(self.root, "tn_full_zero")
        _write_config(self.root, self.bench)
        zero = (self.root / "tn_full_zero.body.spice").read_text(encoding="utf-8")
        (self.root / f"{self.bench}.body.spice").write_text(
            zero.replace("* tn_full_zero --", f"* {self.bench} --", 1), encoding="utf-8")
        self.assertRejected("internal-noise hook is not the tn_full_both configuration")

    def test_wrong_front_end_scale(self):
        _write_config(self.root, self.bench)
        body = self.root / f"{self.bench}.body.spice"
        body.write_text(body.read_text(encoding="utf-8").replace(
            ".param fe_scale=1.0", ".param fe_scale=0.0"), encoding="utf-8")
        self.assertRejected("bench parameter")

    def test_request_for_other_configuration(self):
        # tn_full_int_x4's request filed under tn_full_int_x8: names the wrong body.
        _write_config(self.root, "tn_full_int_x8")
        _write_config(self.root, "tn_full_int_x4")
        tag = "tn_full_int_x8.mos_tt"
        src = (self.root / "tn_full_int_x4.mos_tt.request.json").read_bytes()
        (self.root / f"{tag}.request.json").write_bytes(src)
        self.assertRejected("request names body", "tn_full_int_x8")

    def test_wrong_process_in_envelope(self):
        _write_config(self.root, self.bench)
        path = self.root / f"{self.bench}.mos_tt.envelope.json"
        env = json.loads(path.read_text(encoding="utf-8"))
        env["corners"][0]["process"] = "mos_ss"
        raw = json.dumps(env).encode("utf-8")
        path.write_bytes(raw)
        inv_path = self.root / f"{self.bench}.mos_tt.invocation.json"
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
        inv["envelope_sha256"] = _sha(raw)
        inv_path.write_text(json.dumps(inv), encoding="utf-8")
        self.assertRejected("not mos_tt")


class RejectedConfigurationNeverCompleteTest(unittest.TestCase):
    def test_envelopes_only_campaign_is_never_complete(self):
        dut = grade_mod.load_dut_reference()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("tn_full_fe", "tn_full_int_probed", "tn_full_both"):
                _write_config(root, name, gz=True)
                for p in list(root.glob("*.body.spice")) + list(root.glob("*.request.json")) \
                        + list(root.glob("*.invocation.json")):
                    p.unlink()
            result = nf.analyse(root, dut)
        for cfg in ("fe", "int", "both"):
            c = result["configs"][cfg]
            self.assertTrue(c["rejected"])
            self.assertFalse(c["complete"])
            self.assertNotIn("grid_mean", c)
            self.assertEqual(c["points_valid"], 0)
            self.assertTrue(c["rejection_reasons"])
        self.assertTrue(result["as_measured"]["incomplete"])
        self.assertIn("REJECTED", result["as_measured"]["why"])
        self.assertNotIn("split_grid", result)
        md = nf.render_markdown(result)
        self.assertIn("REJECTED by provenance validation", md)
        self.assertIn("body is missing", md)

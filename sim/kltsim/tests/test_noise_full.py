"""Stdlib-only tests for the issue #81 noise-split arithmetic."""

import math
import unittest
from statistics import NormalDist

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


# --------------------------------------------------------------------------- #
# issue #263: timestep smoke evidence is validated before convergence arithmetic
# --------------------------------------------------------------------------- #

SMOKE_N = 20  # deliberately not the historical 160: the request declares N
_ROWS = json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
_EV = next(r for r in _ROWS["rows"] if r["id"] == "2")["evidence"]


def _smoke_measurements(plus: float, minus: float, zero: float, k: int) -> list[dict]:
    def m(name, value, unit="V/V"):
        return {"name": name, "value": value, "unit": unit, "status": "pass", "margin": None}
    return [m("vdd_meas", 1.2, "V"), m("temp_meas", 27.0, "C"),
            m("vn0_a", 0.001 * (k + 1), "V"), m("vn0_b", 0.002 * (k + 1), "V"),
            m("vn1_a", 0.003 * (k + 1), "V"), m("d_zero", 1.0), m("d_plus", 1.0),
            m("d_minus", 0.0), m("res_zero", 0.5), m("res_plus", 0.5), m("res_minus", 0.5),
            m("hit_zero", zero, "1"), m("hit_plus", plus, "1"), m("hit_minus", minus, "1")]


def _smoke_corner(k: int, plus: float, minus: float, zero: float) -> dict:
    return {"corner_id": f"mos_tt/1.200V/27C/mc{k}", "process": "mos_tt",
            "supply_v": {"vsup": 1.2}, "temperature_c": 27.0, "status": "pass",
            "measurements": _smoke_measurements(plus, minus, zero, k), "diagnostics": [],
            "monte_carlo": {"sample_index": k, "seed": 1000 + k, "process_seed": 2000 + k,
                            "mismatch_seed": 3000 + k}}


def _write_smoke(root: Path, hits: dict[str, tuple[int, int, int]], n: int = SMOKE_N) -> Path:
    """smoke/ with a body and, per rung, request + invocation + envelope built from the
    real bench builders. ``hits[step]`` = (#high at +od, #high at -od, #high at 0)."""
    bench = ALL_BENCHES["tn_full_both"]
    smoke = root / "smoke"
    smoke.mkdir()
    _, _, files = build_mod.plan_bench_inputs(bench, smoke, target="batch")
    for path, data in files:
        if path.name == "tn_full_both.body.spice":
            path.write_bytes(data)
    body_sha = _sha((smoke / "tn_full_both.body.spice").read_bytes())
    base = json.loads(dict((p.name, d) for p, d in files)["tn_full_both.mos_tt.request.json"])
    for step, (hp, hm, hz) in hits.items():
        tag = f"timestep-{step}"
        req = json.loads(json.dumps(base))
        req["netlist"] = "tn_full_both.body.spice"
        req["corners"] = {"process": ["mos_tt"], "supply_v": {"vsup": [1.2]},
                          "temperature_c": [27.0]}
        req["analysis"]["args"] = f"{step} 5.1n 0 {step}"
        req["monte_carlo"]["n"] = n
        (smoke / f"{tag}.request.json").write_text(json.dumps(req, indent=2), encoding="utf-8")
        corners = [_smoke_corner(k, float(k < hp), float(k < hm), float(k < hz))
                   for k in range(n)]
        env = {"provenance": {"input": {"content_hash": f"sha256:{body_sha}"},
                              "deck": {"content_hash": "sha256:" + "d" * 64}},
               "environment": {"netlist_source": "schematic"}, "corner_count": n,
               "corners": corners}
        raw = json.dumps(env).encode("utf-8")
        (smoke / f"{tag}.envelope.json").write_bytes(raw)
        inv = {"tag": tag, "exit_code": 0, "envelope_sha256": _sha(raw),
               "request_sha256": _sha((smoke / f"{tag}.request.json").read_bytes())}
        (smoke / f"{tag}.invocation.json").write_text(json.dumps(inv), encoding="utf-8")
    return smoke


class TimestepSmokeValidationTest(unittest.TestCase):
    HITS = {"20p": (15, 5, 10), "10p": (17, 4, 9), "5p": (14, 5, 10)}

    @classmethod
    def setUpClass(cls):
        cls.dut = grade_mod.load_dut_reference()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def smoke(self, hits=None):
        return _write_smoke(self.root, hits or self.HITS)

    def run_ts(self, smoke):
        return nf.timestep_convergence(smoke, _EV, self.dut)

    def rewrite(self, smoke, step, *, request=None, envelope=None, invocation=None):
        """Edit a rung's file(s) and keep the invocation hashes consistent."""
        tag = f"timestep-{step}"
        rp, ep, ip = (smoke / f"{tag}.{x}.json" for x in ("request", "envelope", "invocation"))
        for path, fn in ((rp, request), (ep, envelope)):
            if fn:
                data = json.loads(path.read_text(encoding="utf-8"))
                fn(data)
                path.write_text(json.dumps(data), encoding="utf-8")
        if invocation:
            inv = json.loads(ip.read_text(encoding="utf-8"))
            invocation(inv)
            ip.write_text(json.dumps(inv), encoding="utf-8")
        else:
            inv = json.loads(ip.read_text(encoding="utf-8"))
            inv["request_sha256"] = _sha(rp.read_bytes())
            inv["envelope_sha256"] = _sha(ep.read_bytes())
            ip.write_text(json.dumps(inv), encoding="utf-8")

    def assertRejectedRung(self, ts, step, text):
        rung = ts["steps"][step]
        self.assertEqual(rung["status"], "rejected", rung)
        self.assertTrue(any(text in p for p in rung["problems"]), rung["problems"])
        for key in ("sigma", "sigma_se", "z_vs_20p", "p_plus", "p_minus", "p_zero"):
            self.assertNotIn(key, rung)
        self.assertIn(step, ts["withheld"] if step != "20p" else ts["rejected_rungs"])

    def test_valid_chain_gives_expected_sigma_se_and_comparison(self):
        ts = self.run_ts(self.smoke())
        self.assertEqual(ts["validated_rungs"], ["20p", "10p", "5p"])
        self.assertEqual(ts["withheld"], {})
        sig, se = nf.sigma_se(0.75, 0.25, SMOKE_N, float(_EV["od_x_mv"]))
        self.assertAlmostEqual(ts["steps"]["20p"]["sigma"], sig)
        self.assertAlmostEqual(ts["steps"]["20p"]["sigma_se"], se)
        self.assertEqual(ts["steps"]["20p"]["n"], SMOKE_N)  # declared N, not 160
        s10, se10 = nf.sigma_se(0.85, 0.2, SMOKE_N, float(_EV["od_x_mv"]))
        self.assertAlmostEqual(ts["steps"]["10p"]["z_vs_20p"], (s10 - sig) / math.hypot(se, se10))
        self.assertEqual(ts["comparisons"], ["10p", "5p"])

    def test_issue_reproduction_errored_duplicates_rejected(self):
        smoke = self.smoke()

        def broken(env):
            env["corners"] = [dict(_smoke_corner(0, 0.7, 0.3, 0.5), status="error")
                              for _ in range(10)]
        self.rewrite(smoke, "20p", envelope=broken)
        (smoke / "timestep-20p.request.json").unlink()
        (smoke / "timestep-20p.invocation.json").unlink()
        ts = self.run_ts(smoke)
        rung = ts["steps"]["20p"]
        self.assertEqual(rung["status"], "rejected")
        self.assertEqual(rung["statuses"], {"error": 10})
        self.assertNotIn("sigma", rung)
        self.assertEqual(ts["comparisons"], [])
        self.assertTrue(any("baseline rung 20p is rejected" in w for w in ts["withheld"].values()))

    def test_errored_sample(self):
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e["corners"][3].update(status="error"))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "untrusted")

    def test_duplicate_measurement_name(self):
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e["corners"][2]["measurements"].append(
            dict(e["corners"][2]["measurements"][-1])))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "duplicate measurement")

    def test_wrong_probe(self):
        smoke = self.smoke()

        def vdd(env):
            env["corners"][1]["measurements"][0]["value"] = 1.08
        self.rewrite(smoke, "10p", envelope=vdd)
        self.assertRejectedRung(self.run_ts(smoke), "10p", "supply probe")

    def test_wrong_corner(self):
        smoke = self.smoke()

        def corner(env):
            for c in env["corners"]:
                c["temperature_c"] = 125.0
        self.rewrite(smoke, "10p", envelope=corner)
        self.assertRejectedRung(self.run_ts(smoke), "10p", "nominal")

    def test_nonfinite_and_nonbinary_hits(self):
        for bad in (0.5, float("nan"), None):
            with self.subTest(bad=bad):
                self.setUp()
                smoke = self.smoke()

                def hit(env, bad=bad):
                    for m in env["corners"][4]["measurements"]:
                        if m["name"] == "hit_plus":
                            m["value"] = bad
                self.rewrite(smoke, "10p", envelope=hit)
                self.assertRejectedRung(self.run_ts(smoke), "10p", "untrusted")

    def test_ambiguous_and_repeated_sample_identity(self):
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e["corners"][5]["monte_carlo"].update(
            sample_index=4))
        ts = self.run_ts(smoke)
        self.assertRejectedRung(ts, "10p", "repeated sample_index")
        self.setUp()
        smoke = self.smoke()
        self.rewrite(smoke, "5p", envelope=lambda e: e["corners"][5]["monte_carlo"].update(
            seed=1004, process_seed=2004, mismatch_seed=3004))
        self.assertRejectedRung(self.run_ts(smoke), "5p", "repeat another sample's seeds")

    def test_repeated_raw_noise_draw(self):
        smoke = self.smoke()

        def same(env):
            env["corners"][6]["measurements"][2:5] = [dict(m) for m in
                                                      env["corners"][5]["measurements"][2:5]]
        self.rewrite(smoke, "10p", envelope=same)
        self.assertRejectedRung(self.run_ts(smoke), "10p", "raw noise draw")

    def test_empty_population_and_count_mismatch(self):
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e.update(corners=[]))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "empty population")
        self.setUp()
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e["corners"].pop())
        self.assertRejectedRung(self.run_ts(smoke), "10p", "request declares N")

    def test_provenance_mismatch(self):
        smoke = self.smoke()
        (smoke / "timestep-10p.envelope.json").write_text(
            (smoke / "timestep-10p.envelope.json").read_text() + " ", encoding="utf-8")
        self.assertRejectedRung(self.run_ts(smoke), "10p", "envelope_sha256 mismatch")

    def test_missing_invocation_and_wrong_tag(self):
        smoke = self.smoke()
        (smoke / "timestep-10p.invocation.json").unlink()
        self.assertRejectedRung(self.run_ts(smoke), "10p", "invocation timestep-10p.invocation.json is missing")
        self.setUp()
        smoke = self.smoke()
        self.rewrite(smoke, "5p", invocation=lambda i: i.update(tag="timestep-10p"))
        self.assertRejectedRung(self.run_ts(smoke), "5p", "invocation names tag")

    def test_input_hash_and_body_mismatch(self):
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e["provenance"]["input"].update(
            content_hash="sha256:" + "0" * 64))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "content_hash")
        self.setUp()
        smoke = self.smoke()
        (smoke / "tn_full_both.body.spice").unlink()
        ts = self.run_ts(smoke)
        self.assertEqual(ts["validated_rungs"], [])
        self.assertTrue(any("smoke body is missing" in p for p in ts["steps"]["20p"]["problems"]))

    def test_deck_hash_missing_malformed_and_differing(self):
        # provenance.deck deleted: no model-deck provenance, rung rejected
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e["provenance"].pop("deck"))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "model deck content_hash is missing")
        self.setUp()
        smoke = self.smoke()
        # deck object present but carries no hash
        self.rewrite(smoke, "10p", envelope=lambda e: e["provenance"].update(deck={}))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "model deck content_hash is missing")
        self.setUp()
        smoke = self.smoke()
        # malformed hash: present but not a sha256:<64 hex> digest
        self.rewrite(smoke, "10p", envelope=lambda e: e["provenance"]["deck"].update(
            content_hash="deck-final.spice"))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "model deck content_hash is missing")
        self.setUp()
        smoke = self.smoke()
        # equal malformed hashes on EVERY rung must not enable comparison
        for step in ("20p", "10p", "5p"):
            self.rewrite(smoke, step, envelope=lambda e: e["provenance"]["deck"].update(
                content_hash="not-a-digest"))
        ts = self.run_ts(smoke)
        self.assertEqual(ts["validated_rungs"], [])
        self.assertEqual(ts["comparisons"], [])
        self.setUp()
        smoke = self.smoke()
        # well-formed but differing deck hash: rung validates, comparison withheld
        self.rewrite(smoke, "10p", envelope=lambda e: e["provenance"]["deck"].update(
            content_hash="sha256:" + "e" * 64))
        ts = self.run_ts(smoke)
        self.assertEqual(ts["steps"]["10p"]["status"], "validated")
        self.assertIn("model deck content hash", ts["withheld"]["10p"])
        self.assertNotIn("z_vs_20p", ts["steps"]["10p"])
        self.assertEqual(ts["comparisons"], ["5p"])

    def test_wrong_request_step_and_corner(self):
        smoke = self.smoke()
        self.rewrite(smoke, "10p", request=lambda r: r["analysis"].update(args="20p 5.1n 0 20p"))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "step and max step")
        self.setUp()
        smoke = self.smoke()
        self.rewrite(smoke, "10p", request=lambda r: r["corners"].update(temperature_c=[125.0]))
        self.assertRejectedRung(self.run_ts(smoke), "10p", "request corners")

    def test_unintended_cross_rung_change_withholds_comparison(self):
        smoke = self.smoke()
        # Valid on its own (hash chain consistent) but a different draw population / options.
        self.rewrite(smoke, "10p", request=lambda r: r["options"].update(timeout_s=1))
        ts = self.run_ts(smoke)
        self.assertEqual(ts["steps"]["10p"]["status"], "validated")
        self.assertNotIn("z_vs_20p", ts["steps"]["10p"])
        self.assertIn("request (other than solver step/max step)", ts["withheld"]["10p"])
        self.assertEqual(ts["comparisons"], ["5p"])
        self.setUp()
        smoke = self.smoke()
        self.rewrite(smoke, "5p", envelope=lambda e: e["corners"][0]["monte_carlo"].update(
            seed=99999))
        ts = self.run_ts(smoke)
        self.assertIn("sample identities", ts["withheld"]["5p"])
        self.assertNotIn("z_vs_20p", ts["steps"]["5p"])

    def test_different_declared_n_across_rungs_withheld(self):
        smoke = self.smoke()
        bad = _write_smoke(Path(tempfile.mkdtemp(dir=self.root)), {"10p": (8, 2, 5)}, n=10)
        for ext in ("request", "envelope", "invocation"):
            (smoke / f"timestep-10p.{ext}.json").write_bytes((bad / f"timestep-10p.{ext}.json").read_bytes())
        ts = self.run_ts(smoke)
        self.assertEqual(ts["steps"]["10p"]["n"], 10)
        self.assertIn("N", ts["withheld"]["10p"])

    def test_missing_rung_and_absent_smoke_are_explicit(self):
        smoke = self.smoke({"20p": (15, 5, 10), "10p": (17, 4, 9)})
        ts = self.run_ts(smoke)
        self.assertEqual(ts["missing_rungs"], ["5p"])
        self.assertEqual(ts["steps"]["5p"]["status"], "missing")
        self.assertIn("5p", ts["withheld"])
        empty = self.run_ts(self.root / "nonexistent")
        self.assertFalse(empty["available"])
        self.assertEqual(empty["steps"], {})
        self.assertIn("not assessed", empty["unavailable"])
        md = nf.render_markdown({"od_x_mv": 1.0, "expected_n": 80, "target_max_mv": 1.0,
                                 "stretch_max_mv": 0.6, "configs": {}, "points": [],
                                 "timestep": empty, "as_measured": {"incomplete": True, "why": "x"}})
        self.assertIn("UNAVAILABLE", md)

    def test_saturated_rung_keeps_validation_but_no_sigma(self):
        smoke = self.smoke({"20p": (15, 5, 10), "10p": (SMOKE_N, 0, 10), "5p": (14, 5, 10)})
        ts = self.run_ts(smoke)
        self.assertEqual(ts["steps"]["10p"]["status"], "validated")
        self.assertNotIn("sigma", ts["steps"]["10p"])
        self.assertIn("sigma unavailable", ts["withheld"]["10p"])

    def test_render_shows_rejection_and_withheld(self):
        smoke = self.smoke()
        self.rewrite(smoke, "10p", envelope=lambda e: e["corners"][3].update(status="error"))
        ts = self.run_ts(smoke)
        md = nf.render_markdown({"od_x_mv": 1.0, "expected_n": 80, "target_max_mv": 1.0,
                                 "stretch_max_mv": 0.6, "configs": {}, "points": [],
                                 "timestep": ts, "as_measured": {"incomplete": True, "why": "x"}})
        self.assertIn("`10p` REJECTED", md)
        self.assertIn("comparison 10p vs 20p WITHHELD", md)
        self.assertIn("| 20p | validated |", md)

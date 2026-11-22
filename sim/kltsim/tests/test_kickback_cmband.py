"""Kickback CM-band campaign tests (issue #165). Stdlib only; no PDK, no
ngspice, writes nothing outside a temporary directory.

Uses the committed issue #62 kickback envelope/request/body as a read-only
fixture and perturbs deep copies of it.
"""

from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kltsim import cli as kcli, kickback_cmband as kb

SIM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SIM))
import run_kickback_cm_band as rkb  # noqa: E402

REF = kb.REFERENCE_DIR
REF_ENV = json.loads((REF / "kickback.envelope.json").read_text(encoding="utf-8"))
REF_REQ = json.loads((REF / "kickback.request.json").read_text(encoding="utf-8"))
REF_BODY = (REF / "kickback.body.spice").read_text(encoding="utf-8")
NOM = kb.condition("vcm-nom")
M050 = kb.condition("vcm-m050")


def env_for(cond, mutate=None):
    """The reference envelope, as if run at ``cond`` (adds the vcm_meas probe)."""
    env = copy.deepcopy(REF_ENV)
    for c in env["corners"]:
        c["measurements"].append({"name": "vcm_meas", "value": cond.vcm_v(), "unit": "V",
                                  "status": "pass", "margin": None})
    if mutate:
        mutate(env)
    return env


def meas(corner, name):
    return next(m for m in corner["measurements"] if m["name"] == name)


def seed_probe_ref_body(series, cond):
    """Materialize the #165 probe reference body inside the tempdir so the
    byte-identity check in write_probe_inputs stays independent of campaign
    evidence outside the CI sparse cone (see test_run_offset_cm_band)."""
    ref = series / kb.PROBE_REFERENCE_SERIES / cond.name / kb.BODY_NAME
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(kb.compose_body(cond))


class Transform(unittest.TestCase):
    def test_reference_has_double_space_and_matches_once(self):
        self.assertIn("vcm  cm 0 dc {dut_vcm}", REF_BODY)
        out = kb.apply_transform(REF_BODY, M050)
        self.assertIn(".param vcm_delta=-0.05", out)
        self.assertEqual(out.count(kb.VCM_LINE_CM), 1)

    def test_reverse_restores_circuit(self):
        for cond in kb.CONDITIONS:
            back = kb.undo_transform(kb.apply_transform(REF_BODY, cond)).split("\n")
            orig = REF_BODY.split("\n")
            norm = lambda lines: [re.sub(r"\s+", " ", l) for l in lines[2:]]  # noqa: E731
            self.assertEqual(norm(back), norm(orig))

    def test_zero_or_multiple_sources_fail(self):
        with self.assertRaises(kb.KickbackCmBandError):
            kb.apply_transform("a\nb\nc\nR1 x y 1\n", NOM)
        twice = REF_BODY + "\nvcm cm 0 dc {dut_vcm}\n"
        with self.assertRaises(kb.KickbackCmBandError):
            kb.apply_transform(twice, NOM)

    def test_whitespace_tolerant(self):
        for line in ("vcm cm 0 dc {dut_vcm}", "vcm\t cm  0 dc   {dut_vcm}  "):
            body = "h0\nh1\nh2\n" + line + "\n"
            self.assertIn(kb.VCM_LINE_CM, kb.apply_transform(body, NOM))


class Requests(unittest.TestCase):
    def test_grid_backend_and_no_monte_carlo(self):
        self.assertEqual(len(kb.expected_keys()), 45)
        for cond in kb.CONDITIONS:
            req = kb.compose_request(cond)
            self.assertEqual(req["backend"], "batch")
            self.assertNotIn("monte_carlo", req)
            self.assertEqual(req["analysis"], {"kind": "tran", "args": "5p 60n"})
            self.assertEqual(len(req["corners"]["process"])
                             * len(req["corners"]["supply_v"]["vsup"])
                             * len(req["corners"]["temperature_c"]), 45)

    def test_original_request_semantics_unchanged(self):
        req = kb.compose_request(NOM)
        strip = lambda r: {k: v for k, v in r.items()  # noqa: E731
                           if k not in ("_comment", "_condition", "netlist")}
        added = req["measurements"][-1]
        self.assertEqual(added["name"], "vcm_meas")
        req["measurements"] = req["measurements"][:-1]
        self.assertEqual(strip(req), strip(REF_REQ))
        # original limits kept (charge limit included)
        lim = {m["name"]: m.get("limits") for m in REF_REQ["measurements"] if m.get("limits")}
        self.assertEqual(lim["qkick_fc"], {"max": 25.0})
        self.assertEqual(lim[kb.RESIDUE], {"max": 100.0})

    def test_nominal_body_circuit_equals_reference(self):
        body = kb.compose_body(NOM)
        self.assertEqual(kb.declared_hashes(body), kb.declared_hashes(REF_BODY))


class Validity(unittest.TestCase):
    def evaluate(self, mutate=None, cond=NOM):
        return kb.evaluate_condition(cond, env_for(cond, mutate))

    def test_clean_nominal_is_45_valid_and_met(self):
        r = self.evaluate()
        self.assertEqual(r["points_valid"], 45)
        self.assertEqual(r["verdict"]["target"], "MET")
        self.assertEqual(r["verdict"]["stretch"], "MET")

    def test_charge_limit_failure_is_not_residue_failure_and_is_reported(self):
        r = self.evaluate()
        self.assertGreater(r["qkick_limit_failures"], 0)  # 39/45 at nominal (DR-0003)
        self.assertEqual(r["verdict"]["target"], "MET")
        self.assertEqual(r["points_valid"], 45)

    def test_missing_point(self):
        def m(env):
            env["corners"].pop(0)
        r = self.evaluate(m)
        self.assertEqual(r["points_valid"], 44)
        self.assertIn("not in the envelope", r["rejected"][0]["reason"])
        self.assertEqual(r["verdict"]["target"], "INCOMPLETE")

    def test_duplicate_point_selects_nothing(self):
        def m(env):
            env["corners"].append(copy.deepcopy(env["corners"][3]))
        r = self.evaluate(m)
        self.assertEqual(r["points_valid"], 44)
        self.assertIn("duplicate", r["rejected"][0]["reason"])
        self.assertTrue(r["structural_notes"])

    def test_probe_mismatch(self):
        def m(env):
            meas(env["corners"][0], "vcm_meas")["value"] = 0.6
        r = self.evaluate(m, M050)
        self.assertEqual(r["points_valid"], 44)
        self.assertIn("vcm_meas", r["rejected"][0]["reason"])

    def test_missing_probe_supply_and_temperature_mismatch(self):
        def m(env):
            env["corners"][0]["measurements"] = [
                x for x in env["corners"][0]["measurements"] if x["name"] != "vcm_meas"]
            meas(env["corners"][1], "vdd_meas")["value"] = 1.0
            meas(env["corners"][2], "temp_meas")["value"] = 99.0
        r = self.evaluate(m)
        self.assertEqual(r["points_valid"], 42)

    def test_nonfinite_and_missing_measurements(self):
        def m(env):
            meas(env["corners"][0], "kick_sigdep_uv")["value"] = float("nan")
            meas(env["corners"][1], "kick_sigdep_uv")["value"] = None
            meas(env["corners"][2], "qkick_p_fc")["value"] = float("inf")
        r = self.evaluate(m)
        self.assertEqual(r["points_valid"], 42)

    def test_simulation_failure_and_decision_gate(self):
        def m(env):
            env["corners"][0]["status"] = "error"
            meas(env["corners"][1], "dout_1k_end")["status"] = "fail"
        r = self.evaluate(m)
        self.assertEqual(r["points_valid"], 43)
        self.assertEqual(r["verdict"]["target"], "INCOMPLETE")

    def test_rejected_points_are_not_repaired_and_not_in_stats(self):
        def m(env):
            meas(env["corners"][0], "kick_sigdep_uv")["value"] = 5000.0
            meas(env["corners"][0], "dout_float_big_end")["status"] = "fail"
        r = self.evaluate(m)
        self.assertLess(r["residue_uv"]["max"], 100.0)
        self.assertEqual(r["verdict"]["target"], "INCOMPLETE")

    def test_residue_over_bounds(self):
        def over(v):
            def m(env):
                meas(env["corners"][0], "kick_sigdep_uv")["value"] = v
            return m
        r = self.evaluate(over(50.0))
        self.assertEqual((r["verdict"]["target"], r["verdict"]["stretch"]), ("MET", "NOT MET"))
        r = self.evaluate(over(150.0))
        self.assertEqual((r["verdict"]["target"], r["verdict"]["stretch"]),
                         ("NOT MET", "NOT MET"))


class Reproduction(unittest.TestCase):
    def check(self, env=None, request=None, body=None):
        return kb.reproduction_check(
            env or env_for(NOM), request or kb.compose_request(NOM),
            body or kb.compose_body(NOM), REF_ENV, REF_REQ, REF_BODY)

    def test_identical_values_pass(self):
        r = self.check()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["values_compared"], r["expected_values"])

    def test_value_discrepancy_fails_and_is_named(self):
        def m(env):
            meas(env["corners"][4], "kick_sigdep_uv")["value"] += 1e-6
        r = self.check(env=env_for(NOM, m))
        self.assertFalse(r["ok"])
        self.assertEqual(r["mismatches"][0]["measurement"], "kick_sigdep_uv")

    def test_provenance_discrepancy_fails(self):
        def m(env):
            env["environment"]["models_lib_sha256"] = "0" * 64
        self.assertFalse(self.check(env=env_for(NOM, m))["ok"])
        req = kb.compose_request(NOM)
        req["analysis"]["args"] = "10p 60n"
        self.assertFalse(self.check(request=req)["ok"])

    def test_missing_key_fails(self):
        def m(env):
            env["corners"].pop()
        self.assertFalse(self.check(env=env_for(NOM, m))["ok"])


class Probe405(unittest.TestCase):
    """Issue #405 supplementary probe requests."""

    def test_grid_is_exactly_the_probe_points_and_batch(self):
        for name, sups in kb.PROBE_SUPPLIES_V.items():
            req = kb.probe_request(kb.condition(name), "obs")
            self.assertEqual(req["corners"]["process"], ["mos_ss"])
            self.assertEqual(req["corners"]["supply_v"], {"vsup": list(sups)})
            self.assertEqual(req["corners"]["temperature_c"], [-40.0])
            self.assertEqual(req["backend"], "batch")
            self.assertEqual(req["batch"]["capacity_wait_s"], 600)

    def test_repro_arm_keeps_165_cards_and_analysis(self):
        cond = kb.condition("vcm-m050")
        base = kb.compose_request(cond)
        rep = kb.probe_request(cond, "repro")
        self.assertEqual(rep["measurements"], base["measurements"])
        self.assertEqual(rep["analysis"], base["analysis"])

    def test_arms_add_cards_and_vary_only_the_labelled_setting(self):
        cond = kb.condition("vcm-p050")
        names = lambda r: [m["name"] for m in r["measurements"]]  # noqa: E731
        obs, xing, step = (kb.probe_request(cond, a) for a in ("obs", "xing", "step20p"))
        self.assertIn("b_dp_55n", names(obs))
        self.assertNotIn("b_t_half", names(obs))
        self.assertIn("b_t_half", names(xing))
        self.assertEqual(names(step), names(obs))
        self.assertEqual(step["analysis"]["args"], "5p 60n 0 20p")
        self.assertEqual(obs["analysis"]["args"], "5p 60n")
        self.assertEqual(len(set(names(xing))), len(names(xing)))

    def test_unknown_arm_refused(self):
        with self.assertRaises(kb.KickbackCmBandError):
            kb.probe_request(kb.condition("vcm-nom"), "nope")


class Supplement415(unittest.TestCase):
    """Issue #415 forced-DC supplement: arms repro/obs/optdc/icdc in a new
    series; optdc/icdc append exactly one declared block to the #165 body."""

    ISSUE = kb.SUPPLEMENT_ISSUE

    def request(self, cond_name, arm):
        return kb.probe_request(kb.condition(cond_name), arm, issue=self.ISSUE)

    def test_grid_is_exactly_the_probe_points_and_batch(self):
        for name, sups in kb.PROBE_SUPPLIES_V.items():
            for arm in kb.PROBE_ARMS_415:
                req = self.request(name, arm)
                self.assertEqual(req["corners"]["process"], ["mos_ss"])
                self.assertEqual(req["corners"]["supply_v"], {"vsup": list(sups)})
                self.assertEqual(req["corners"]["temperature_c"], [-40.0])
                self.assertEqual(req["backend"], "batch")
                self.assertEqual(req["batch"]["capacity_wait_s"], 600)

    def test_labels_issue_415_and_declared_body_supplement(self):
        for name in kb.PROBE_SUPPLIES_V:
            for arm in kb.PROBE_ARMS_415:
                req = self.request(name, arm)
                self.assertEqual(req["_condition"]["issue"], 415)
                self.assertEqual(req["_condition"]["probe_arm"], arm)
                self.assertEqual(req["_condition"].get("body_supplement"),
                                 arm if arm in kb.PROBE_BODY_SUPPLEMENT_ARMS else None)
                self.assertIn("(issue #415)", req["_comment"][0])

    def test_analysis_unchanged_and_obs_cards_on_every_non_repro_arm(self):
        cond = kb.condition("vcm-m050")
        names = lambda r: [m["name"] for m in r["measurements"]]  # noqa: E731
        base = kb.compose_request(cond)
        for arm in ("obs", "optdc", "icdc"):
            req = self.request("vcm-m050", arm)
            self.assertEqual(req["analysis"]["args"], "5p 60n")
            self.assertIn("b_vd_1n", names(req))
            self.assertIn("c_vd_strobe", names(req))
            self.assertNotIn("b_t_half", names(req))
        self.assertEqual(self.request("vcm-m050", "repro")["measurements"], base["measurements"])

    def test_repro_and_obs_bodies_are_byte_identical_to_165(self):
        for name in kb.PROBE_SUPPLIES_V:
            cond = kb.condition(name)
            ref = (kb.SERIES_DIR / "20261011-165" / name / kb.BODY_NAME).read_bytes()
            for arm in ("repro", "obs"):
                self.assertEqual(kb.probe_expected_body(cond, arm).encode("utf-8"), ref,
                                 f"{arm} body for {name} must stay byte-identical to #165")

    def test_supplement_body_is_165_plus_exactly_the_declared_block(self):
        expected_nodesets = {
            "vcm-m050": ".nodeset v(bpp)=0.5505 v(bpn)=0.5495 v(cpp)=0.6 v(cpn)=0.5",
            "vcm-nom": ".nodeset v(bpp)=0.6005 v(bpn)=0.5995 v(cpp)=0.65 v(cpn)=0.55",
            "vcm-p050": ".nodeset v(bpp)=0.6505 v(bpn)=0.6495 v(cpp)=0.7 v(cpn)=0.6",
        }
        for name, cond in ((n, kb.condition(n)) for n in kb.PROBE_SUPPLIES_V):
            ref = (kb.SERIES_DIR / "20261011-165" / name / kb.BODY_NAME).read_text(encoding="utf-8")
            optdc = kb.probe_expected_body(cond, "optdc")
            self.assertTrue(optdc.startswith(ref))
            self.assertEqual(optdc[len(ref):], kb.probe_body_supplement(cond, "optdc"))
            self.assertIn(".options itl1=500 gminsteps=500 srcsteps=500 gmin=1e-12\n", optdc)
            self.assertNotIn(".nodeset v(", optdc)
            self.assertNotIn(".ic v(", optdc)
            icdc = kb.probe_expected_body(cond, "icdc")
            self.assertTrue(icdc.startswith(ref))
            self.assertEqual(icdc[len(ref):], kb.probe_body_supplement(cond, "icdc"))
            cards = [ln for ln in icdc[len(ref):].splitlines() if ln and not ln.startswith("*")]
            self.assertEqual(cards, [expected_nodesets[name],
                                     ".ic v(douta)=0 v(doutb)=0 v(doutc)=0"])
            self.assertEqual(icdc, ref + kb.probe_body_supplement(cond, "icdc"))

    def test_supplement_arms_reference_per_arm_body_files(self):
        for name in kb.PROBE_SUPPLIES_V:
            for arm in kb.PROBE_ARMS_415:
                req = self.request(name, arm)
                if arm in kb.PROBE_BODY_SUPPLEMENT_ARMS:
                    self.assertEqual(req["netlist"], f"kickback-{arm}.body.spice")
                else:
                    self.assertEqual(req["netlist"], kb.BODY_NAME)
                    self.assertEqual(kb.probe_body_name(arm), kb.BODY_NAME)

    def test_forced_output_polarity_is_the_wrong_one_and_nodes_are_real(self):
        block = kb.probe_body_supplement(kb.condition("vcm-m050"), "icdc")
        for node in ("bpp", "bpn", "cpp", "cpn", "douta", "doutb", "doutc"):
            self.assertIn(node, block)
        # dout seeded LOW (0 V): the wrong answer for a programmed positive
        # differential, never the expected high state the gate would pass on,
        # and never a supply value (0 V is the one supply-independent rail).
        self.assertIn(".ic v(douta)=0 v(doutb)=0 v(doutc)=0\n", block)

    def test_write_probe_inputs_append_only_and_supplement_paths(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "vcm-m050"
            for arm in kb.PROBE_ARMS_415:
                kb.write_probe_inputs(M050, arm, out, issue=self.ISSUE)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            ref = (kb.SERIES_DIR / "20261108-405-probe" / "vcm-m050" / kb.BODY_NAME).read_bytes()
            # shared body = #165 body (written by repro/obs); per-arm bodies =
            # #165 body + exactly the declared block
            self.assertEqual(before[kb.BODY_NAME], ref)
            self.assertEqual(before["kickback-icdc.body.spice"],
                             ref + kb.probe_body_supplement(M050, "icdc").encode("utf-8"))
            self.assertEqual(before["kickback-optdc.body.spice"],
                             ref + kb.probe_body_supplement(M050, "optdc").encode("utf-8"))
            self.assertIn("kickback-icdc.request.json", before)
            for arm in kb.PROBE_ARMS_415:  # identical rebuild: no-op
                kb.write_probe_inputs(M050, arm, out, issue=self.ISSUE)
            self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)
            (out / kb.BODY_NAME).write_bytes(b"tampered")
            with self.assertRaises(kb.KickbackCmBandError):
                kb.write_probe_inputs(M050, "repro", out, issue=self.ISSUE)

    def test_compare_with_supplement_arm_set_labels_issue_415(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            for cond in kb.CONDITIONS:
                out = series / cond.name
                for arm in kb.PROBE_ARMS_415:
                    kb.write_probe_inputs(cond, arm, out, issue=self.ISSUE)
                env = env_for(cond)
                for arm in kb.PROBE_ARMS_415:
                    (out / f"{kb.probe_arm_tag(arm)}.envelope.json").write_text(
                        json.dumps(env), encoding="utf-8")
            res = kb.probe_compare(series, arms=kb.PROBE_ARMS_415, issue=self.ISSUE)
            self.assertEqual(res["problems"], [])
            self.assertEqual(res["issue"], 415)
            self.assertEqual(set(res["arms"]), {f"{c.name}/{a}" for c in kb.CONDITIONS
                                                for a in kb.PROBE_ARMS_415})
            # the synthetic edges carry #165's values, so repro/obs equal it;
            # a forced-body arm would legitimately differ on the gate cards.
            md = kb.probe_render_markdown(res)
            self.assertIn("issue #415", md)

    def test_unknown_supplement_arm_refused_everywhere(self):
        with self.assertRaises(kb.KickbackCmBandError):
            kb.probe_request(M050, "icdc2")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(kb.KickbackCmBandError):
                kb.write_probe_inputs(M050, "icdc2", Path(d))


class SupplementRunner(unittest.TestCase):
    """Runner-level arm-set selection and the frozen-series compare guard."""

    @staticmethod
    def build_args(series, arm=None):
        return mock.Mock(series=series, condition=None, arm=arm)

    def test_default_arms_by_series(self):
        self.assertEqual(rkb._arms_for("20261108-405-probe", None), kb.PROBE_ARMS)
        self.assertEqual(rkb._arms_for("20261114-415-forceddc", None), kb.PROBE_ARMS_415)
        self.assertEqual(rkb._arms_for("any-series", ["repro"]), ("repro",))

    def test_default_issue_by_series(self):
        self.assertEqual(rkb._issue_for("20261108-405-probe"), kb.PROBE_ISSUE)
        self.assertEqual(rkb._issue_for("20261114-415-forceddc"), kb.SUPPLEMENT_ISSUE)

    def test_probe_build_defaults_write_the_supplement_arm_set(self):
        # inside the repo tree: cmd_probe_build prints repo-relative paths and
        # compose_body derives its declared hashes from REPO_ROOT-relative paths
        with tempfile.TemporaryDirectory(dir=rkb.build_mod.SIM_DIR) as d:
            series = Path(d)
            with mock.patch.object(rkb, "_series", return_value=series):
                self.assertEqual(rkb.cmd_probe_build(self.build_args("20261114-x")), 0)
            written = sorted(p.name for p in (series / "vcm-m050").iterdir())
            for arm in kb.PROBE_ARMS_415:
                self.assertIn(f"kickback-{arm}.request.json", written)
            req = json.loads((series / "vcm-m050" / "kickback-icdc.request.json")
                             .read_text(encoding="utf-8"))
            self.assertEqual(req["_condition"]["issue"], 415)
            self.assertEqual(req["netlist"], "kickback-icdc.body.spice")

    def test_probe_build_conflict_writes_nothing(self):
        # a conflict on a later arm must not leave the earlier arms written
        with tempfile.TemporaryDirectory(dir=rkb.build_mod.SIM_DIR) as d:
            series = Path(d)
            conflicting = series / "vcm-m050" / "kickback-icdc.request.json"
            conflicting.parent.mkdir(parents=True)
            conflicting.write_bytes(b"tampered")
            with mock.patch.object(rkb, "_series", return_value=series):
                self.assertEqual(
                    rkb.cmd_probe_build(self.build_args("20261114-x")), 1)
            self.assertEqual(sorted(p.name for p in (series / "vcm-m050").iterdir()),
                             ["kickback-icdc.request.json"])
            self.assertFalse((series / "vcm-nom").exists())
            self.assertFalse((series / "vcm-p050").exists())
            self.assertEqual(conflicting.read_bytes(), b"tampered")

    def test_probe_compare_refuses_frozen_series_with_other_arms(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            with mock.patch.object(rkb, "_series", return_value=series):
                code = rkb.cmd_probe_compare(self.build_args("20261108-405-probe", ["icdc"]))
            self.assertEqual(code, 1)
            self.assertFalse((series / "comparison.json").exists())

    def test_compare_on_frozen_405_series_reports_no_problems(self):
        # Regression guard (hazard: appending to kb.PROBE_ARMS makes the frozen
        # series report spurious missing envelopes and rewrites its committed
        # comparison files): the #405 arm set over the committed series must
        # stay problem-free and reproduce the committed comparison exactly.
        res = kb.probe_compare(kb.SERIES_DIR / "20261108-405-probe", arms=kb.PROBE_ARMS)
        self.assertEqual(res["problems"], [])
        committed = json.loads((kb.SERIES_DIR / "20261108-405-probe" / "comparison.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual(res, committed)
        self.assertEqual(kb.probe_render_markdown(res),
                         (kb.SERIES_DIR / "20261108-405-probe" / "comparison.md")
                         .read_text(encoding="utf-8"))


class Evidence(unittest.TestCase):
    def test_cmd_build_conflict_writes_nothing(self):
        # a conflict on a later condition must not leave earlier conditions
        # written (the whole build is one preflighted batch)
        with tempfile.TemporaryDirectory(dir=rkb.build_mod.SIM_DIR) as d:
            series = Path(d)
            conflicting = series / "vcm-p050" / kb.BODY_NAME
            conflicting.parent.mkdir(parents=True)
            conflicting.write_bytes(b"tampered")
            args = mock.Mock(series="s", condition=None)
            with mock.patch.object(rkb, "_series", return_value=series):
                self.assertEqual(rkb.cmd_build(args), 1)
            self.assertEqual([p for p in series.rglob("*") if p.is_file()], [conflicting])
            self.assertEqual(conflicting.read_bytes(), b"tampered")

    def test_build_is_append_only(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "vcm-nom"
            kb.write_condition_inputs(NOM, out)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            kb.write_condition_inputs(NOM, out)  # identical rebuild: no-op
            (out / kb.BODY_NAME).write_text("tampered", encoding="utf-8")
            with self.assertRaises(kb.KickbackCmBandError):
                kb.write_condition_inputs(NOM, out)
            self.assertEqual((out / kb.BODY_NAME).read_text(), "tampered")
            self.assertEqual(set(before), {kb.BODY_NAME, "kickback.request.json"})

    def test_write_condition_inputs_refuses_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "vcm-nom"
            out.mkdir()
            outside = root / "outside" / "stolen.spice"
            (out / kb.BODY_NAME).symlink_to(outside)
            with self.assertRaises(kb.KickbackCmBandError):
                kb.write_condition_inputs(NOM, out)
            self.assertFalse(outside.exists())  # the symlink target was NOT created
            self.assertEqual([p.name for p in out.iterdir()], [kb.BODY_NAME])

    def test_write_condition_inputs_refuses_directory_destination(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "vcm-nom"
            (out / kb.BODY_NAME).mkdir(parents=True)
            with self.assertRaises(kb.KickbackCmBandError):  # not a bare IsADirectoryError
                kb.write_condition_inputs(NOM, out)
            self.assertFalse((out / "kickback.request.json").exists())

    def test_write_probe_inputs_refuses_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            series = root / "series"
            out = series / "vcm-m050"
            out.mkdir(parents=True)
            seed_probe_ref_body(series, M050)
            outside = root / "outside" / "stolen.spice"
            (out / kb.BODY_NAME).symlink_to(outside)
            with mock.patch.object(kb, "SERIES_DIR", series):
                with self.assertRaises(kb.KickbackCmBandError):
                    kb.write_probe_inputs(M050, "repro", out)
            self.assertFalse(outside.exists())
            self.assertEqual([p.name for p in out.iterdir()], [kb.BODY_NAME])

    def test_write_probe_inputs_refuses_directory_destination(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            out = series / "vcm-m050"
            (out / kb.BODY_NAME).mkdir(parents=True)
            seed_probe_ref_body(series, M050)
            with mock.patch.object(kb, "SERIES_DIR", series):
                with self.assertRaises(kb.KickbackCmBandError):
                    kb.write_probe_inputs(M050, "repro", out)
            self.assertFalse((out / "kickback-repro.request.json").exists())

    def test_run_refuses_existing_envelope_and_completed_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            out = series / "vcm-nom"
            kb.write_condition_inputs(NOM, out)
            args = mock.Mock(series="s", condition="vcm-nom", skip_existing=False,
                             retry_refused=0, retry_wait=0, klt="klt", force=False)
            with mock.patch.object(rkb, "_series", return_value=series), \
                    mock.patch.object(kcli, "_submit", return_value=0) as sub:
                (out / "kickback.envelope.json").write_text("{}")
                self.assertEqual(rkb.cmd_run(args), 1)
                (out / "kickback.envelope.json").unlink()
                (out / "attempts.jsonl").write_text(
                    json.dumps({"tag": "kickback", "exit_code": 3}) + "\n")
                self.assertEqual(rkb.cmd_run(args), 1)
                sub.assert_not_called()
                (out / "attempts.jsonl").write_text(
                    json.dumps({"tag": "kickback", "exit_code": 1}) + "\n")
                self.assertEqual(rkb.cmd_run(args), 0)
                sub.assert_called_once()

    def test_probe_run_submits_on_batch_through_the_retry_helper(self):
        """cmd_probe_run keeps --backend batch and the fleet-cap retry loop
        after adopting kcli._submit_with_retry (issue #431)."""
        arm = "repro"
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            seed_probe_ref_body(series, NOM)
            out = series / NOM.name
            with mock.patch.object(kb, "SERIES_DIR", series):
                kb.write_probe_inputs(NOM, arm, out)
            args = mock.Mock(series="s", condition=NOM.name, arm=arm, skip_existing=False,
                             retry_refused=2, retry_wait=5, klt="klt", force=False)
            with mock.patch.object(rkb, "_series", return_value=series), \
                    mock.patch.object(kcli, "_submit", return_value=0) as sub:
                self.assertEqual(rkb.cmd_probe_run(args), 0)
            sub.assert_called_once()
            self.assertEqual(sub.call_args.kwargs["backend"], "batch")
            extra = sub.call_args.kwargs["extra"]
            self.assertEqual(extra["kind"], "probe")
            self.assertEqual(extra["probe_arm"], arm)
            self.assertEqual(sub.call_args.args[:3],
                             (out / f"{kb.probe_arm_tag(arm)}.request.json", out,
                              kb.probe_arm_tag(arm)))

    def test_probe_run_retries_while_the_fleet_refuses_at_its_cap(self):
        arm = "obs"
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            seed_probe_ref_body(series, NOM)
            out = series / NOM.name
            with mock.patch.object(kb, "SERIES_DIR", series):
                kb.write_probe_inputs(NOM, arm, out)
            args = mock.Mock(series="s", condition=NOM.name, arm=arm, skip_existing=False,
                             retry_refused=2, retry_wait=5, klt="klt", force=False)
            sleeps = []
            with mock.patch.object(rkb, "_series", return_value=series), \
                    mock.patch.object(kcli, "_submit", side_effect=[2, 2, 0]) as sub, \
                    mock.patch.object(kcli, "_last_attempt_refused_at_cap",
                                      return_value=True), \
                    mock.patch.object(kcli.time, "sleep", sleeps.append):
                self.assertEqual(rkb.cmd_probe_run(args), 0)
            self.assertEqual(sub.call_count, 3)
            self.assertEqual(sleeps, [5, 5])
            self.assertEqual([c.kwargs["backend"] for c in sub.call_args_list],
                             ["batch"] * 3)

    def test_compare_is_deterministic_from_saved_envelopes(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            for cond in kb.CONDITIONS:
                out = series / cond.name
                kb.write_condition_inputs(cond, out)
                (out / "kickback.envelope.json").write_text(json.dumps(env_for(cond)))
            a = kb.compare_series(series)
            b = kb.compare_series(series)
            self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
            self.assertEqual(kb.render_markdown(a), kb.render_markdown(b))
            # synthetic edges carry the nominal values, so the gate passes
            self.assertTrue(a["reproduction"]["ok"], a["reproduction"])
            self.assertEqual(a["per_point"][0]["vcm-m050"]["residue_delta_vs_nom_uv"], 0.0)


if __name__ == "__main__":
    unittest.main()

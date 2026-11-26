"""Kickback CM-band campaign tests (issue #165). Stdlib only; no PDK, no
ngspice, writes nothing outside a temporary directory.

Uses the committed issue #62 kickback envelope/request/body as a read-only
fixture and perturbs deep copies of it.
"""

from __future__ import annotations

import contextlib
import copy
import io
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
    byte-identity check in ``check_probe_reference_body`` stays independent of
    campaign evidence outside the CI sparse cone (see test_run_offset_cm_band)."""
    ref = series / kb.PROBE_REFERENCE_SERIES / cond.name / kb.BODY_NAME
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(kb.compose_body(cond))


def commit_build_inputs(planned, *, evidence="campaign evidence"):
    """The kickback CLIs' commit path (issue #543): ``kcli.commit_build``
    with the series evidence wording. Returns (exit code, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = kcli.commit_build("build", planned, evidence=evidence)
    return rc, err.getvalue()


def commit_condition_inputs(cond, out_dir):
    """What ``run_kickback_cm_band build`` commits for one condition."""
    return commit_build_inputs([(out_dir / n, data)
                                for n, data in kb.input_bytes(cond).items()])


def commit_probe_inputs(cond, arm, out_dir, issue=kb.PROBE_ISSUE):
    """What ``run_kickback_cm_band probe-build`` commits for one arm."""
    files = kb.probe_input_bytes(cond, arm, issue=issue)
    kb.check_probe_reference_body(cond, arm, files)
    return commit_build_inputs([(out_dir / n, data) for n, data in files.items()],
                               evidence="probe evidence")


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

    def _null(self, env, name, corner_idx=0):
        meas(env["corners"][corner_idx], name)["value"] = None

    def test_null_null_pair_is_problem_not_compared(self):
        # issue #532: a null/null pair is a missing measurement, not compared
        nom = env_for(NOM)
        ref = copy.deepcopy(REF_ENV)
        self._null(nom, "kick_sigdep_uv")
        self._null(ref, "kick_sigdep_uv")
        r = kb.reproduction_check(nom, kb.compose_request(NOM), kb.compose_body(NOM),
                                  ref, REF_REQ, REF_BODY)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["values_compared"], r["expected_values"] - 1)
        self.assertEqual(r["mismatches"], [])
        self.assertEqual(len(r["problems"]), 1)
        self.assertIn("unmeasured", r["problems"][0])
        self.assertIn("both sides", r["problems"][0])

    def test_null_on_one_side_is_problem_not_compared(self):
        nom = env_for(NOM)
        self._null(nom, "kick_sigdep_uv")
        r = self.check(env=nom)
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["values_compared"], r["expected_values"] - 1)
        self.assertEqual(r["mismatches"], [])
        self.assertEqual(len(r["problems"]), 1)
        self.assertIn("one side", r["problems"][0])


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

    def test_commit_probe_inputs_append_only_and_supplement_paths(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "vcm-m050"
            for arm in kb.PROBE_ARMS_415:
                self.assertEqual(commit_probe_inputs(M050, arm, out, issue=self.ISSUE)[0], 0)
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
                self.assertEqual(commit_probe_inputs(M050, arm, out, issue=self.ISSUE)[0], 0)
            self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)
            (out / kb.BODY_NAME).write_bytes(b"tampered")
            self.assertEqual(commit_probe_inputs(M050, "repro", out, issue=self.ISSUE)[0], 1)

    def test_compare_with_supplement_arm_set_labels_issue_415(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            for cond in kb.CONDITIONS:
                out = series / cond.name
                for arm in kb.PROBE_ARMS_415:
                    self.assertEqual(commit_probe_inputs(cond, arm, out, issue=self.ISSUE)[0], 0)
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
        with self.assertRaises(kb.KickbackCmBandError):
            kb.probe_input_bytes(M050, "icdc2")


class ProbeCompareNulls(unittest.TestCase):
    """Issue #535: a null-valued original card must not certify equality."""

    @staticmethod
    def ref_env(cond):
        return json.loads(
            (kb.SERIES_DIR / kb.PROBE_REFERENCE_SERIES / cond.name
             / f"{kb.TAG}.envelope.json").read_text(encoding="utf-8"))

    def write_series(self, series, arm_env):
        for cond in kb.CONDITIONS:
            out = series / cond.name
            out.mkdir(parents=True)
            for arm in kb.PROBE_ARMS:
                for name, data in kb.probe_input_bytes(cond, arm).items():
                    (out / name).write_bytes(data)
                (out / f"{kb.probe_arm_tag(arm)}.envelope.json").write_text(
                    json.dumps(arm_env(cond)), encoding="utf-8")

    def write_reference(self, base, ref_env):
        for cond in kb.CONDITIONS:
            out = base / kb.PROBE_REFERENCE_SERIES / cond.name
            out.mkdir(parents=True)
            (out / f"{kb.TAG}.envelope.json").write_text(
                json.dumps(ref_env(cond)), encoding="utf-8")

    @staticmethod
    def null(env, name):
        for c in env["corners"]:
            meas(c, name)["value"] = None
        return env

    @staticmethod
    def rows(res):
        return [a for r in res["points"] for a in r["arms"].values()
                if a.get("present")]

    def test_null_on_only_one_side_is_a_diff(self):
        def with_null(cond):
            return self.null(self.ref_env(cond), "kick_sigdep_uv")

        for side in ("arm", "reference"):
            with self.subTest(null_side=side), tempfile.TemporaryDirectory() as d:
                base = Path(d)
                series = base / "series"
                self.write_reference(base, with_null if side == "reference" else self.ref_env)
                self.write_series(series, with_null if side == "arm" else self.ref_env)
                with mock.patch.object(kb, "SERIES_DIR", base):
                    res = kb.probe_compare(series, arms=kb.PROBE_ARMS)
                self.assertEqual(res["problems"], [])
                for a in self.rows(res):
                    self.assertEqual(a["differs_from_165"], ["kick_sigdep_uv"])
                    self.assertNotIn("unmeasured_on_original_cards", a)
                    self.assertFalse(a["equals_165_on_original_cards"], a)
                self.assertIn("| False | kick_sigdep_uv |", kb.probe_render_markdown(res))

    def test_null_null_original_card_is_unmeasured_not_equal(self):
        # None == None is not evidence of equality: with the card null on both
        # sides the flag must fall without inventing a diff
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self.write_reference(
                base, lambda cond: self.null(self.ref_env(cond), "kick_sigdep_uv"))
            series = base / "series"
            self.write_series(
                series, lambda cond: self.null(self.ref_env(cond), "kick_sigdep_uv"))
            with mock.patch.object(kb, "SERIES_DIR", base):
                res = kb.probe_compare(series, arms=kb.PROBE_ARMS)
            self.assertEqual(res["problems"], [])
            for a in self.rows(res):
                self.assertEqual(a["unmeasured_on_original_cards"],
                                 ["kick_sigdep_uv"])
                self.assertFalse(a["equals_165_on_original_cards"], a)
                self.assertEqual(a["differs_from_165"], [])
            self.assertIn("| False | unmeasured: kick_sigdep_uv |",
                          kb.probe_render_markdown(res))

    def test_all_measured_baseline_emits_no_unmeasured_field(self):
        # conditional emission keeps committed comparisons byte-identical
        with tempfile.TemporaryDirectory() as d:
            series = Path(d) / "series"
            self.write_series(series, self.ref_env)
            res = kb.probe_compare(series, arms=kb.PROBE_ARMS)
            self.assertEqual(res["problems"], [])
            self.assertNotIn("unmeasured_on_original_cards", json.dumps(res))
            md = kb.probe_render_markdown(res)
            self.assertNotIn("unmeasured:", md)
            for a in self.rows(res):
                self.assertTrue(a["equals_165_on_original_cards"], a)
                self.assertEqual(a["differs_from_165"], [])

    def test_empty_original_cards_stay_false(self):
        # a reference corner with no measurement cards gives no equality basis
        def no_cards(cond):
            env = self.ref_env(cond)
            for c in env["corners"]:
                c["measurements"] = []
            return env

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self.write_reference(base, no_cards)
            series = base / "series"
            self.write_series(series, self.ref_env)
            with mock.patch.object(kb, "SERIES_DIR", base):
                res = kb.probe_compare(series, arms=kb.PROBE_ARMS)
            self.assertEqual(res["problems"], [])
            for a in self.rows(res):
                self.assertFalse(a["equals_165_on_original_cards"], a)
                self.assertNotIn("unmeasured_on_original_cards", a)
                self.assertEqual(a["differs_from_165"], [])

    def test_null_added_card_keeps_equality(self):
        # a null on a probe-added card (not an original #165 card) is not the
        # flag's concern, as in the committed xing rows
        def null_added(cond):
            env = self.ref_env(cond)
            for c in env["corners"]:
                c["measurements"].append(
                    {"name": "vcm_probe", "value": None, "unit": "V",
                     "status": "pass", "margin": None})
            return env

        with tempfile.TemporaryDirectory() as d:
            series = Path(d) / "series"
            self.write_series(series, null_added)
            res = kb.probe_compare(series, arms=kb.PROBE_ARMS)
            self.assertEqual(res["problems"], [])
            for a in self.rows(res):
                self.assertTrue(a["equals_165_on_original_cards"], a)
                self.assertNotIn("unmeasured_on_original_cards", a)
                self.assertIsNone(a["values"]["vcm_probe"])


class SupplementRunner(unittest.TestCase):
    """Runner-level arm-set selection and the frozen-series compare guard."""

    @staticmethod
    def build_args(series, arm=None):
        # report_dir/check are explicit (never Mock-synthesized) so the
        # in-place frozen-series guard sees a real in-place probe-compare.
        return mock.Mock(series=series, condition=None, arm=arm,
                         report_dir=None, check=False)

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
        with tempfile.TemporaryDirectory(dir=kb.build_mod.SIM_DIR) as d:
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
        with tempfile.TemporaryDirectory(dir=kb.build_mod.SIM_DIR) as d:
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

    def test_frozen_415_comparison_reproduces_byte_for_byte(self):
        series = kb.SERIES_DIR / "20261114-415-forceddc"
        res = kb.probe_compare(series, arms=kb.PROBE_ARMS_415, issue=kb.SUPPLEMENT_ISSUE)
        self.assertEqual(res["problems"], [])
        self.assertEqual((json.dumps(res, indent=2) + "\n").encode("utf-8"),
                         (series / "comparison.json").read_bytes())
        self.assertEqual(kb.probe_render_markdown(res).encode("utf-8"),
                         (series / "comparison.md").read_bytes())


class Evidence(unittest.TestCase):
    def test_cmd_build_conflict_writes_nothing(self):
        # a conflict on a later condition must not leave earlier conditions
        # written (the whole build is one preflighted batch)
        with tempfile.TemporaryDirectory(dir=kb.build_mod.SIM_DIR) as d:
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
            self.assertEqual(commit_condition_inputs(NOM, out)[0], 0)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            self.assertEqual(commit_condition_inputs(NOM, out)[0], 0)  # identical rebuild
            (out / kb.BODY_NAME).write_text("tampered", encoding="utf-8")
            self.assertEqual(commit_condition_inputs(NOM, out)[0], 1)
            self.assertEqual((out / kb.BODY_NAME).read_text(), "tampered")
            self.assertEqual(set(before), {kb.BODY_NAME, "kickback.request.json"})

    def test_commit_condition_inputs_refuses_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "vcm-nom"
            out.mkdir()
            outside = root / "outside" / "stolen.spice"
            (out / kb.BODY_NAME).symlink_to(outside)
            self.assertEqual(commit_condition_inputs(NOM, out)[0], 1)
            self.assertFalse(outside.exists())  # the symlink target was NOT created
            self.assertEqual([p.name for p in out.iterdir()], [kb.BODY_NAME])

    def test_commit_condition_inputs_refuses_directory_destination(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "vcm-nom"
            (out / kb.BODY_NAME).mkdir(parents=True)
            self.assertEqual(commit_condition_inputs(NOM, out)[0], 1)  # not IsADirectoryError
            self.assertFalse((out / "kickback.request.json").exists())

    def test_commit_probe_inputs_refuses_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            series = root / "series"
            out = series / "vcm-m050"
            out.mkdir(parents=True)
            seed_probe_ref_body(series, M050)
            outside = root / "outside" / "stolen.spice"
            (out / kb.BODY_NAME).symlink_to(outside)
            with mock.patch.object(kb, "SERIES_DIR", series):
                self.assertEqual(commit_probe_inputs(M050, "repro", out)[0], 1)
            self.assertFalse(outside.exists())
            self.assertEqual([p.name for p in out.iterdir()], [kb.BODY_NAME])

    def test_commit_probe_inputs_refuses_directory_destination(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            out = series / "vcm-m050"
            (out / kb.BODY_NAME).mkdir(parents=True)
            seed_probe_ref_body(series, M050)
            with mock.patch.object(kb, "SERIES_DIR", series):
                self.assertEqual(commit_probe_inputs(M050, "repro", out)[0], 1)
            self.assertFalse((out / "kickback-repro.request.json").exists())

    def test_commit_condition_inputs_refuses_non_directory_out_dir(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "vcm-nom"
            out.write_text("not a directory", encoding="utf-8")
            rc, err = commit_condition_inputs(NOM, out)
            self.assertEqual(rc, 1)
            self.assertIn(f"{out}: exists and is not a directory", err)
            self.assertEqual(out.read_text(encoding="utf-8"), "not a directory")
            self.assertEqual([p.name for p in Path(d).iterdir()], ["vcm-nom"])

    def test_commit_probe_inputs_refuses_non_directory_out_dir(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            out = series / "vcm-m050"
            out.write_text("not a directory", encoding="utf-8")
            seed_probe_ref_body(series, M050)
            with mock.patch.object(kb, "SERIES_DIR", series):
                rc, err = commit_probe_inputs(M050, "repro", out)
            self.assertEqual(rc, 1)
            self.assertIn(f"{out}: exists and is not a directory", err)
            self.assertEqual(out.read_text(encoding="utf-8"), "not a directory")
            self.assertEqual(sorted(p.name for p in series.iterdir()),
                             sorted([kb.PROBE_REFERENCE_SERIES, "vcm-m050"]))

    def test_commit_build_refuses_non_directory_parents_in_batch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "vcm-m050").mkdir()
            (root / "vcm-nom").write_text("x", encoding="utf-8")
            (root / "vcm-p050").symlink_to(root / "vcm-m050")
            planned = [(root / cond.name / name, data)
                       for cond in kb.CONDITIONS for name, data in kb.input_bytes(cond).items()]
            rc, err = commit_build_inputs(planned)
            self.assertEqual(rc, 1)
            for name in ("vcm-nom", "vcm-p050"):
                self.assertIn(f"{root / name}: exists and is not a directory", err)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["vcm-m050", "vcm-nom", "vcm-p050"])
            self.assertEqual(list((root / "vcm-m050").iterdir()), [])

    def test_commit_build_refuses_non_directory_ancestor(self):
        for as_symlink in (False, True):
            with self.subTest(symlink=as_symlink), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                series = root / "series"
                if as_symlink:
                    series.symlink_to(root / "gone")
                else:
                    series.write_text("x", encoding="utf-8")
                rc, err = commit_build_inputs([(series / "vcm-nom" / kb.BODY_NAME, b"body")])
                self.assertEqual(rc, 1)
                self.assertIn(f"{series}: exists and is not a directory", err)
                self.assertFalse((root / "gone").exists())
                self.assertEqual([p.name for p in root.iterdir()], ["series"])

    def test_commit_follows_a_symlinked_ancestor(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            self.assertEqual(commit_condition_inputs(NOM, root / "link" / "series" / "vcm-nom")[0],
                             0)
            written = root / "real" / "series" / "vcm-nom"
            self.assertEqual(sorted(p.name for p in written.iterdir()),
                             sorted(kb.input_bytes(NOM)))

    def test_cmd_build_reports_non_directory_condition_dir(self):
        with tempfile.TemporaryDirectory(dir=kb.build_mod.SIM_DIR) as d, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            series = Path(d)
            (series / "vcm-nom").write_text("x", encoding="utf-8")
            args = mock.Mock(series="s", condition=None)
            with mock.patch.object(rkb, "_series", return_value=series):
                self.assertEqual(rkb.cmd_build(args), 1)
            self.assertIn(f"{series / 'vcm-nom'}: exists and is not a directory", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())
            self.assertEqual([p.name for p in series.iterdir()], ["vcm-nom"])

    def test_cmd_probe_build_reports_non_directory_condition_dir(self):
        with tempfile.TemporaryDirectory(dir=kb.build_mod.SIM_DIR) as d, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            series = Path(d)
            (series / "vcm-nom").write_text("x", encoding="utf-8")
            args = mock.Mock(series="20261114-x", condition=None, arm=None)
            with mock.patch.object(rkb, "_series", return_value=series):
                self.assertEqual(rkb.cmd_probe_build(args), 1)
            self.assertIn(f"{series / 'vcm-nom'}: exists and is not a directory", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())
            self.assertEqual([p.name for p in series.iterdir()], ["vcm-nom"])

    def test_run_refuses_existing_envelope_and_completed_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            out = series / "vcm-nom"
            self.assertEqual(commit_condition_inputs(NOM, out)[0], 0)
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
                self.assertEqual(commit_probe_inputs(NOM, arm, out)[0], 0)
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
                self.assertEqual(commit_probe_inputs(NOM, arm, out)[0], 0)
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
                self.assertEqual(commit_condition_inputs(cond, out)[0], 0)
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


def healthy_init_values(residue_uv=50.0):
    """One point's measured values as a healthy initialized run would report
    them: released control, full applied differential, low pre-strobe outputs,
    post-strobe crossings, gates at 1.0, and 29/55 ns samples whose own
    arithmetic reproduces ``kick_sigdep_uv`` (so the cross-check agrees)."""
    return {
        "init_ctl_1n": 1.0, "init_ctl_29n": 0.0,
        "b_vd_1n": 0.9996e-3, "b_vd_strobe": 0.9996e-3,
        "c_vd_1n": 99.96e-3, "c_vd_strobe": 99.96e-3,
        "dan_29n": 0.0, "dbn_29n": 0.0, "dcn_29n": 0.0,
        "a_dp_29n": 0.0, "a_dn_29n": 1.2,
        "b_dp_29n": 0.0, "b_dn_29n": 1.2,
        "c_dp_29n": 0.0, "c_dn_29n": 1.2,
        "a_t_half": 30.8e-9, "b_t_half": 31.0e-9, "c_t_half": 30.9e-9,
        "a_t_pair": 30.7e-9, "b_t_pair": 30.9e-9, "c_t_pair": 30.8e-9,
        "dout_1k_end": 1.0, "dout_float_small_end": 1.0, "dout_float_big_end": 1.0,
        "bd0": 0.9990e-3, "bd1": 1.0000e-3,
        "cd0": 99.949e-3, "cd1": 100.000e-3,
        "kick_sigdep_uv": residue_uv,
    }


class ColdInit552(unittest.TestCase):
    """Issue #552 cold-edge supplement: the init arm's request and body."""

    def request(self, cond_name, issue=kb.COLD_ISSUE):
        return kb.probe_request(kb.condition(cond_name), "init", issue=issue)

    def test_grid_is_exactly_the_four_points_and_batch(self):
        for name, sups in kb.PROBE_SUPPLIES_V.items():
            req = self.request(name)
            self.assertEqual(req["corners"]["process"], ["mos_ss"])
            self.assertEqual(req["corners"]["supply_v"], {"vsup": list(sups)})
            self.assertEqual(req["corners"]["temperature_c"], [-40.0])
            self.assertEqual(req["backend"], "batch")
            self.assertEqual(req["batch"]["capacity_wait_s"], 600)

    def test_labels_issue_552_and_declares_the_release(self):
        for name in kb.PROBE_SUPPLIES_V:
            req = self.request(name)
            self.assertEqual(req["_condition"]["issue"], 552)
            self.assertEqual(req["_condition"]["probe_arm"], "init")
            self.assertEqual(req["_condition"]["body_supplement"], "init")
            self.assertEqual(req["_condition"]["release_ns"], kb.INIT_RELEASE_NS)
            self.assertLess(req["_condition"]["released_fully_ns"], 29)
            self.assertIn("(issue #552)", req["_comment"][0])
            self.assertIn("init", req["_comment"][3])
        # the default issue label stays #405 (the runner routes #552 by series)
        self.assertEqual(self.request("vcm-nom", issue=kb.PROBE_ISSUE)
                         ["_condition"]["issue"], kb.PROBE_ISSUE)

    def test_cards_cover_the_qualification_observations(self):
        names = [m["name"] for m in self.request("vcm-m050")["measurements"]]
        self.assertEqual(len(names), len(set(names)))
        for name in (*kb.required_measurements(), "vcm_meas"):  # #165 originals
            self.assertIn(name, names)
        for name in ("b_vd_1n", "b_vd_strobe", "c_vd_1n", "c_vd_strobe",  # obs
                     "b_dp_55n", "c_dn_50n", "b_t_half", "b_t_pair",     # + xing
                     "a_t_half", "a_t_pair",                              # branch A
                     "a_dp_30n", "a_dn_55n",
                     "a_dp_29n", "a_dn_29n", "b_dp_29n", "b_dn_29n",      # pre-strobe
                     "c_dp_29n", "c_dn_29n",
                     "dan_29n", "dbn_29n", "dcn_29n",
                     "init_ctl_1n", "init_ctl_29n"):                      # release
            self.assertIn(name, names, name)

    def test_analysis_unchanged(self):
        for name in kb.PROBE_SUPPLIES_V:
            self.assertEqual(self.request(name)["analysis"],
                             {"kind": "tran", "args": "5p 60n"})

    def test_init_body_is_165_plus_exactly_the_declared_block(self):
        for name in kb.PROBE_SUPPLIES_V:
            cond = kb.condition(name)
            body = kb.probe_expected_body(cond, "init")
            self.assertEqual(body, kb.compose_body(cond)
                             + kb.probe_body_supplement(cond, "init"))
            sup = kb.probe_body_supplement(cond, "init")
            cards = [ln for ln in sup.splitlines() if ln and not ln.startswith("*")]
            self.assertEqual(len(cards), 9, cards)
            self.assertTrue(cards[0].startswith("vclti clti 0 pulse(1 0 "
                                                f"{kb.INIT_RELEASE_NS:g}n"))
            active = [ln for ln in sup.splitlines() if ln and not ln.startswith("*")]
            for forbidden in (".options", ".nodeset", ".ic ", ".tran"):
                self.assertNotIn(forbidden, "\n".join(active))

    def test_supplement_drives_analytic_targets_and_wrong_polarity(self):
        sup = kb.probe_body_supplement(kb.condition("vcm-m050"), "init")
        for node in ("bpp", "bpn", "cpp", "cpn", "douta", "doutb", "doutc", "clti"):
            self.assertIn(node, sup)
        # pins follow their own ideal sources (cm +/- dv/2), not hard numbers
        for node in ("bsp", "bsn", "csp", "csn"):
            self.assertIn(f"v({node})", sup)
        # outputs are switched to 0 V (the supply-independent LOW rail)
        for node in ("douta", "doutb", "doutc"):
            self.assertIn(f"Sinit_out{node[-1]} {node} 0 clti 0 {kb.INIT_SW_MODEL}", sup)
        self.assertIn(kb.INIT_SW_CARD, sup)

    def test_commit_probe_inputs_append_only(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "vcm-m050"
            self.assertEqual(commit_probe_inputs(M050, "init", out, issue=kb.COLD_ISSUE)[0], 0)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            self.assertEqual(sorted(before),
                             ["kickback-init.body.spice", "kickback-init.request.json"])
            self.assertEqual(commit_probe_inputs(M050, "init", out, issue=kb.COLD_ISSUE)[0], 0)
            self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)
            (out / "kickback-init.body.spice").write_bytes(b"tampered")
            self.assertEqual(commit_probe_inputs(M050, "init", out, issue=kb.COLD_ISSUE)[0], 1)


class ColdInitQualify(unittest.TestCase):
    """The #552 qualification rules on synthetic observations."""

    def qualify(self, **over):
        values = healthy_init_values()
        values.update(over)
        return kb.coldinit_qualify(values)

    def test_healthy_point_qualifies_and_meets(self):
        q = self.qualify()
        self.assertTrue(q["qualified"], q)
        self.assertEqual(q["failed"], [])
        self.assertEqual(q["residue_verdict"], "MET")

    def test_qualified_residue_above_the_bound_is_reportable_not_met(self):
        q = self.qualify(kick_sigdep_uv=kb.RESIDUE_TARGET_UV + 1.0)
        self.assertTrue(q["qualified"], q)  # the measurement is valid ...
        self.assertEqual(q["residue_verdict"], "NOT MET")  # ... and a miss is reportable

    def test_collapsed_stimulus_fails_both_differential_criteria(self):
        q = self.qualify(b_vd_strobe=23.5e-6, c_vd_strobe=2.353e-3)
        self.assertFalse(q["qualified"])
        self.assertTrue(any("b_vd_strobe" in w and "outside" in w for w in q["failed"]),
                        q["failed"])
        self.assertTrue(any("c_vd_strobe" in w and "outside" in w for w in q["failed"]),
                        q["failed"])
        self.assertIsNone(q["residue_verdict"])

    def test_output_already_high_before_the_strobe_fails(self):
        # the #415 icdc reject signature: parked high before the strobe, no crossing
        q = self.qualify(dbn_29n=1.0, b_t_half=None, b_dp_29n=1.2, b_dn_29n=0.0)
        self.assertFalse(q["qualified"])
        self.assertTrue(any("pre-strobe" in w and "opposite polarity" in w for w in q["failed"]))
        self.assertTrue(any("missing" in w and "b_t_half" in w for w in q["failed"]))

    def test_missing_crossing_alone_fails(self):
        q = self.qualify(c_t_half=None)
        self.assertFalse(q["qualified"])
        self.assertIn("c_t_half: the branch-c post-strobe low-to-high crossing is missing",
                      q["failed"])

    def test_gate_below_bound_fails(self):
        q = self.qualify(dout_float_big_end=0.68e-9)
        self.assertFalse(q["qualified"])
        self.assertTrue(any("dout_float_big_end" in w and "below" in w for w in q["failed"]))

    def test_drive_not_released_fails(self):
        q = self.qualify(init_ctl_29n=1.0)
        self.assertFalse(q["qualified"])
        self.assertTrue(any("not proven released" in w for w in q["failed"]))

    def test_drive_not_engaged_fails(self):
        q = self.qualify(init_ctl_1n=0.5)
        self.assertFalse(q["qualified"])
        self.assertTrue(any("not proven engaged" in w for w in q["failed"]))

    def test_stimulus_tolerance_boundaries(self):
        tol_b = kb.STIMULUS_TOL_REL * 1e-3
        self.assertTrue(self.qualify(b_vd_strobe=1e-3 + 0.999 * tol_b)["qualified"])
        q = self.qualify(b_vd_strobe=1e-3 + 1.001 * tol_b)
        self.assertFalse(q["qualified"])
        self.assertTrue(any("branch-b pin differential" in w for w in q["failed"]))
        self.assertTrue(self.qualify(c_vd_strobe=0.1 - 0.999 * kb.STIMULUS_TOL_REL * 0.1)
                        ["qualified"])
        self.assertFalse(self.qualify(c_vd_strobe=0.1 - 1.001 * kb.STIMULUS_TOL_REL * 0.1)
                         ["qualified"])

    def test_missing_observations_are_named(self):
        values = healthy_init_values()
        for name in ("init_ctl_29n", "b_vd_strobe", "dbn_29n", "b_t_half",
                     "dout_float_small_end", "kick_sigdep_uv"):
            broken = dict(values, **{name: None})
            q = kb.coldinit_qualify(broken)
            self.assertFalse(q["qualified"], name)
            self.assertTrue(any(name in w for w in q["failed"]), (name, q["failed"]))

    def test_residue_unmeasured_on_an_otherwise_qualified_point(self):
        q = self.qualify(kick_sigdep_uv=None)
        self.assertFalse(q["qualified"])
        self.assertTrue(any("kick_sigdep_uv is unmeasured" in w for w in q["failed"]))


class ColdInitCompare(unittest.TestCase):
    """coldinit_compare over a synthetic #552 series (stdlib only)."""

    @staticmethod
    def corner_values(cond, sup, residue_uv, **over):
        values = {n: 1.0 for n in kb.required_measurements()}
        values.update(healthy_init_values(residue_uv=residue_uv))
        values.update({"vcm_meas": cond.vcm_v(), "vdd_meas": float(sup),
                       "temp_meas": -40.0})
        values.update(over)
        return values

    def write_env(self, cdir, cond, per_supply, status="pass"):
        """One envelope for the condition, one corner per supply (the shape a
        real probe-run leaves: one request per condition)."""
        corners = []
        for sup, values in per_supply.items():
            cards = [{"name": n, "value": v, "unit": "C" if n == "temp_meas" else "V",
                      "status": "fail" if n == "dout_float_big_end" and v < 0.9 else "pass",
                      "margin": None} for n, v in values.items()]
            corners.append({"corner_id": f"mos_ss/{sup:.3f}V/-40C", "process": "mos_ss",
                            "supply_v": {"vsup": sup}, "temperature_c": -40.0,
                            "status": status, "measurements": cards})
        env = {"schema_version": 1, "status": status, "corner_count": len(corners),
               "passed": len(corners), "failed": 0, "errored": 0, "inconclusive": 0,
               "environment": {"engine": "ngspice", "engine_version": "47",
                               "models_lib_sha256": "0" * 64,
                               "remote": {"provider": "aws-batch-fleet",
                                          "job_id": "klt-sim-coldinit-test",
                                          "state": "SUCCEEDED"}},
               "corners": corners}
        cdir.mkdir(parents=True, exist_ok=True)
        for name, data in kb.probe_input_bytes(cond, "init", issue=kb.COLD_ISSUE).items():
            (cdir / name).write_bytes(data)
        (cdir / f"{kb.probe_arm_tag('init')}.envelope.json").write_text(
            json.dumps(env), encoding="utf-8")

    def write_165_reference(self, base):
        for cond in kb.CONDITIONS:
            env = env_for(cond)
            corners, _ = kb.load_points(env)
            picked = {k: v for k, v in corners.items()
                      if k in {("ss", round(float(s), 6), -40.0)
                               for s in kb.PROBE_SUPPLIES_V[cond.name]}}
            out = base / kb.PROBE_REFERENCE_SERIES / cond.name
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{kb.TAG}.envelope.json").write_text(
                json.dumps({"status": "pass", "corners": list(picked.values())}),
                encoding="utf-8")

    def write_series(self, base, mutate=None):
        self.write_165_reference(base)
        series = base / "series"
        for cond in kb.CONDITIONS:
            per_supply = {}
            for sup in kb.PROBE_SUPPLIES_V[cond.name]:
                over = {}
                if mutate:
                    over = mutate(cond, sup) or {}
                per_supply[sup] = self.corner_values(cond, sup, 50.0, **over)
            self.write_env(series / cond.name, cond, per_supply)
        return series

    def test_four_points_roles_pairs_and_classifications(self):
        with tempfile.TemporaryDirectory() as d:
            series = self.write_series(Path(d))
            with mock.patch.object(kb, "SERIES_DIR", Path(d)):
                res = kb.coldinit_compare(series)
                again = kb.coldinit_compare(series)
            self.assertEqual(res["problems"], [])
            self.assertEqual(res["issue"], 552)
            self.assertEqual(len(res["points"]), 4)
            by_ck = {(p["condition"], p["key"]): p for p in res["points"]}
            edge12 = by_ck[("vcm-m050", "ss/1.200V/-40C")]
            self.assertEqual(edge12["role"], "edge")
            self.assertEqual(edge12["pair"], "1.200 V supply pair")
            self.assertEqual(by_ck[("vcm-p050", "ss/1.080V/-40C")]["role"], "edge")
            self.assertEqual(by_ck[("vcm-nom", "ss/1.080V/-40C")]["role"], "control")
            self.assertEqual(by_ck[("vcm-nom", "ss/1.200V/-40C")]["role"], "control")
            controls = [p for p in res["points"] if p["role"] == "control"]
            self.assertEqual(sorted(p["condition"] for p in controls), ["vcm-nom"] * 2)
            self.assertEqual({p["supply_v"] for p in controls}, {1.08, 1.2})
            for p in res["points"]:
                self.assertTrue(p["qualification"]["qualified"], p)
                self.assertEqual(p["qualification"]["residue_verdict"], "MET")
                self.assertTrue(p["context_165"]["present"])
            # deterministic: the committed comparison is recomputed exactly
            self.assertEqual(json.dumps(res, sort_keys=True),
                             json.dumps(again, sort_keys=True))

    def test_unqualified_point_is_named_and_never_graded(self):
        def mutate(cond, sup):
            if cond.name == "vcm-m050":
                return {"b_vd_strobe": 21.9e-6, "c_vd_strobe": 2.191e-3}
            return None

        with tempfile.TemporaryDirectory() as d:
            series = self.write_series(Path(d), mutate)
            with mock.patch.object(kb, "SERIES_DIR", Path(d)):
                res = kb.coldinit_compare(series)
            self.assertEqual(res["problems"], [])
            edge = next(p for p in res["points"] if p["condition"] == "vcm-m050")
            q = edge["qualification"]
            self.assertFalse(q["qualified"])
            self.assertTrue(any("branch-b pin differential" in w for w in q["failed"]))
            self.assertIsNone(q["residue_verdict"])
            md = kb.coldinit_render_markdown(res)
            self.assertIn("**NO**", md)
            self.assertIn("not graded (unqualified)", md)
            self.assertIn("## Failed conditions, unqualified points", md)
            # every other point is still independently qualified and graded
            for p in res["points"]:
                if p is not edge:
                    self.assertTrue(p["qualification"]["qualified"])
                    self.assertEqual(p["qualification"]["residue_verdict"], "MET")

    def test_residue_inconsistent_with_its_own_samples_is_a_problem(self):
        with tempfile.TemporaryDirectory() as d:
            series = self.write_series(Path(d))
            cdir = series / "vcm-nom"
            env = json.loads((cdir / "kickback-init.envelope.json").read_text())
            for c in env["corners"]:
                meas(c, "kick_sigdep_uv")["value"] = 5000.0
            (cdir / "kickback-init.envelope.json").write_text(json.dumps(env))
            with mock.patch.object(kb, "SERIES_DIR", Path(d)):
                res = kb.coldinit_compare(series)
            self.assertTrue(any("inconsistent with its own 29/55 ns samples" in p
                                for p in res["problems"]), res["problems"])

    def test_missing_envelope_is_a_problem(self):
        with tempfile.TemporaryDirectory() as d:
            series = self.write_series(Path(d))
            (series / "vcm-m050" / "kickback-init.envelope.json").unlink()
            with mock.patch.object(kb, "SERIES_DIR", Path(d)):
                res = kb.coldinit_compare(series)
            self.assertIn("missing envelope vcm-m050/init", res["problems"])
            self.assertEqual(len(res["points"]), 3)  # the other conditions still report

    def test_wrong_arm_set_refused(self):
        with tempfile.TemporaryDirectory() as d:
            series = self.write_series(Path(d))
            with self.assertRaises(kb.KickbackCmBandError):
                kb.coldinit_compare(series, arms=("repro", "init"))

    def test_markdown_carries_the_summary_sections(self):
        with tempfile.TemporaryDirectory() as d:
            series = self.write_series(Path(d))
            with mock.patch.object(kb, "SERIES_DIR", Path(d)):
                res = kb.coldinit_compare(series)
            md = kb.coldinit_render_markdown(res)
            for fragment in ("issue #552", "pull/166", "## Qualification rules",
                             "## Four-point summary", "## Fleet jobs",
                             "klt-sim-coldinit-test", "## Historical context",
                             "probe-compare"):
                self.assertIn(fragment, md, fragment)
            self.assertIn(f"released {kb.INIT_RELEASE_NS:g} -> "
                          f"{kb.INIT_RELEASE_NS + 0.1:g} ns", md)


class ColdInitRunner(unittest.TestCase):
    """Runner-level routing of the #552 cold-edge series."""

    SERIES = "20261126-552-coldinit"

    def test_default_arms_and_issue_by_series(self):
        self.assertEqual(rkb._arms_for(self.SERIES, None), kb.PROBE_ARMS_552)
        self.assertEqual(rkb._issue_for(self.SERIES), kb.COLD_ISSUE)
        # historical routing unchanged
        self.assertEqual(rkb._issue_for("20261108-405-probe"), kb.PROBE_ISSUE)
        self.assertEqual(rkb._issue_for("20261114-415-forceddc"), kb.SUPPLEMENT_ISSUE)
        self.assertEqual(rkb._issue_for("any-other-series"), kb.SUPPLEMENT_ISSUE)
        self.assertEqual(rkb._arms_for("any-other-series", None), kb.PROBE_ARMS_415)
        self.assertIn("init", kb.ALL_PROBE_ARMS)

    def test_series_root_option_stages_outside_campaigns(self):
        args = mock.Mock(series="s", root=None)
        self.assertEqual(rkb._series(args), kb.SERIES_DIR / "s")
        args = mock.Mock(series="s", root="sim/.work/scratch")
        self.assertEqual(rkb._series(args), Path("sim/.work/scratch") / "s")
        args = mock.Mock(series="s")  # no root attribute at all
        self.assertEqual(rkb._series(args), kb.SERIES_DIR / "s")

    def test_probe_build_writes_only_the_init_arm(self):
        with tempfile.TemporaryDirectory(dir=kb.build_mod.SIM_DIR) as d:
            series = Path(d)
            args = mock.Mock(series=self.SERIES, condition=None, arm=None, root=None)
            with mock.patch.object(rkb, "_series", return_value=series):
                self.assertEqual(rkb.cmd_probe_build(args), 0)
            for cond in kb.CONDITIONS:
                written = sorted(p.name for p in (series / cond.name).iterdir())
                self.assertEqual(written, ["kickback-init.body.spice",
                                           "kickback-init.request.json"])
            req = json.loads((series / "vcm-m050" / "kickback-init.request.json")
                             .read_text(encoding="utf-8"))
            self.assertEqual(req["_condition"]["issue"], 552)
            self.assertEqual(req["netlist"], "kickback-init.body.spice")

    def test_probe_run_labels_the_invocation_with_issue_552(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d)
            out = series / "vcm-m050"
            self.assertEqual(commit_probe_inputs(M050, "init", out, issue=kb.COLD_ISSUE)[0], 0)
            args = mock.Mock(series=self.SERIES, condition="vcm-m050", arm="init",
                             skip_existing=False, retry_refused=0, retry_wait=0,
                             klt="klt", force=False, root=None)
            with mock.patch.object(rkb, "_series", return_value=series), \
                    mock.patch.object(kcli, "_submit", return_value=0) as sub:
                self.assertEqual(rkb.cmd_probe_run(args), 0)
            extra = sub.call_args.kwargs["extra"]
            self.assertEqual(extra["issue"], 552)
            self.assertEqual(extra["probe_arm"], "init")
            self.assertEqual(sub.call_args.kwargs["backend"], "batch")

    def test_probe_compare_publishes_the_four_point_summary(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for cond in kb.CONDITIONS:
                out = base / "series" / cond.name
                out.mkdir(parents=True)
                for name, data in kb.probe_input_bytes(cond, "init",
                                                       issue=kb.COLD_ISSUE).items():
                    (out / name).write_bytes(data)
            ref = base / kb.PROBE_REFERENCE_SERIES / cond.name
            ref.mkdir(parents=True, exist_ok=True)
            args = mock.Mock(series=self.SERIES, arm=None, report_dir=None, check=False,
                             root=None)
            with mock.patch.object(rkb, "_series", return_value=base / "series"), \
                    mock.patch.object(kb, "SERIES_DIR", base), \
                    mock.patch.object(kb, "coldinit_compare",
                                  return_value={"problems": [], "points": []}) as cmp, \
                    mock.patch.object(kb, "coldinit_render_markdown",
                                      return_value="md") as render, \
                    mock.patch.object(kcli, "publish_report_pair", return_value=0) as pub:
                self.assertEqual(rkb.cmd_probe_compare(args), 0)
            cmp.assert_called_once_with(base / "series", arms=kb.PROBE_ARMS_552)
            render.assert_called_once_with({"problems": [], "points": []})
            pub.assert_called_once()

    def test_probe_compare_refuses_non_init_arm_set_on_a_552_series(self):
        with tempfile.TemporaryDirectory() as d:
            series = Path(d) / "series"
            args = mock.Mock(series=self.SERIES, arm=["repro"], report_dir=None,
                             check=False, root=None)
            with mock.patch.object(rkb, "_series", return_value=series):
                self.assertEqual(rkb.cmd_probe_compare(args), 1)
            self.assertFalse((series / "comparison.json").exists())

    def test_default_issue_by_series_docs_example(self):
        # a series named with the token anywhere routes to #552 (documented)
        self.assertEqual(rkb._issue_for("x-552-y"), kb.COLD_ISSUE)

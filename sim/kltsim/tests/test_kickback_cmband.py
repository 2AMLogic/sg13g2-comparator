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

from kltsim import build, cli as kcli, kickback_cmband as kb

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


class Evidence(unittest.TestCase):
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

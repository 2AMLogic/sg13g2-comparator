"""Issue #105: fixture, A/B and fleet-smoke inputs are append-only (stdlib only)."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kltsim import cli, fixture


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


# The default mocked envelope is an incomplete control (issue #106), so ``ab``
# reports its "incomplete or differing" status (2) after a submission that ran.
AB_RAN = 2


class HelperBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.calls = 0

    def fake_run(self, cmd, **kw):
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "klt test\n", "")
        self.calls += 1
        return subprocess.CompletedProcess(
            cmd, 0, '{"status": "ok", "corners": [{"measurements": []}]}\n', "")

    def invoke(self, func, **kw):
        ns = dict(campaign="c1", klt="klt", force=False)
        ns.update(kw)
        err = io.StringIO()
        with mock.patch.object(cli, "CAMPAIGNS_DIR", self.root), \
                mock.patch.object(cli.subprocess, "run", self.fake_run), \
                mock.patch.object(fixture, "check_envelope", lambda b, e: {"ok": True}), \
                mock.patch.object(fixture, "render_markdown", lambda r: "table\n"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = func(argparse.Namespace(**ns))
        return code, err.getvalue()

    def touch_old(self, directory: Path):
        for p in directory.rglob("*"):
            if p.is_file():
                os.utime(p, ns=(10**9, 10**9))


class FixtureTests(HelperBase):
    def run_fixture(self, **kw):
        return self.invoke(cli.cmd_fixture, bench="kickback_fixture", **kw)

    def test_identical_repeat_preserves_inputs_then_envelope_refuses(self):
        self.assertEqual(self.run_fixture()[0], 0)
        out = self.root / "c1" / "fixture"
        self.touch_old(out)
        before = _snapshot(out)
        code, err = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertIn("append-only", err)
        self.assertEqual(_snapshot(out), before)
        self.assertEqual(self.calls, 1)

    def test_changed_body_refused_even_with_envelope_present(self):
        self.run_fixture()
        out = self.root / "c1" / "fixture"
        body = next(out.glob("*.body.spice"))
        body.write_bytes(body.read_bytes() + b"* changed\n")
        self.touch_old(out)
        before = _snapshot(out)
        code, err = self.run_fixture()
        self.assertEqual(code, 1)
        self.assertIn("NEW campaign ID", err)
        self.assertEqual(_snapshot(out), before)
        self.assertEqual(self.calls, 1)


class AbTests(HelperBase):
    def run_ab(self, **kw):
        ns = dict(process="mos_tt", supply=1.2, temperature=27)
        ns.update(kw)
        return self.invoke(cli.cmd_ab, **ns)

    def test_changed_conditions_refused_without_changes(self):
        self.run_ab()
        out = self.root / "c1" / "ab"
        self.touch_old(out)
        before = _snapshot(out)
        code, err = self.run_ab(temperature=85)
        self.assertEqual(code, 1)
        self.assertIn("NEW campaign ID", err)
        self.assertEqual(_snapshot(out), before)
        self.assertEqual(self.calls, 2)

    def test_second_arm_conflict_leaves_first_arm_untouched(self):
        out = self.root / "c1" / "ab"
        out.mkdir(parents=True)
        other = out / "kickback-without_instrument.request.json"
        other.write_text("{}\n")
        code, _ = self.run_ab()
        self.assertEqual(code, 1)
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["kickback-without_instrument.request.json"])
        self.assertEqual(other.read_text(), "{}\n")
        self.assertEqual(self.calls, 0)

    def test_identical_regeneration_with_pending_inputs_keeps_bytes(self):
        self.run_ab()
        out = self.root / "c1" / "ab"
        for p in out.glob("*.envelope.json"):
            p.unlink()  # e.g. a submission that never produced an envelope
        inputs = [p for p in out.iterdir() if p.name.endswith((".spice", ".request.json"))]
        for p in inputs:
            os.utime(p, ns=(10**9, 10**9))
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in inputs}
        self.assertEqual(self.run_ab()[0], AB_RAN)
        for p, state in before.items():
            self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns), state)

    def test_force_overwrites_explicitly(self):
        self.run_ab()
        out = self.root / "c1" / "ab"
        code, _ = self.run_ab(temperature=85, force=True)
        self.assertEqual(code, AB_RAN)
        self.assertIn("85", (out / "kickback-with_instrument.request.json").read_text())


DECISIONS = ("dout_1k_end", "dout_float_small_end", "dout_float_big_end")


def good_env(names=DECISIONS, value=1.0, **over):
    corner = {"process": "mos_tt", "supply_v": {"vsup": 1.2}, "temperature_c": 27,
              "status": "pass",
              "measurements": [{"name": n, "value": value, "status": "pass"} for n in names]}
    env = {"status": "pass", "corners": [corner]}
    env.update(over)
    return env


class AbControlTests(HelperBase):
    """Issue #106: both arm envelopes must be valid and complete."""

    def run_ab_with(self, with_env, without_env=None):
        envs = {"with_instrument": with_env,
                "without_instrument": good_env() if without_env is None else without_env}
        self.envs = envs

        def fake(cmd, **kw):
            if "--version" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "klt test\n", "")
            self.calls += 1
            arm = "with_instrument" if "with_instrument" in " ".join(map(str, cmd)) else "without_instrument"
            return subprocess.CompletedProcess(cmd, 0, json.dumps(envs[arm]) + "\n", "")

        self.fake_run = fake
        self.n = getattr(self, "n", 0) + 1  # fresh campaign: inputs are append-only
        camp = f"c{self.n}"
        code, err = self.invoke(cli.cmd_ab, campaign=camp, process="mos_tt", supply=1.2, temperature=27)
        out = self.root / camp / "ab"
        return code, err, json.loads((out / "ab.json").read_text()), out

    def assert_incomplete(self, res, *needles):
        code, err, ab, out = res
        self.assertEqual(code, 2)
        self.assertFalse(ab["decisions_identical"])
        self.assertEqual(ab["control_status"], "incomplete")
        text = "\n".join(ab["diagnostics"])
        for n in needles:
            self.assertIn(n, text)
            self.assertIn(n, err)
        for arm in ("with_instrument", "without_instrument"):
            self.assertTrue((out / f"kickback-{arm}.envelope.json").exists())

    def test_valid_identical_passes(self):
        code, _, ab, _ = self.run_ab_with(good_env())
        self.assertEqual(code, 0)
        self.assertTrue(ab["decisions_identical"])
        self.assertEqual(ab["control_status"], "complete")
        self.assertEqual(ab["decision_measurements"], sorted(DECISIONS))

    def test_differing_decision_fails(self):
        env = good_env()
        env["corners"][0]["measurements"][1]["value"] = 0.0
        code, _, ab, _ = self.run_ab_with(env)
        self.assertEqual(code, 2)
        self.assertFalse(ab["decisions_identical"])
        self.assertEqual(ab["control_status"], "complete")

    def test_gate_fail_status_is_still_valid_control(self):
        env = good_env(status="fail")
        env["corners"][0]["measurements"][0]["status"] = "fail"
        self.assertEqual(self.run_ab_with(env, good_env(status="fail"))[0], 0)

    def test_missing_decision_in_with_arm(self):
        env = good_env(DECISIONS[:2])
        self.assert_incomplete(self.run_ab_with(env), "with_instrument: dout_float_big_end missing")

    def test_missing_decision_in_without_arm(self):
        env = good_env(DECISIONS[1:])
        self.assert_incomplete(self.run_ab_with(good_env(), env), "without_instrument: dout_1k_end missing")

    def test_single_surviving_equal_row_is_not_identical(self):
        self.assert_incomplete(self.run_ab_with(good_env(DECISIONS[:1]), good_env(DECISIONS[:1])),
                               "dout_float_small_end missing")

    def test_empty_envelope(self):
        self.assert_incomplete(self.run_ab_with({}), "with_instrument: status", "corners must hold exactly one")

    def test_empty_corner_measurements(self):
        self.assert_incomplete(self.run_ab_with(good_env(())), "with_instrument: dout_1k_end missing")

    def test_wrong_corner(self):
        for field, val in (("process", "mos_ff"), ("temperature_c", 85), ("supply_v", {"vsup": 1.5})):
            env = good_env()
            env["corners"][0][field] = val
            key = "supply_v.vsup" if field == "supply_v" else field
            self.assert_incomplete(self.run_ab_with(good_env(), env), f"without_instrument: corners[0].{key}")

    def test_multi_corner(self):
        env = good_env()
        env["corners"].append(good_env()["corners"][0])
        self.assert_incomplete(self.run_ab_with(env), "with_instrument: corners must hold exactly one")

    def test_errored(self):
        env = good_env()
        env["corners"][0]["status"] = "error"
        self.assert_incomplete(self.run_ab_with(good_env(), env), "without_instrument: corners[0].status is error")
        self.assert_incomplete(self.run_ab_with(good_env(status="error")), "with_instrument: status")

    def test_duplicate_measurement(self):
        env = good_env()
        env["corners"][0]["measurements"].append({"name": "dout_1k_end", "value": 1.0})
        self.assert_incomplete(self.run_ab_with(env), "with_instrument: dout_1k_end duplicated")

    def test_null_nan_inf_values(self):
        for bad in (None, float("nan"), float("inf"), float("-inf"), True, "1"):
            env = good_env()
            env["corners"][0]["measurements"][2]["value"] = bad
            self.assert_incomplete(self.run_ab_with(good_env(), env),
                                   "without_instrument: dout_float_big_end value")

    def test_nan_in_both_arms_not_identical(self):
        envs = []
        for _ in range(2):
            e = good_env()
            e["corners"][0]["measurements"][0]["value"] = float("nan")
            envs.append(e)
        self.assert_incomplete(self.run_ab_with(*envs), "dout_1k_end value")

    def test_validator_is_pure_and_request_derived(self):
        req = {"corners": {"process": ["mos_tt"], "supply_v": {"vsup": [1.2]}, "temperature_c": [27]}}
        self.assertEqual(cli.validate_ab_envelope(good_env(), req, {"dout_1k_end"}, "x"), [])
        self.assertEqual(cli.validate_ab_envelope(good_env(), req, {"dout_new"}, "x"),
                         ["x: dout_new missing"])


class FleetSmokeTests(HelperBase):
    def run_smoke(self, **kw):
        ns = dict(bench="regeneration", tag=None, process=None, supply=1.2,
                  temperature=27, n=4, dut_param=None, bias_probes=False,
                  analysis_args=None)
        ns.update(kw)
        return self.invoke(cli.cmd_fleet_smoke, **ns)

    def test_tags_with_different_overrides_use_independent_bodies(self):
        self.assertEqual(self.run_smoke(tag="a")[0], 0)
        out = self.root / "c1" / "smoke"
        self.touch_old(out)
        before = _snapshot(out)
        self.assertEqual(self.run_smoke(tag="b", dut_param=["dut_ib=5e-6"])[0], 0)
        after = _snapshot(out)
        for name, state in before.items():
            if name.endswith("attempts.jsonl"):
                continue  # append-only attempt log grows by design
            self.assertEqual(after[name][0], state[0], name)
        self.assertTrue((out / "a.body.spice").is_file())
        self.assertNotEqual((out / "a.body.spice").read_bytes(),
                            (out / "b.body.spice").read_bytes())
        self.assertIn('"b.body.spice"', (out / "b.request.json").read_text())

    def test_repeat_tag_with_changed_conditions_refused(self):
        self.run_smoke(tag="a")
        out = self.root / "c1" / "smoke"
        self.touch_old(out)
        before = _snapshot(out)
        code, err = self.run_smoke(tag="a", dut_param=["dut_ib=5e-6"])
        self.assertEqual(code, 1)
        self.assertIn("NEW campaign ID", err)
        self.assertEqual(_snapshot(out), before)
        self.assertEqual(self.calls, 1)


if __name__ == "__main__":
    unittest.main()

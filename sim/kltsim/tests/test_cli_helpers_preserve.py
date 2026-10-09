"""Issue #105: fixture, A/B and fleet-smoke inputs are append-only (stdlib only)."""

from __future__ import annotations

import argparse
import contextlib
import io
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


# The mocked envelope has no dout_* measurements, so ``ab`` reports its
# "decisions not identical" status (2) after a submission that did run.
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

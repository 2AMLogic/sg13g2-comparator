"""Native-engine tests for the `klt yield` evidence workflow (issue #63).

NOT discovered by CI (`test_*.py`): the CI environment has no native yield
extension and its harness step forbids skipped tests. Run explicitly:

    KLT_YIELD_CMD='uvx --from "klayout-tools[yield] @ git+https://github.com/2AMLogic/klayout-tools@<manifests/klt-pin.json commit>" klt' \
        PYTHONPATH=sim python3 -m unittest kltsim.tests.engine_yield_reports

Without ``KLT_YIELD_CMD`` every test FAILS (an absent engine is an execution
failure, never a pass or a skip).
"""

from __future__ import annotations

import copy
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from kltsim import yield_reports as yr
from kltsim.tests.test_yield_reports import collect_offset, offset_bench

ENGINE = shlex.split(os.environ.get("KLT_YIELD_CMD", ""))


class NativeEngine(unittest.TestCase):
    pin = yr.load_pin()

    @classmethod
    def setUpClass(cls):
        if not ENGINE:
            raise AssertionError("KLT_YIELD_CMD is not set: the native klt yield engine is required")
        yr.engine_preflight(ENGINE, cls.pin)

    def _run_doc(self, doc, extra=()):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "doc.json"
            path.write_text(yr.dumps(doc), encoding="utf-8")
            proc = subprocess.run(ENGINE + ["yield", str(path), "--format", "json", *extra],
                                  capture_output=True, cwd=str(yr.REPO_ROOT))
        return proc.returncode, json.loads(proc.stdout)

    def test_derived_input_equals_direct_analysis_of_the_sim_report(self):
        """Nominal equivalence on the real committed envelope: keep ONE base
        corner's sampled corners in a copy of the klt sim report and analyse it
        directly; the derived per-PVT sample set must agree on n, distribution
        and empirical yield."""
        src = yr.REPO_ROOT / yr.SOURCE_CAMPAIGN / "offset_mc.mos_tt_mismatch.envelope.json"
        env = json.loads(src.read_text())
        keep = "mos_tt_mismatch/1.200V/27C/"
        env["corners"] = [c for c in env["corners"] if c["corner_id"].startswith(keep)]
        self.assertEqual(len(env["corners"]), 60)
        rc, direct = self._run_doc(env, ("--measurement", "vos_mv"))
        self.assertEqual(rc, 0)
        derived = json.loads((yr.REPO_ROOT / yr.OUT_ROOT / yr.DEFAULT_CAMPAIGN_ID
                              / "offset.yield.json").read_text())
        mine = next(m for m in derived["measurements"] if m["name"] == "vos_mv@tt_27c_1.20v")
        theirs = direct["measurements"][0]
        self.assertEqual(mine["n"], theirs["n"])
        self.assertEqual(mine["limits"], theirs["limits"])
        self.assertEqual(mine["distribution"], theirs["distribution"])
        self.assertEqual(mine["yield"], theirs["yield"])
        self.assertEqual(mine["capability"], theirs["capability"])

    def test_noise_derived_input_equals_direct_analysis(self):
        src = yr.REPO_ROOT / yr.SOURCE_CAMPAIGN / "transient_noise.mos_tt.envelope.json"
        env = json.loads(src.read_text())
        keep = "mos_tt/1.200V/27C/"
        env["corners"] = [c for c in env["corners"] if c["corner_id"].startswith(keep)]
        for m in env["measurements"]:
            m["limits"] = {"min": 0.5} if m["name"] == "hit_plus" else (
                {"max": 0.5} if m["name"] == "hit_minus" else None)
        rc, direct = self._run_doc(env, ("--measurement", "hit_plus,hit_minus"))
        self.assertEqual(rc, 0)
        derived = json.loads((yr.REPO_ROOT / yr.OUT_ROOT / yr.DEFAULT_CAMPAIGN_ID
                              / "noise.yield.json").read_text())
        for name in ("hit_plus", "hit_minus"):
            mine = next(m for m in derived["measurements"] if m["name"] == f"{name}@tt_27c_1.20v")
            theirs = next(m for m in direct["measurements"] if m["name"] == name)
            self.assertEqual(mine["n"], theirs["n"])
            self.assertEqual(mine["yield"], theirs["yield"])

    def test_over_limit_population_fails_the_analysis(self):
        pops = collect_offset(offset_bench(vos=lambda p, v, t, k: 40.0 + k))
        doc = yr.sample_set(pops, prefix="vos_mv", unit="mV",
                            limits_for={"min": -15.0, "max": 15.0, "target_yield": 0.9})
        rc, out = self._run_doc(doc)
        self.assertNotEqual(out["status"], "reported")
        self.assertEqual(out["status"], "fail")
        for m in out["measurements"]:
            self.assertEqual(m["yield"]["empirical"]["estimate"], 0.0)

    def test_in_limit_population_with_target_passes_only_with_enough_samples(self):
        pops = collect_offset(offset_bench(vos=lambda p, v, t, k: (k % 5) - 2.0))
        doc = yr.sample_set(pops, prefix="vos_mv", unit="mV",
                            limits_for={"min": -15.0, "max": 15.0, "target_yield": 0.99})
        _, out = self._run_doc(doc)
        # N = 60 cannot support a 99 % lower bound: never a pass
        self.assertEqual(out["status"], "fail")

    def test_derived_control_is_detected_and_a_fake_control_is_not(self):
        pops = collect_offset(offset_bench())
        ok = yr.sample_set(pops, prefix="vos_mv", unit="mV",
                           limits_for={"min": -15.0, "max": 15.0}, with_control=True)
        _, out = self._run_doc(ok)
        self.assertTrue(all(m["negative_control"]["verdict"] == "detected" for m in out["measurements"]))
        weak = copy.deepcopy(ok)
        for m in weak["measurements"]:
            m["negative_control"]["samples"] = list(m["samples"])    # in-limit "control"
        _, out = self._run_doc(weak)
        self.assertTrue(all(m["negative_control"]["verdict"] == "not_detected" for m in out["measurements"]))

    def test_committed_reports_reproduce_byte_for_byte(self):
        self.assertEqual(yr.check(yr.DEFAULT_CAMPAIGN_ID, klt_cmd=ENGINE, rerun=True), [])




if __name__ == "__main__":
    unittest.main()

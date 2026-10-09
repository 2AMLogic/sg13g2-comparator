"""Unit tests for ``harness.runner.run_point``'s error-visibility contract.

Ported verbatim in behaviour from ``2AMLogic/gf180-comparator``'s
``sim/harness/tests/test_runner.py`` (regression coverage for that repo's
issue #7): ``run_point()`` must not consult ``proc.returncode`` /
``_ERROR_RE`` only inside the ``if missing:`` branch, or a non-fatal ngspice
error (non-zero exit, or an Error/Fatal/doAnalyses: line) is silently
discarded whenever every requested measurement still happened to parse --
the point would come back ``status="ok"`` with no trace of what ngspice
reported. Nothing about this contract is PDK-specific (``run_point``'s
signature and ``PointResult`` are unchanged from gf180-comparator's), so
these tests stub the ``ngspice`` subprocess call (and ``compose_deck``,
exercised by ``harness/testbench.py``'s own fixtures already) exactly as
the source repo's version does, and run without ngspice installed and
without a real testbench/PDK/DUT.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.corners import CORNERS, PvtPoint  # noqa: E402
from harness.report import _json_num, _strict_point, summarize  # noqa: E402
from harness.runner import PointResult, run_point  # noqa: E402


def _fake_completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["ngspice", "-b", "deck.spice"], returncode=returncode, stdout=stdout, stderr=""
    )


class RunPointWarningsTest(unittest.TestCase):
    def setUp(self):
        self.point = PvtPoint(corner=CORNERS["tt"], temp_c=27.0, vdd=1.2, index=0)
        self.tb = types.SimpleNamespace(measure={"vos_mv": "v(out)"})
        self.pdk = types.SimpleNamespace()
        self.dut = types.SimpleNamespace()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workdir = Path(self._tmp.name)

    def _run(self, stdout: str, returncode: int = 0) -> PointResult:
        with mock.patch("harness.runner.compose_deck", return_value="* stub deck\n"), \
             mock.patch(
                 "harness.runner.subprocess.run",
                 return_value=_fake_completed(stdout, returncode),
             ):
            return run_point(self.tb, self.pdk, self.dut, self.point, self.workdir)

    def test_clean_run_has_no_warnings(self):
        """returncode == 0, no _ERROR_RE match -> status=ok, warnings=[]."""
        result = self._run("m_vos_mv = 6.9043645202e-01\n")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.warnings, [])

    def test_nonzero_returncode_with_all_measurements_parsed_is_still_ok_but_warns(self):
        """A non-fatal error must not be discarded just because every
        requested measurement still printed."""
        result = self._run("m_vos_mv = 6.9043645202e-01\n", returncode=1)
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.warnings, "non-zero returncode must surface a warning")
        self.assertTrue(any("1" in w for w in result.warnings))

    def test_error_re_match_with_all_measurements_parsed_is_still_ok_but_warns(self):
        stdout = "doAnalyses: convergence problem, retrying\nm_vos_mv = 6.9043645202e-01\n"
        result = self._run(stdout, returncode=0)
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.warnings, "an _ERROR_RE match must surface a warning")
        self.assertTrue(any("doAnalyses" in w for w in result.warnings))

    def test_missing_measurement_still_fails_and_carries_warnings(self):
        result = self._run("Error: singular matrix\n", returncode=1)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.missing, ["vos_mv"])
        self.assertTrue(result.warnings)

    def test_as_dict_includes_warnings_only_when_present(self):
        clean = self._run("m_vos_mv = 6.9043645202e-01\n")
        self.assertNotIn("warnings", clean.as_dict())

        warned = self._run("m_vos_mv = 6.9043645202e-01\n", returncode=1)
        self.assertIn("warnings", warned.as_dict())
        self.assertEqual(warned.as_dict()["warnings"], warned.warnings)


class NonFiniteMeasurementTest(RunPointWarningsTest):
    """Issue #111: overflow / NaN / inf must never become passing evidence."""

    def test_overflow_both_signs_is_failed_with_diagnostic(self):
        for raw in ("-1e999", "1e999"):
            result = self._run(f"m_vos_mv = {raw}\n")
            self.assertEqual(result.status, "failed", raw)
            self.assertNotIn("vos_mv", result.measurements)
            self.assertIn("vos_mv", result.invalid)
            self.assertIn("non-finite", result.message)

    def test_failure_keeps_raw_log_and_strict_json(self):
        result = self._run("m_vos_mv = -1e999\n")
        self.assertTrue((self.workdir / result.log).read_text().count("-1e999"))
        json.dumps(result.as_dict(), allow_nan=False)

    def test_finite_measurement_with_simulator_warning_stays_ok(self):
        result = self._run("doAnalyses: retry\nm_vos_mv = 1.5e-01\n", returncode=1)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.measurements, {"vos_mv": 0.15})
        self.assertTrue(result.warnings)
        self.assertEqual(result.invalid, {})


def _summ_tb(check):
    return types.SimpleNamespace(measure={"m": "v(out)"}, checks={"m": check})


def _pr(value, index=0, status="ok"):
    return PointResult(
        point=PvtPoint(corner=CORNERS["tt"], temp_c=27.0, vdd=1.2, index=index),
        status=status,
        measurements={"m": value},
    )


class SummaryDefensiveTest(unittest.TestCase):
    def test_one_point_max_only_and_min_only_reject_infinity(self):
        for check, value in (({"max": 1.0}, -math.inf), ({"min": 1.0}, math.inf)):
            summaries = summarize(_summ_tb(check), [_pr(value)])
            self.assertTrue(summaries["m"].failures, (check, value))

    def test_nan_and_infinities_rejected_without_exception(self):
        for value in (math.nan, math.inf, -math.inf):
            for check in ({"max": 1.0}, {"min": -1.0}, {"min_spread_pct": 0.0}):
                summaries = summarize(_summ_tb(check), [_pr(value), _pr(0.5, index=1)])
                self.assertTrue(
                    any("non-finite" in f for f in summaries["m"].failures), (value, check)
                )

    def test_derived_overflow_cannot_pass_and_json_is_strict(self):
        results = [_pr(1.7e308), _pr(-1.7e308, index=1)]
        tb = _summ_tb({"min_spread_pct": 0.0})
        summaries = summarize(tb, results)
        self.assertTrue(any("non-finite" in f for f in summaries["m"].failures))
        s = summaries["m"]
        payload = {
            "mean": _json_num(s.mean),
            "spread": _json_num(s.spread),
        }
        json.dumps(payload, allow_nan=False)

    def test_nonfinite_point_serializes_strict(self):
        record = _strict_point(_pr(math.nan), ["m"])
        json.dumps(record, allow_nan=False)
        self.assertIn("m", record["invalid_measurements"])

    def test_finite_verdicts_unchanged(self):
        summaries = summarize(_summ_tb({"max": 1.0, "min": 0.0}), [_pr(0.5)])
        self.assertEqual(summaries["m"].failures, [])


if __name__ == "__main__":
    unittest.main()

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

import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.corners import CORNERS, PvtPoint  # noqa: E402
from harness import report as report_mod  # noqa: E402
from harness.report import _json_num, _strict_point, summarize  # noqa: E402
from harness.runner import PointResult, run_grid, run_point  # noqa: E402


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


# --------------------------------------------------------------------------
# Issue #110: exclusive run-identity reservation and append-only evidence.
# --------------------------------------------------------------------------

FROZEN = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
COMMIT = "abc1234"


def _tree(root: Path) -> dict[str, str]:
    """Relative path -> sha256 (or 'dir') for every entry under ``root``."""
    out = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        out[rel] = "dir" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _tokens(*values):
    it = iter(values)
    return lambda: next(it)


class ReservationTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.exp = self.root / "sim" / "exp"
        self.exp.mkdir(parents=True)
        self.work = self.root / "sim" / ".work" / "exp"

    def reserve(self, write=True, **kw):
        kw.setdefault("now", FROZEN)
        kw.setdefault("commit", COMMIT)
        return report_mod.reserve_run(self.exp, self.work, write, **kw)

    def plant_bundle(self, rid: str) -> dict[str, str]:
        """A pre-existing committed bundle (record, twin, snapshot, logs)."""
        paths = report_mod.bundle_paths(self.exp, rid)
        paths["record"].parent.mkdir(parents=True, exist_ok=True)
        paths["record"].write_text(f"# Record {rid}\nold evidence\n")
        paths["json"].write_text(json.dumps({"record_id": rid}) + "\n")
        paths["snapshot"].parent.mkdir(parents=True, exist_ok=True)
        paths["snapshot"].write_text("* old snapshot\n")
        paths["logs"].mkdir(parents=True)
        (paths["logs"] / "tt_27c_1.20v.log").write_text("old raw log\n")
        return _tree(self.exp)


class ReserveRunTest(ReservationTestBase):
    def test_record_id_keeps_prefix_and_adds_token(self):
        rid = report_mod.record_id(FROZEN, COMMIT, "0a1b2c")
        self.assertEqual(rid, "20261009-120000-abc1234-0a1b2c")

    def test_frozen_clock_and_commit_give_distinct_identities(self):
        a = self.reserve()
        b = self.reserve()
        self.assertNotEqual(a.rid, b.rid)
        self.assertTrue(a.rid.startswith("20261009-120000-abc1234-"))
        self.assertNotEqual(a.workdir, b.workdir)
        self.assertNotEqual(a.log_dir, b.log_dir)
        for r in (a, b):
            self.assertTrue(r.workdir.is_dir())
            self.assertEqual(r.log_dir, self.exp / "corners" / r.rid)
            self.assertTrue(r.log_dir.is_dir())

    def test_no_write_run_gets_private_scratch_only(self):
        r = self.reserve(write=False)
        self.assertEqual(r.log_dir, r.workdir)
        self.assertFalse((self.exp / "corners").exists())

    def test_exclusive_reservation_race(self):
        """Many concurrent runs, same frozen clock/commit, all first trying
        the SAME token: exactly one wins it, the rest retry; every identity,
        scratch dir and log dir is distinct and exclusively created."""
        n = 8
        barrier = threading.Barrier(n)
        results, errors = [None] * n, []

        def worker(i):
            seq = iter(["5a5a5a"] + [f"{i:02d}{k:04d}" for k in range(50)])
            try:
                barrier.wait()
                results[i] = self.reserve(token_factory=lambda: next(seq))
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        rids = [r.rid for r in results]
        self.assertEqual(len(set(rids)), n)
        self.assertEqual(len({r.workdir for r in results}), n)
        self.assertEqual(len({r.log_dir for r in results}), n)
        self.assertEqual(sum(rid.endswith("-5a5a5a") for rid in rids), 1)
        self.assertEqual(
            sorted(p.name for p in (self.exp / "corners").iterdir()), sorted(rids)
        )

    def test_random_tokens_race_with_frozen_clock(self):
        n = 8
        barrier = threading.Barrier(n)
        results = [None] * n

        def worker(i):
            barrier.wait()
            results[i] = self.reserve()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len({r.rid for r in results}), n)

    def test_every_orphan_member_occupies_the_identity(self):
        taken = "20261009-120000-abc1234-dead00"
        for member in ("record", "json", "snapshot", "logs"):
            with self.subTest(member=member):
                path = report_mod.bundle_paths(self.exp, taken)[member]
                path.parent.mkdir(parents=True, exist_ok=True)
                if member == "logs":
                    path.mkdir()
                    (path / "x.log").write_text("orphan\n")
                else:
                    path.write_text("orphan\n")
                before = _tree(self.exp)
                r = self.reserve(token_factory=_tokens("dead00", "beef01"))
                self.assertEqual(r.rid, "20261009-120000-abc1234-beef01")
                after = _tree(self.exp)
                for rel, digest in before.items():
                    self.assertEqual(after[rel], digest, rel)
                r.release_scratch()
                # reset for the next member
                shutil.rmtree(self.exp)
                self.exp.mkdir()

    def test_occupied_scratch_dir_is_not_shared(self):
        self.work.mkdir(parents=True)
        squat = self.work / "20261009-120000-abc1234-aaaaaa"
        squat.mkdir()
        (squat / "other.spice").write_text("someone else's deck\n")
        r = self.reserve(token_factory=_tokens("aaaaaa", "bbbbbb"))
        self.assertEqual(r.rid, "20261009-120000-abc1234-bbbbbb")
        # the half-claimed evidence dir for "aaaaaa" was rolled back
        self.assertFalse((self.exp / "corners" / "20261009-120000-abc1234-aaaaaa").exists())
        self.assertTrue((squat / "other.spice").exists())

    def test_exhausted_retries_refuse_and_write_nothing(self):
        rid = "20261009-120000-abc1234-ffffff"
        before = self.plant_bundle(rid)
        with self.assertRaises(report_mod.ReservationFailed):
            self.reserve(token_factory=lambda: "ffffff", attempts=5)
        self.assertEqual(_tree(self.exp), before)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_cleanup_only_removes_the_invoking_runs_scratch(self):
        a = self.reserve()
        b = self.reserve()
        (a.workdir / "a.spice").write_text("a\n")
        (b.workdir / "b.spice").write_text("b\n")
        (a.log_dir / "tt.log").write_text("a log\n")
        a.release_scratch()
        self.assertFalse(a.workdir.exists())
        self.assertTrue((b.workdir / "b.spice").exists())
        self.assertTrue((a.log_dir / "tt.log").exists(), "evidence logs are kept")

    def test_historical_ids_are_recognised_and_paths_validated(self):
        old = "20260910-233015-8148438"  # pre-#110 format, no token
        self.assertEqual(report_mod.occupied_members(self.exp, old), [])
        self.plant_bundle(old)
        self.assertEqual(
            sorted(report_mod.occupied_members(self.exp, old)),
            ["json", "logs", "record", "snapshot"],
        )
        for bad in ("../x", "a/b", ".hidden", ""):
            with self.assertRaises(ValueError):
                report_mod.bundle_paths(self.exp, bad)


def _record_tb(experiment_dir: Path):
    netlist = experiment_dir / "testbench" / "tb.spice"
    netlist.parent.mkdir(parents=True, exist_ok=True)
    netlist.write_text("* tb fragment\n")
    return types.SimpleNamespace(
        experiment="exp", experiment_dir=experiment_dir, measure={"m": "v(out)"},
        checks={}, claim="", netlist=netlist, netlist_sha256="0" * 64,
        manifest_sha256="1" * 64, evidence={}, provenance=lambda: {"tb": "fake"},
    )


def _record_context(rid: str) -> dict:
    return {
        "record_id": rid, "commit": COMMIT, "dirty": False, "dirty_paths": [],
        "pdk": {"variant": "v", "release_version": "r", "discovered_via": "test"},
        "toolchain": {"observed": {"ngspice": "ngspice-46", "python": "3"}, "drift": []},
        "dut_id": "d", "dut_provenance": "schematic", "dut_netlist": "dut.spice",
        "dut_netlist_sha256": "2" * 64,
    }


class WriteRecordAppendOnlyTest(ReservationTestBase):
    def setUp(self):
        super().setUp()
        self.tb = _record_tb(self.exp)
        self.dut = self.root / "dut.spice"
        self.dut.write_text("* dut\n")
        self.results = [_pr(0.5)]
        self.summaries = summarize(_summ_tb({}), self.results)

    def write(self, rid):
        return report_mod.write_record(
            self.tb, self.results, self.summaries, _record_context(rid), self.dut
        )

    def test_reserved_identity_writes_full_bundle_once(self):
        r = self.reserve()
        path = self.write(r.rid)
        self.assertEqual(path, self.exp / "records" / f"{r.rid}.md")
        self.assertEqual(sorted(report_mod.occupied_members(self.exp, r.rid)),
                         ["json", "logs", "record", "snapshot"])
        before = _tree(self.exp)
        with self.assertRaises(report_mod.EvidenceCollision):
            self.write(r.rid)
        self.assertEqual(_tree(self.exp), before)

    def test_any_existing_member_refuses_before_writing_anything(self):
        for member in ("record", "json", "snapshot"):
            with self.subTest(member=member):
                rid = f"20261009-120000-abc1234-{member[:3]}000"
                path = report_mod.bundle_paths(self.exp, rid)[member]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("pre-existing evidence\n")
                before = _tree(self.exp)
                with self.assertRaises(report_mod.EvidenceCollision):
                    self.write(rid)
                self.assertEqual(_tree(self.exp), before)

    def test_full_existing_bundle_stays_byte_identical(self):
        rid = "20260910-233015-8148438"
        before = self.plant_bundle(rid)
        with self.assertRaises(report_mod.EvidenceCollision):
            self.write(rid)
        self.assertEqual(_tree(self.exp), before)


class ExclusiveLogTest(RunPointWarningsTest):
    def test_existing_log_is_refused_before_simulation(self):
        log_dir = self.workdir / "corners" / "rid"
        log_dir.mkdir(parents=True)
        log = log_dir / f"{self.point.corner_id}.log"
        log.write_text("committed raw log\n")
        with mock.patch("harness.runner.compose_deck", return_value="* stub\n"), \
             mock.patch("harness.runner.subprocess.run") as run:
            with self.assertRaises(FileExistsError):
                run_point(self.tb, self.pdk, self.dut, self.point, self.workdir / "scratch",
                          log_dir=log_dir, exclusive_logs=True)
            run.assert_not_called()
        self.assertEqual(log.read_text(), "committed raw log\n")
        self.assertFalse((self.workdir / "scratch" / f"{self.point.corner_id}.spice").exists())

    def test_exclusive_log_written_for_fresh_identity(self):
        log_dir = self.workdir / "corners" / "rid"
        with mock.patch("harness.runner.compose_deck", return_value="* stub\n"), \
             mock.patch("harness.runner.subprocess.run",
                        return_value=_fake_completed("m_vos_mv = 1.0\n")):
            results = run_grid(self.tb, self.pdk, self.dut, [self.point],
                               self.workdir / "scratch", log_dir=log_dir,
                               exclusive_logs=True)
        self.assertEqual(results[0].status, "ok")
        self.assertIn("m_vos_mv", (log_dir / results[0].log).read_text())


if __name__ == "__main__":
    unittest.main()

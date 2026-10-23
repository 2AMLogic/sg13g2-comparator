"""Append-only preservation of derived report pairs (issues #237, #302).

Only analysis/rendering is mocked; every test drives the public CLI entry
points against a temporary directory. No simulator, no network.
"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_clock_supply_sensitivity as clock
import run_decision_cm_band as decision
import run_offset_cm_band as offset
from kltsim import artifacts
from kltsim import cli
from kltsim import clocksupply as cs
from kltsim import cmband
from kltsim import cmdecision
from kltsim import clocksupply_report as rep
from kltsim import declared_n
from kltsim import grade as grade_mod
from kltsim import ibsweep
from kltsim import noise_full

SIDE = {"grade": ("grading.json", "grading.md"),
        "noise": ("noise_full.json", "noise_full.md"),
        "clock": ("comparison.json", "comparison.md"),
        "offset": ("comparison.json", "comparison.md"),
        "decision": ("comparison.json", "comparison.md"),
        "ibsweep": ("ibsweep.json", "ibsweep.md")}
SERIES_RUNNERS = {"clock": clock, "offset": offset, "decision": decision}


class Harness(unittest.TestCase):
    """Runs one public command with mocked analysis whose output is mutable."""

    kind = ""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.campaigns = self.root / "campaigns"
        self.src = self.campaigns / "C1"
        self.src.mkdir(parents=True)
        self.result = {"campaign": "C1", "series": "C1", "v": 1}
        self.md = "# report v1\n"
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(cli, "CAMPAIGNS_DIR", self.campaigns))
        stack.enter_context(mock.patch.object(cs, "SERIES_DIR", self.campaigns))
        stack.enter_context(mock.patch.object(declared_n, "grade_campaign", lambda d, n=None: dict(self.result)))
        stack.enter_context(mock.patch.object(grade_mod, "render_markdown", lambda r: self.md))
        stack.enter_context(mock.patch.object(grade_mod, "render_summary", lambda r: "summary"))
        stack.enter_context(mock.patch.object(noise_full, "analyse", lambda d: dict(self.result)))
        stack.enter_context(mock.patch.object(noise_full, "render_markdown", lambda r: self.md))
        stack.enter_context(mock.patch.object(rep, "compare_series", lambda d: dict(self.result)))
        stack.enter_context(mock.patch.object(rep, "render_markdown", lambda r: self.md))
        for mod in (cmband, cmdecision):
            stack.enter_context(mock.patch.object(mod, "SERIES_DIR", self.campaigns))
            stack.enter_context(mock.patch.object(
                mod, "compare_series", lambda d, **kw: {**self.result, "conditions": {}}))
            stack.enter_context(mock.patch.object(mod, "render_markdown", lambda r: self.md))
        stack.enter_context(mock.patch.object(
            ibsweep, "sweep", lambda d: {**self.result, "points": [1]}))
        stack.enter_context(mock.patch.object(ibsweep, "render_markdown", lambda r: self.md))

    def argv(self, *extra):
        return {"grade": ["grade", "--campaign", "C1"], "noise": ["noise-full", "--campaign", "C1"],
                "ibsweep": ["ibsweep", "--campaign", "C1"]}[self.kind] + list(extra)

    def run_cmd(self, *extra):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            if self.kind in SERIES_RUNNERS:
                rc = SERIES_RUNNERS[self.kind].main(["compare", "--series", "C1", *extra])
            else:
                rc = cli.main(self.argv(*extra))
        return rc, out.getvalue(), err.getvalue()

    @property
    def names(self):
        return SIDE[self.kind]

    def snapshot(self, d):
        return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(d.iterdir())}


class _Cases:
    def test_fresh_creates_pair(self):
        rc, _, _ = self.run_cmd()
        self.assertEqual(rc, 0)
        self.assertEqual({p.name for p in self.src.iterdir()}, set(self.names))

    def test_identical_rerun_preserves_bytes_and_mtime(self):
        self.run_cmd()
        for p in self.src.iterdir():
            os.utime(p, ns=(1_000_000_001, 1_000_000_002))
        before = self.snapshot(self.src)
        rc, _, _ = self.run_cmd()
        self.assertEqual(rc, 0)
        self.assertEqual(self.snapshot(self.src), before)

    def test_changed_json_refuses_without_writes(self):
        self.run_cmd()
        before = self.snapshot(self.src)
        self.result = {**self.result, "v": 2}
        rc, _, err = self.run_cmd()
        self.assertEqual(rc, 1)
        self.assertIn(self.names[0], err)
        self.assertEqual(self.snapshot(self.src), before)

    def test_changed_markdown_only_refuses_without_writes(self):
        self.run_cmd()
        before = self.snapshot(self.src)
        self.md = "# report v2\n"
        rc, _, _ = self.run_cmd()
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(self.src), before)

    def test_second_member_conflict_does_not_create_absent_first(self):
        (self.src / self.names[1]).write_text("old\n")
        rc, _, err = self.run_cmd()
        self.assertEqual(rc, 1)
        self.assertEqual([p.name for p in self.src.iterdir()], [self.names[1]])
        self.assertEqual((self.src / self.names[1]).read_text(), "old\n")
        self.assertIn(self.names[1], err)

    def test_matching_partial_pair_is_completed(self):
        self.run_cmd()
        (self.src / self.names[1]).unlink()
        kept = self.snapshot(self.src)
        rc, _, _ = self.run_cmd()
        self.assertEqual(rc, 0)
        self.assertEqual(self.snapshot(self.src)[self.names[0]], kept[self.names[0]])
        self.assertEqual((self.src / self.names[1]).read_text(), self.md)

    def test_symlink_member_refused(self):
        target = self.root / "elsewhere"
        target.write_text("x")
        (self.src / self.names[0]).symlink_to(target)
        rc, _, _ = self.run_cmd()
        self.assertEqual(rc, 1)
        self.assertEqual(target.read_text(), "x")
        self.assertFalse((self.src / self.names[1]).exists())

    def test_directory_member_refused(self):
        (self.src / self.names[1]).mkdir()
        rc, _, _ = self.run_cmd()
        self.assertEqual(rc, 1)
        self.assertFalse((self.src / self.names[0]).exists())

    def test_check_mode_never_writes(self):
        rc, _, err = self.run_cmd("--check")
        self.assertEqual(rc, 1)
        self.assertIn("missing", err)
        self.assertEqual(list(self.src.iterdir()), [])
        rc, _, _ = self.run_cmd("--check", "--report-dir", str(self.root / "nope"))
        self.assertEqual(rc, 1)
        self.assertFalse((self.root / "nope").exists())
        self.run_cmd()
        before = self.snapshot(self.src)
        rc, out, _ = self.run_cmd("--check")
        self.assertEqual((rc, "check ok" in out), (0, True))
        self.md = "# stale\n"
        rc, _, err = self.run_cmd("--check")
        self.assertEqual(rc, 1)
        self.assertIn("differs", err)
        self.assertEqual(self.snapshot(self.src), before)

    def test_check_flags_unsafe_member(self):
        (self.src / self.names[0]).symlink_to(self.root)
        rc, _, err = self.run_cmd("--check")
        self.assertEqual(rc, 1)
        self.assertIn("not a regular file", err)

    def test_report_dir_publishes_changed_analysis_and_keeps_original(self):
        self.run_cmd()
        before = self.snapshot(self.src)
        self.result = {**self.result, "v": 2}
        new = self.root / "new-ns"
        rc, _, _ = self.run_cmd("--report-dir", str(new))
        self.assertEqual(rc, 0)
        self.assertEqual(self.snapshot(self.src), before)
        self.assertEqual({p.name for p in new.iterdir()}, set(self.names))
        self.assertIn("C1", (new / self.names[0]).read_text())
        if self.kind != "noise":
            self.assertIn("source_", (new / self.names[0]).read_text())
            self.assertIn("original evidence", (new / self.names[1]).read_text())

    def test_report_dir_is_a_file_refused(self):
        f = self.root / "afile"
        f.write_text("x")
        rc, _, _ = self.run_cmd("--report-dir", str(f))
        self.assertEqual(rc, 1)
        self.assertEqual(f.read_text(), "x")


class GradeTest(_Cases, Harness):
    kind = "grade"


class NoiseFullTest(_Cases, Harness):
    kind = "noise"

    def test_compact_json_serialization_kept(self):
        self.run_cmd()
        self.assertEqual((self.src / "noise_full.json").read_text(),
                         '{"campaign":"C1","series":"C1","v":1}\n')


class ClockTest(_Cases, Harness):
    kind = "clock"


class OffsetCmBandTest(_Cases, Harness):
    kind = "offset"


class DecisionCmBandTest(_Cases, Harness):
    kind = "decision"


class IbsweepTest(_Cases, Harness):
    kind = "ibsweep"


class WriterTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)

    def test_concurrent_identical_winner_accepted_and_different_rejected(self):
        a, b = self.d / "a", self.d / "b"
        real_open = open

        def racing(path, mode="r", *args, **kw):
            if Path(path) == b and mode == "xb":
                with real_open(path, "wb") as fh:
                    fh.write(winner)
                raise FileExistsError(path)
            return real_open(path, mode, *args, **kw)

        winner = b"2"
        with mock.patch("builtins.open", racing):
            artifacts.commit([(a, b"1"), (b, b"2")])
        self.assertEqual(b.read_bytes(), b"2")
        b.unlink()
        winner = b"other"
        with mock.patch("builtins.open", racing):
            with self.assertRaises(artifacts.ArtifactConflict) as cm:
                artifacts.commit([(b, b"2")])
        self.assertTrue(cm.exception.concurrent)
        self.assertEqual(b.read_bytes(), b"other")

    def test_duplicate_destination_with_different_bytes_rejected(self):
        p = self.d / "x"
        with self.assertRaises(artifacts.ArtifactConflict):
            artifacts.commit([(p, b"1"), (p, b"2")])
        self.assertFalse(p.exists())

    def test_check_does_not_create_parent_directory(self):
        p = self.d / "sub" / "x"
        self.assertEqual(len(artifacts.check([(p, b"1")])), 1)
        self.assertFalse(p.parent.exists())


if __name__ == "__main__":
    unittest.main()

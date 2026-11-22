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
    # Issue #423: whether a redirected publish cites its source in the JSON and
    # markdown. `noise` is the one deliberate exception — it must NOT cite.
    cites_source = True

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
        json_text = (new / self.names[0]).read_text()
        md_text = (new / self.names[1]).read_text()
        if self.cites_source:
            self.assertIn("source_", json_text)
            self.assertIn("original evidence", md_text)
        else:
            self.assertNotIn("source_", json_text)
            self.assertNotIn("original evidence", md_text)

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
    # Issue #423: noise_full deliberately publishes without citing its source
    # campaign; changing that is a sim/README.md decision-record question.
    cites_source = False

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

    def test_commit_refuses_non_directory_destination_dir(self):
        dest = self.d / "camp"
        dest.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(artifacts.ArtifactConflict) as caught:
            artifacts.commit([(dest / "a.spice", b"body")])
        self.assertIn(f"{dest}: exists and is not a directory", str(caught.exception))
        self.assertEqual(dest.read_text(), "not a directory")
        self.assertEqual([p.name for p in self.d.iterdir()], ["camp"])

    def test_commit_refuses_symlinked_destination_dir(self):
        real = self.d / "real"
        real.mkdir()
        dest = self.d / "camp"
        dest.symlink_to(real, target_is_directory=True)
        with self.assertRaises(artifacts.ArtifactConflict) as caught:
            artifacts.commit([(dest / "a.spice", b"body")])
        self.assertIn(f"{dest}: exists and is not a directory", str(caught.exception))
        self.assertEqual(list(real.iterdir()), [])

    def test_commit_refuses_non_directory_ancestor(self):
        for kind in ("file", "dangling-symlink", "symlink-to-file"):
            with self.subTest(kind=kind):
                root = self.d / kind.replace("-", "_")
                root.mkdir()
                ancestor = root / "camp"
                if kind == "file":
                    ancestor.write_text("x", encoding="utf-8")
                elif kind == "dangling-symlink":
                    ancestor.symlink_to(root / "gone")
                else:
                    (root / "afile").write_text("x", encoding="utf-8")
                    ancestor.symlink_to(root / "afile")
                with self.assertRaises(artifacts.ArtifactConflict) as caught:
                    artifacts.commit([(ancestor / "bench" / "a.spice", b"body")])
                self.assertIn(f"{ancestor}: exists and is not a directory",
                              str(caught.exception))
                self.assertFalse((root / "gone").exists())
                leftovers = {"file": ["camp"], "dangling-symlink": ["camp"],
                             "symlink-to-file": ["afile", "camp"]}[kind]
                self.assertEqual(sorted(p.name for p in root.iterdir()), leftovers)

    def test_commit_follows_symlinked_ancestor_to_directory(self):
        real = self.d / "real"
        real.mkdir()
        link = self.d / "link"
        link.symlink_to(real, target_is_directory=True)
        created = artifacts.commit([(link / "camp" / "a.spice", b"body")])
        self.assertEqual(created, [link / "camp" / "a.spice"])
        self.assertEqual((real / "camp" / "a.spice").read_bytes(), b"body")

    def test_commit_multi_dir_batch_rejects_whole_set(self):
        bad = self.d / "bad"
        bad.write_text("x", encoding="utf-8")
        good = self.d / "good"
        with self.assertRaises(artifacts.ArtifactConflict) as caught:
            artifacts.commit([(bad / "a", b"1"), (good / "b", b"2")])
        self.assertIn(f"{bad}: exists and is not a directory", str(caught.exception))
        self.assertFalse(good.exists())

    def test_commit_reports_shared_bad_ancestor_once(self):
        ancestor = self.d / "camp"
        ancestor.write_text("x", encoding="utf-8")
        with self.assertRaises(artifacts.ArtifactConflict) as caught:
            artifacts.commit([(ancestor / "one" / "a", b"1"), (ancestor / "two" / "b", b"2")])
        self.assertEqual(
            str(caught.exception).count(f"{ancestor}: exists and is not a directory"), 1)

    def test_check_reports_directory_conflict_without_spurious_missing(self):
        bad = self.d / "bad"
        bad.write_text("x", encoding="utf-8")
        good = self.d / "good"
        good.mkdir()
        problems = artifacts.check([(bad / "a", b"1"), (good / "b", b"2")])
        self.assertEqual(problems,
                         [f"{bad}: exists and is not a directory", f"{good / 'b'}: missing"])
        self.assertFalse((good / "b").exists())

    def test_require_dir_short_circuit_preserved(self):
        f = self.d / "afile"
        f.write_text("x", encoding="utf-8")
        self.assertEqual(artifacts.check([], require_dir=f),
                         [f"{f}: exists and is not a directory"])
        real = self.d / "real"
        real.mkdir()
        link = self.d / "link"
        link.symlink_to(real, target_is_directory=True)
        self.assertEqual(artifacts.check([], require_dir=link),
                         [f"{link}: exists and is not a directory"])
        with self.assertRaises(artifacts.ArtifactConflict) as caught:
            artifacts.commit([(self.d / "other" / "a", b"1")], require_dir=f)
        self.assertEqual(str(caught.exception), f"{f}: exists and is not a directory")
        self.assertFalse((self.d / "other").exists())


if __name__ == "__main__":
    unittest.main()

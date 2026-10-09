"""Issue #95: campaign inputs are append-only evidence (stdlib only)."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kltsim import build, cli
from kltsim.benches import BENCHES, KICKBACK, REGENERATION


def _plan(benches, out_dir, **kw):
    files = []
    for bench in benches:
        files += build.plan_bench_inputs(bench, out_dir, target="batch", **kw)[2]
    return files


def _snapshot(directory: Path) -> dict:
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(directory.iterdir())}


class CommitInputsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name) / "campaign"

    def test_fresh_build_creates_everything(self):
        files = _plan([REGENERATION], self.out)
        created = build.commit_inputs(files)
        self.assertEqual(set(created), {p for p, _ in files})
        for path, data in files:
            self.assertEqual(path.read_bytes(), data)

    def test_identical_rebuild_touches_nothing(self):
        build.commit_inputs(_plan([REGENERATION], self.out))
        # stand-ins for envelopes / invocation records produced by a submit
        (self.out / "regeneration.envelope.json").write_text("{}\n")
        (self.out / "regeneration.invocation.json").write_text("{}\n")
        for p in self.out.iterdir():
            os.utime(p, ns=(10**9, 10**9))
        before = _snapshot(self.out)
        created = build.commit_inputs(_plan([REGENERATION], self.out))
        self.assertEqual(created, [])
        self.assertEqual(_snapshot(self.out), before)

    def test_changed_body_rejected_without_writes(self):
        build.commit_inputs(_plan([REGENERATION], self.out))
        before = _snapshot(self.out)
        with self.assertRaises(build.BuildError) as ctx:
            build.commit_inputs(_plan([REGENERATION], self.out, param_overrides={"dut_ib": 5e-6}))
        message = str(ctx.exception)
        self.assertIn("regeneration.body.spice", message)
        self.assertIn("NEW campaign ID", message)
        self.assertEqual(_snapshot(self.out), before)

    def test_changed_request_rejected_without_writes(self):
        build.commit_inputs(_plan([REGENERATION], self.out))
        before = _snapshot(self.out)
        changed = dataclasses.replace(REGENERATION, timeout_s=REGENERATION.timeout_s + 1)
        with self.assertRaises(build.BuildError) as ctx:
            build.commit_inputs(_plan([changed], self.out))
        self.assertIn(".request.json", str(ctx.exception))
        self.assertNotIn("regeneration.body.spice", str(ctx.exception))
        self.assertEqual(_snapshot(self.out), before)

    def test_conflict_after_new_bench_changes_nothing(self):
        build.commit_inputs(_plan([REGENERATION], self.out))
        before = _snapshot(self.out)
        changed = dataclasses.replace(REGENERATION, timeout_s=REGENERATION.timeout_s + 1)
        # KICKBACK is new and precedes the conflicting bench in selection order
        with self.assertRaises(build.BuildError):
            build.commit_inputs(_plan([KICKBACK, changed], self.out))
        self.assertEqual(_snapshot(self.out), before)
        self.assertFalse((self.out / "kickback.body.spice").exists())

    def test_adding_independent_bench_keeps_existing_files(self):
        build.commit_inputs(_plan([REGENERATION], self.out))
        before = _snapshot(self.out)
        created = build.commit_inputs(_plan([REGENERATION, KICKBACK], self.out))
        self.assertTrue(created)
        self.assertTrue((self.out / "kickback.body.spice").is_file())
        after = _snapshot(self.out)
        for name, state in before.items():
            self.assertEqual(after[name], state)

    def test_exclusive_creation_never_overwrites_a_racing_writer(self):
        files = _plan([REGENERATION], self.out)
        target = files[0][0]
        real_exists = Path.exists

        def lying_exists(path):  # preflight sees "absent", file appears after
            if path == target:
                return False
            return real_exists(path)

        self.out.mkdir(parents=True)
        target.write_bytes(b"someone else's bytes\n")
        with mock.patch.object(Path, "exists", lying_exists):
            with self.assertRaises(build.BuildError):
                build.commit_inputs(files)
        self.assertEqual(target.read_bytes(), b"someone else's bytes\n")

    def test_smoke_write_keeps_overwrite_contract(self):
        build.write_bench_inputs(REGENERATION, self.out, target="batch")
        build.write_bench_inputs(
            REGENERATION, self.out, target="batch", param_overrides={"dut_ib": 5e-6})
        self.assertIn("dut_ib=5e-06", (self.out / "regeneration.body.spice").read_text())


class CmdBuildTests(unittest.TestCase):
    def run_build(self, root: Path, benches, dut_param=None):
        args = argparse.Namespace(
            campaign="c1", bench=benches, dut_param=dut_param, bias_probes=False)
        err = io.StringIO()
        with mock.patch.object(cli, "CAMPAIGNS_DIR", root), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = cli.cmd_build(args)
        return code, err.getvalue()

    def test_cli_rejects_late_conflict_and_recovers_with_new_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_build(root, ["regeneration"])[0], 0)
            before = _snapshot(root / "c1")
            self.assertEqual(self.run_build(root, ["regeneration"])[0], 0)
            self.assertEqual(_snapshot(root / "c1"), before)
            code, err = self.run_build(root, ["kickback", "regeneration"], ["dut_ib=5e-6"])
            self.assertEqual(code, 1)
            self.assertIn("NEW campaign ID", err)
            self.assertEqual(_snapshot(root / "c1"), before)
            self.assertTrue(set(BENCHES) >= {"regeneration", "kickback"})


if __name__ == "__main__":
    unittest.main()

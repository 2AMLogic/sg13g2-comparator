"""Regression tests for scripts/check_evidence_size.py (issues #132, #323).

Synthetic throwaway git repositories; stdlib only. The MiB unit is shrunk to
1000 bytes inside the tests so exact-boundary cases stay tiny.
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "check_evidence_size", ROOT / "scripts" / "check_evidence_size.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}
UNIT_A = "sim/a/campaigns/c1"
UNIT_R = "sim/a/records/r1.json"
NEW = "sim/a/campaigns/new"
RETIRING = "spec/decision-records/evidence-size/323-retire-incremental-evidence-size-raises.md"


class Base(unittest.TestCase):
    def setUp(self):
        self._mib = chk.MIB
        chk.MIB = 1000
        self.addCleanup(setattr, chk, "MIB", self._mib)
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)
        self.git("init", "-q", "-b", "main")
        # baseline: two units of 3000 and 500 bytes + 500 bytes elsewhere in sim
        self.write(UNIT_A + "/data.bin", "x" * 3000)
        self.write(UNIT_R, "y" * 500)
        self.write("sim/tool.py", "z" * 500)
        self.write("README.md", "r" * 77)
        self.base = self.commit("base")
        m = chk.measure(str(self.root), self.base)
        self.assertEqual(m["sim_bytes"], 4000)
        self.budget = chk.build_budget(m, self.base)
        # allowance = ceil(10% * 4000 / 1000) * 1000 = 1000
        self.assertEqual(self.budget["allowance"]["bytes"], 1000)
        self.assertEqual(self.budget["total_ceiling_bytes"], 5000)
        self.write_budget()

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], env=ENV, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE
                              ).stdout.decode().strip()

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)

    def write_budget(self):
        self.write("sim/evidence-size-budget.json", json.dumps(self.budget, indent=2))

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def run_main(self, tree="HEAD", *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["--repo", str(self.root), "--tree", tree, *extra])
        return rc, out.getvalue(), err.getvalue()

class Boundaries(Base):
    def test_baseline_tree_passes(self):
        self.commit("budget")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)

    def test_grandfathered_unit_at_baseline_ok_one_byte_over_fails(self):
        self.commit("budget")
        self.write(UNIT_A + "/more.bin", "")  # empty add: still baseline bytes
        self.commit("zero")
        self.assertEqual(self.run_main()[0], 0)
        self.write(UNIT_A + "/more.bin", "m")
        self.commit("grow")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn(f"{UNIT_A}: 3001 B measured > grandfathered baseline 3000 B "
                      "(over by 1 B)", err)
        self.assertIn("no exception route", err)

    def test_new_unit_exact_ceiling_ok_one_over_fails(self):
        self.write(NEW + "/d.bin", "n" * 1000)
        self.commit("new-exact")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.write(NEW + "/e.bin", "n")
        self.commit("new-over")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn(f"{NEW}: 1001 B measured > new-unit ceiling 1000 B", err)

    def test_aggregate_exact_ok_and_overflow_fails_with_small_units(self):
        self.commit("budget")
        m = chk.measure(str(self.root), "HEAD")
        room = self.budget["total_ceiling_bytes"] - m["evidence_bytes"]
        self.assertEqual(room, 1500)
        self.write("sim/a/records/fill1.json", "q" * 1000)
        self.write("sim/a/records/fill2.json", "q" * (room - 1000))
        self.commit("fill")
        self.assertEqual(self.run_main()[0], 0)
        self.write("sim/a/records/fill3.json", "q")
        self.commit("overflow")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn(f"evidence: {self.budget['total_ceiling_bytes'] + 1} B measured > "
                      f"total ceiling {self.budget['total_ceiling_bytes']} B", err)

    def test_code_and_docs_under_sim_never_count(self):
        self.commit("budget")
        self.write("sim/harness/big.py", "c" * 100000)
        self.write("sim/README.md", "d" * 100000)
        self.write("sim/a/testbench/bench.spice", "t" * 100000)
        self.commit("code")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)

    def test_many_small_new_units_overflow_aggregate(self):
        self.commit("budget")
        for i in range(6):
            self.write(f"sim/a/records/n{i}.json", "k" * 900)
        self.commit("many")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("total ceiling", err)
        self.assertNotIn("new-unit ceiling", err)  # each unit alone is within limits

    def test_deterministic_output(self):
        self.write(NEW + "/d.bin", "n" * 2000)
        self.commit("over")
        self.assertEqual(self.run_main(), self.run_main())
        self.assertEqual(self.run_main("HEAD", "--quiet"), self.run_main("HEAD", "--quiet"))

    def test_report_names_totals_and_units(self):
        self.commit("budget")
        rc, out, _ = self.run_main()
        self.assertIn("repo: ", out)
        self.assertIn(f"  {UNIT_A}: 3000 B [baseline]", out)
        self.assertIn(f"  {UNIT_R}: 500 B [baseline]", out)


class Measuring(Base):
    def test_missing_or_non_numeric_size_fails_closed(self):
        with self.assertRaises(chk.MeasureError):
            chk.parse_ls_tree(b"100644 blob " + b"a" * 40 + b"       -\tsim/x\0")
        with self.assertRaises(chk.MeasureError):
            chk.parse_ls_tree(b"100644 blob " + b"a" * 40 + b"     12x\tsim/x\0")
        with self.assertRaises(chk.MeasureError):
            chk.parse_ls_tree(b"garbage\0")
        self.assertEqual(chk.parse_ls_tree(
            b"160000 commit " + b"a" * 40 + b"       -\tsub\0"), [])

    def test_unavailable_tree_is_exit_2_not_success(self):
        rc, _, err = self.run_main("no-such-rev")
        self.assertEqual(rc, 2)
        self.assertIn("ERROR (measure)", err)

    def test_missing_budget_file_fails(self):
        (self.root / "sim/evidence-size-budget.json").unlink()
        self.commit("nobudget")
        self.assertEqual(self.run_main()[0], 1)

    def test_counts_blobs_not_working_tree(self):
        self.commit("budget")
        (self.root / UNIT_A / "data.bin").write_text("x" * 99999)  # uncommitted
        self.assertEqual(self.run_main()[0], 0)

    def test_allowance_rounds_up_to_next_mib_exactly(self):
        chk.MIB = 1024 * 1024
        self.assertEqual(chk.allowance_bytes(489675829), 47 * 1024 * 1024)
        self.assertEqual(chk.allowance_bytes(10 * 1024 * 1024), 1024 * 1024)  # exact
        self.assertEqual(chk.allowance_bytes(10 * 1024 * 1024 + 1), 2 * 1024 * 1024)

    def test_budget_derivation_is_validated(self):
        for mutate in (
            lambda b: b["allowance"].update(percent=20),
            lambda b: b["allowance"].update(bytes=2000, mib=2),
            lambda b: b.update(total_ceiling_bytes=b["total_ceiling_bytes"] + 1),
            lambda b: b.update(new_unit_ceiling_bytes=1),
            lambda b: b["baseline"].update(sim_bytes=1),
            lambda b: b.update(extra=1),
            lambda b: b["units"].update({"sim/a/campaigns": 5}),
        ):
            with self.subTest(m=mutate):
                self.setUp()
                mutate(self.budget)
                self.write_budget()
                self.commit("bad")
                rc, _, err = self.run_main()
                self.assertEqual(rc, 1, err)
                self.assertIn("FAIL (budget)", err)


class Suspended(Base):
    """Issue #312: a `suspended` block makes the size check report-only."""

    def suspend(self):
        self.budget["suspended"] = {
            "by": "operator", "date": "2026-10-20", "until": "2AMLogic/2am#5553"}
        self.write_budget()

    def test_breach_is_reported_but_exits_0_while_suspended(self):
        self.suspend()
        self.write(NEW + "/big.bin", "n" * 5000)  # over every ceiling
        self.commit("big")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.assertIn("SUSPENDED (report-only)", out)
        self.assertIn("2AMLogic/2am#5553", out)
        self.assertIn(f"would-fail (not enforced): {NEW}: 5000 B measured", out)
        self.assertIn("sim/ ", out)  # measured size line still printed
        self.assertEqual(err, "")

    def test_same_breach_fails_without_suspension(self):
        self.write(NEW + "/big.bin", "n" * 5000)
        self.commit("big")
        self.assertEqual(self.run_main()[0], 1)

    def test_suspended_still_exits_2_on_measurement_error(self):
        self.suspend()
        self.commit("budget")
        self.assertEqual(self.run_main("no-such-rev")[0], 2)

    def test_suspended_still_validates_budget(self):
        self.suspend()
        self.budget["allowance"]["percent"] = 20
        self.write_budget()
        self.commit("bad")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1, err)
        self.assertIn("FAIL (budget)", err)

    def test_malformed_suspended_block_rejected(self):
        for bad in ({"by": "operator"}, "yes", {"by": "", "date": "2026-10-20", "until": "x"},
                    {"by": "o", "date": "today", "until": "x"},
                    {"by": "o", "date": "2026-10-20", "until": "x", "more": 1}):
            with self.subTest(bad=bad):
                self.setUp()
                self.budget["suspended"] = bad
                self.write_budget()
                self.commit("bad")
                rc, _, err = self.run_main()
                self.assertEqual(rc, 1, err)
                self.assertIn("FAIL (budget)", err)


class PartialClone(Base):
    """A blob-filtered partial clone must fail closed fast, never lazy-fetch.

    This is the shape actions/checkout produces whenever its `sparse-checkout:`
    input is set (it adds --filter=blob:none); CI run 38029844566 hung there.
    """

    def setUp(self):
        super().setUp()
        self.commit("budget")
        self.blob = self.git("rev-parse", f"HEAD:{UNIT_A}/data.bin")

    def clone(self, *opts):
        dst = Path(self._td.name + "-clone")
        self.addCleanup(subprocess.run, ["rm", "-rf", str(dst)])
        subprocess.run(
            ["git", "clone", "-q", "--no-checkout", *opts,
             "-u", "git -c uploadpack.allowFilter=true upload-pack",
             f"file://{self.root}", str(dst)],
            env=ENV, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return dst

    def has_blob(self, repo):
        return subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", self.blob],
            env={**ENV, "GIT_NO_LAZY_FETCH": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0

    def run_in(self, repo):
        out, err = io.StringIO(), io.StringIO()
        t0 = time.monotonic()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["--repo", str(repo), "--tree", "origin/main"])
        return rc, err.getvalue(), time.monotonic() - t0

    def test_blob_none_clone_exits_2_quickly_without_fetching(self):
        dst = self.clone("--filter=blob:none")
        self.assertFalse(self.has_blob(dst))
        rc, err, dt = self.run_in(dst)
        self.assertEqual(rc, 2, err)
        self.assertIn("partial clone", err)
        self.assertLess(dt, 10)
        self.assertFalse(self.has_blob(dst), "checker lazily fetched a blob")

    def test_no_lazy_fetch_even_if_config_guard_is_bypassed(self):
        dst = self.clone("--filter=blob:none")
        orig = chk.assert_complete_repo
        chk.assert_complete_repo = lambda repo: None
        self.addCleanup(setattr, chk, "assert_complete_repo", orig)
        rc, err, dt = self.run_in(dst)
        self.assertEqual(rc, 2, err)
        self.assertIn("ERROR (measure)", err)
        self.assertFalse(self.has_blob(dst), "GIT_NO_LAZY_FETCH not honoured")

    def test_promisor_config_alone_is_refused(self):
        for key, val in (("remote.origin.promisor", "true"),
                         ("extensions.partialClone", "origin")):
            with self.subTest(key=key):
                self.git("config", key, val)
                rc, _, err = self.run_main()
                self.assertEqual(rc, 2, err)
                self.assertIn("partial clone", err)
                self.git("config", "--unset", key)
        self.git("config", "remote.origin.promisor", "false")
        self.assertEqual(self.run_main()[0], 0)

    def test_complete_and_shallow_clones_measure_exactly(self):
        for opts in ((), ("--depth=1",)):
            with self.subTest(opts=opts):
                dst = self.clone(*opts)
                rc, err, _ = self.run_in(dst)
                self.assertEqual(rc, 0, err)
                self.assertTrue(self.has_blob(dst))
                subprocess.run(["rm", "-rf", str(dst)], check=True)


class Retired(Base):
    """Issue #323: per-PR evidence-size exceptions no longer exist."""

    def fails(self, needle):
        self.commit("x")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1, err)
        self.assertIn(needle, err)

    def test_budget_exception_entry_rejected(self):
        self.budget["exceptions"].append({"path": "sim", "additional_bytes": 5})
        self.write_budget()
        self.fails("exceptions must be empty")

    def test_exception_file_rejected(self):
        self.write("sim/evidence-size-exceptions/1-x.json", "{}")
        self.fails("evidence-size-exceptions/ must not exist")

    def test_new_exception_record_rejected(self):
        self.write("spec/decision-records/0100-x-evidence-size-exception.md",
                   "- **Superseded by**: none\n")
        self.fails("0100-x-evidence-size-exception.md")

    def test_new_subdir_exception_record_rejected(self):
        self.write("spec/decision-records/evidence-size/400-evidence-size-exception.md",
                   "# x\n")
        self.fails("400-evidence-size-exception.md")

    def test_superseded_record_accepted(self):
        self.write("spec/decision-records/0005-evidence-size-exception.md",
                   "- **Superseded by**: [r](evidence-size/323-retire-incremental-"
                   "evidence-size-raises.md)\n")
        self.commit("x")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 0, err)


class ManifestOnly(Base):
    """Issue #318: after the re-baseline new evidence is a manifest plus a
    summary, so ordinary growth needs no exception (the #276 case)."""

    def test_source_growth_under_sim_passes_without_exception(self):
        self.commit("budget")
        self.assertEqual(self.budget["exceptions"], [])
        self.write("sim/harness/new_module.py", "s" * 300)
        self.commit("source")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)

    def test_manifest_and_summary_run_passes_without_exception(self):
        self.commit("budget")
        self.write("manifests/artifacts/a-r2.manifest.json", "m" * 2000)  # outside sim/
        self.write("sim/a/records/r2.md", "# summary\n")
        self.commit("stored run")
        rc, out, err = self.run_main()
        self.assertEqual(rc, 0, err)
        self.assertIn("sim/a/records/r2.md", out)

    def test_new_unit_over_ceiling_fails_without_exception(self):
        self.commit("budget")
        self.write(NEW + "/blob.bin", "b" * 1001)
        self.commit("committed blob")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn(f"{NEW}: 1001 B measured > new-unit ceiling 1000 B", err)


class RepoBudget(unittest.TestCase):
    def test_committed_budget_is_valid_and_matches_issue_baseline(self):
        # Issue #318: re-baselined at main 4c0db1c86 with exceptions cleared
        # (spec/decision-records/evidence-size/318-manifest-store-rebaseline.md).
        b = json.loads((ROOT / "sim/evidence-size-budget.json").read_text())
        self.assertEqual(b["baseline"]["commit"], "4c0db1c86b9318a5f4af922f6750d8d7e3441adb")
        self.assertEqual(b["allowance"]["derivation"],
                         "ceil(10% x 567379629 B / 1048576 B/MiB) = 55 MiB")
        self.assertEqual(b["baseline"]["sim_bytes"], 567379629)
        self.assertEqual(b["baseline"]["sim_blobs"], 114687)
        self.assertEqual(b["total_ceiling_bytes"], 567379629 + 55 * 1048576)
        self.assertEqual(b["exceptions"], [])
        self.assertIsNone(chk.validate_budget(str(ROOT), "HEAD", b))

    def test_committed_budget_is_enforced(self):
        b = json.loads((ROOT / "sim/evidence-size-budget.json").read_text())
        self.assertNotIn("suspended", b)
        self.assertTrue((ROOT / "spec/decision-records/evidence-size/"
                         "318-manifest-store-rebaseline.md").is_file())
        self.assertTrue((ROOT / RETIRING).is_file())

    def test_head_within_committed_budget(self):
        rc = chk.main(["--repo", str(ROOT), "--tree", "HEAD", "--quiet"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

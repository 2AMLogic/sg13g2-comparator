"""Regression tests for scripts/check_evidence_size.py (issue #132).

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
REC = "spec/decision-records/0100-size.md"


class Base(unittest.TestCase):
    def setUp(self):
        self._mib = chk.MIB
        chk.MIB = 1000
        self.addCleanup(setattr, chk, "MIB", self._mib)
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)
        self.git("init", "-q", "-b", "main")
        self.rec_items = []
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

    def add_exception(self, path, extra, record_path=None, rec_json=None, reason="why"):
        item = rec_json if rec_json is not None else {
            "kind": "evidence-size", "path": path, "additional_bytes": extra}
        self.rec_items = getattr(self, "rec_items", []) + [item]
        self.write(REC, "# DR\n\n```json\n" + json.dumps(self.rec_items) + "\n```\n")
        self.budget["exceptions"].append({
            "path": path, "additional_bytes": extra, "reason": reason,
            "decision_record": record_path or REC})
        self.write_budget()


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
        self.assertIn("spec/decision-records", err)  # decision route named

    def test_new_unit_exact_ceiling_ok_one_over_fails(self):
        self.add_exception("sim", 3000)  # budget file itself counts toward sim/
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
        # 1000 B of non-unit sim files: total 5000 + budget file bytes?  Budget
        # file is itself under sim/, so measure what is left.
        self.commit("budget")
        m = chk.measure(str(self.root), "HEAD")
        room = self.budget["total_ceiling_bytes"] - m["sim_bytes"]
        self.assertGreater(room, 0)
        self.write("sim/misc.txt", "q" * room)
        self.commit("fill")
        self.assertEqual(self.run_main()[0], 0)
        self.write("sim/misc2.txt", "q")
        self.commit("overflow")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn(f"sim: {self.budget['total_ceiling_bytes'] + 1} B measured > "
                      f"total ceiling {self.budget['total_ceiling_bytes']} B", err)

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


class Exceptions(Base):
    def test_valid_exception_raises_new_unit_ceiling(self):
        self.add_exception("sim", 3000)
        self.write(NEW + "/d.bin", "n" * 1500)
        self.add_exception(NEW, 500)
        self.commit("exc")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 0, err)

    def test_valid_exception_is_exact_not_open_ended(self):
        self.add_exception("sim", 3000)
        self.write(NEW + "/d.bin", "n" * 1501)
        self.add_exception(NEW, 500)
        self.commit("exc")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("new-unit ceiling 1500 B", err)

    def test_valid_exception_raises_grandfathered_unit(self):
        self.write(UNIT_A + "/more.bin", "m" * 100)
        self.add_exception(UNIT_A, 100)
        self.write("sim/pad.txt", "")
        self.commit("exc")
        self.assertEqual(self.run_main()[0], 0)

    def test_valid_exception_for_total(self):
        self.write("sim/big.txt", "b" * 3000)
        self.add_exception("sim", 4000)
        self.commit("exc")
        self.assertEqual(self.run_main()[0], 0)

    def bad(self, needle, **kw):
        self.commit("bad")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1, err)
        self.assertIn(needle, err)

    def test_missing_record_rejected(self):
        self.budget["exceptions"].append({
            "path": NEW, "additional_bytes": 5, "reason": "r", "decision_record": REC})
        self.write_budget()
        self.bad("not a tracked file")

    def test_mismatched_path_rejected(self):
        self.add_exception(NEW, 5, rec_json={
            "kind": "evidence-size", "path": "sim/a/campaigns/other", "additional_bytes": 5})
        self.bad("has no fenced json block")

    def test_mismatched_allowance_rejected(self):
        self.add_exception(NEW, 5, rec_json={
            "kind": "evidence-size", "path": NEW, "additional_bytes": 6})
        self.bad("has no fenced json block")

    def test_wrong_kind_rejected(self):
        self.add_exception(NEW, 5, rec_json={"path": NEW, "additional_bytes": 5})
        self.bad("has no fenced json block")

    def test_wildcards_and_non_exact_paths_rejected(self):
        for p in ("sim/a/campaigns/*", "sim/*", "sim/a/campaigns/", "sim/a",
                  "sim/a/campaigns/../x/y", "/sim/a/records/x", "sim/a/misc/x",
                  "sim/a/campaigns/c1/sub"):
            with self.subTest(path=p):
                self.setUp()
                self.add_exception(p, 5)
                self.bad("must be exactly 'sim' or one evidence unit")

    def test_malformed_entries_rejected(self):
        self.write(REC, "# DR\n")
        cases = [
            {"path": NEW, "additional_bytes": 5, "reason": "r"},  # missing key
            {"path": NEW, "additional_bytes": 5, "reason": "r", "decision_record": REC, "x": 1},
            {"path": NEW, "additional_bytes": 0, "reason": "r", "decision_record": REC},
            {"path": NEW, "additional_bytes": True, "reason": "r", "decision_record": REC},
            {"path": NEW, "additional_bytes": "5", "reason": "r", "decision_record": REC},
            {"path": NEW, "additional_bytes": 5, "reason": " ", "decision_record": REC},
            {"path": NEW, "additional_bytes": 5, "reason": "r", "decision_record": "README.md"},
            {"path": NEW, "additional_bytes": 5, "reason": "r",
             "decision_record": "spec/decision-records/../../README.md"},
            "not-an-object",
        ]
        for c in cases:
            with self.subTest(case=c):
                self.setUp()
                self.budget["exceptions"] = [c]
                self.write_budget()
                self.bad("exceptions[0]")

    def test_duplicate_path_rejected(self):
        self.add_exception(NEW, 5)
        self.budget["exceptions"].append(dict(self.budget["exceptions"][0]))
        self.write_budget()
        self.bad("duplicates path")


class RepoBudget(unittest.TestCase):
    def test_committed_budget_is_valid_and_matches_issue_baseline(self):
        b = json.loads((ROOT / "sim/evidence-size-budget.json").read_text())
        self.assertEqual(b["allowance"]["derivation"],
                         "ceil(10% x 489675829 B / 1048576 B/MiB) = 47 MiB")
        self.assertEqual(b["baseline"]["sim_bytes"], 489675829)
        self.assertEqual(b["baseline"]["sim_blobs"], 96352)
        self.assertEqual(b["total_ceiling_bytes"], 489675829 + 47 * 1048576)
        extras = chk.validate_budget(str(ROOT), "HEAD", b)
        self.assertEqual(extras, {})
        self.assertEqual(sum(1 for _ in b["units"]), len(b["units"]))

    def test_head_within_committed_budget(self):
        rc = chk.main(["--repo", str(ROOT), "--tree", "HEAD", "--quiet"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

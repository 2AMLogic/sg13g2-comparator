"""Regression tests for scripts/check_append_only_evidence.py (issue #116).

Each test builds a throwaway git repository; stdlib only.
"""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_append_only_evidence.py"
spec = importlib.util.spec_from_file_location("check_append_only_evidence", SCRIPT)
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}
EMPTY_TREE = chk.EMPTY_TREE
DIRS = ["records", "corners", "netlist-snapshots", "campaigns", "reports"]


class Repo:
    def __init__(self, root):
        self.root = Path(root)
        self.git("init", "-q", "-b", "main")

    def git(self, *a):
        r = subprocess.run(["git", "-C", str(self.root), *a], env=ENV,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return r.stdout.decode().strip()

    def write(self, rel, data="x\n", mode=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
        if mode:
            p.chmod(mode)

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def oid(self, rel):
        return self.git("rev-parse", f"HEAD:{rel}")

    def mode(self, rel):
        return self.git("ls-tree", "HEAD", "--", rel).split()[0]


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.r = Repo(self._td.name)

    def run_check(self, base, head="HEAD"):
        return chk.check(str(self.r.root), base, head)

    def main(self, base, head="HEAD"):
        return chk.main(["--repo", str(self.r.root), "--base", base, "--head", head])


class Protection(Base):
    def test_additions_pass(self):
        self.r.write("sim/a/records/one.json")
        b = self.r.commit()
        for d in DIRS:
            self.r.write(f"sim/a/{d}/new.txt")
        self.r.write("sim/zz-new-bench/records/x.json")
        self.r.commit()
        self.assertEqual(self.run_check(b), [])

    def test_modify_delete_each_dir_fail(self):
        for d in DIRS:
            self.r.write(f"sim/b/{d}/deep/f.txt")
        b = self.r.commit()
        for d in DIRS:
            self.r.write(f"sim/b/{d}/deep/f.txt", "changed\n")
        self.r.commit()
        self.assertEqual(len(self.run_check(b)), len(DIRS))
        base2 = self.r.git("rev-parse", "HEAD")
        for d in DIRS:
            (self.r.root / f"sim/b/{d}/deep/f.txt").unlink()
        self.r.commit()
        v = self.run_check(base2)
        self.assertEqual(len(v), len(DIRS))
        self.assertTrue(all("deleted" in x for x in v))

    def test_non_json_campaign_content_protected(self):
        self.r.write("sim/c/campaigns/run1/probe.cir")
        b = self.r.commit()
        self.r.write("sim/c/campaigns/run1/probe.cir", "y\n")
        self.r.commit()
        self.assertEqual(len(self.run_check(b)), 1)

    def test_mutable_sources_editable(self):
        paths = ["sim/a/testbench/t.sp", "sim/klt-corner-verification/benches/b.json",
                 "sim/comparator-pex/dut/d.spice", "sim/comparator-pex/requests/r.json",
                 "sim/README.md", "layout/comparator/comparator.pex.spice",
                 "sim/records/x.json", "records/sim.json", "sim/a/records",
                 "xsim/a/records/x", "sim/a/myrecords/x", "sim/a/sub/records/x"]
        for p in paths:
            self.r.write(p)
        b = self.r.commit()
        for p in paths:
            self.r.write(p, "edited\n")
        self.r.commit()
        self.assertEqual(self.run_check(b), [])

    def test_mode_change_fails(self):
        self.r.write("sim/a/records/s.sh", mode=0o644)
        b = self.r.commit()
        self.r.git("update-index", "--chmod=+x", "sim/a/records/s.sh")
        self.r.git("commit", "-q", "-m", "chmod")
        v = self.run_check(b)
        self.assertEqual(len(v), 1)
        self.assertIn("mode changed", v[0])

    def test_type_change_fails(self):
        self.r.write("sim/a/records/l")
        b = self.r.commit()
        (self.r.root / "sim/a/records/l").unlink()
        os.symlink("elsewhere", self.r.root / "sim/a/records/l")
        self.r.commit()
        v = self.run_check(b)
        self.assertEqual(len(v), 1)
        self.assertIn("type changed", v[0])

    def test_renames(self):
        self.r.write("sim/a/records/orig.json", "data\n")
        self.r.write("sim/a/testbench/src.txt", "src\n")
        b = self.r.commit()
        # protected -> protected, protected -> unprotected fail; copy passes
        self.r.git("mv", "sim/a/records/orig.json", "sim/a/records/moved.json")
        self.r.commit()
        self.assertEqual(len(self.run_check(b)), 1)
        b2 = self.r.git("rev-parse", "HEAD")
        self.r.git("mv", "sim/a/records/moved.json", "sim/a/testbench/out.json")
        self.r.commit()
        self.assertEqual(len(self.run_check(b2)), 1)
        # unprotected -> protected passes
        b3 = self.r.git("rev-parse", "HEAD")
        (self.r.root / "sim/a/campaigns").mkdir(parents=True)
        self.r.git("mv", "sim/a/testbench/src.txt", "sim/a/campaigns/src.txt")
        self.r.commit()
        self.assertEqual(self.run_check(b3), [])
        # copy retaining original passes
        b4 = self.r.git("rev-parse", "HEAD")
        self.r.write("sim/a/campaigns/copy.txt", "src\n")
        self.r.commit()
        self.assertEqual(self.run_check(b4), [])

    def test_weird_filenames_nul_safe(self):
        names = ["sim/a/records/sp ace.json", "sim/a/records/ta\tb.json",
                 "sim/a/records/new\nline.json"]
        for n in names:
            self.r.write(n)
        b = self.r.commit()
        for n in names:
            self.r.write(n, "z\n")
        self.r.commit()
        self.assertEqual(len(self.run_check(b)), 3)

    def test_all_violations_reported(self):
        for i in range(3):
            self.r.write(f"sim/a/records/{i}")
        b = self.r.commit()
        for i in range(3):
            self.r.write(f"sim/a/records/{i}", "n\n")
        self.r.commit()
        self.assertEqual(len(self.run_check(b)), 3)
        self.assertEqual(self.main(b), 1)


class AggregateCharacterization(Base):
    D = "sim/characterization/20261009-x-schematic"

    def _base(self):
        for n in ("report.json", "input-index.json"):
            self.r.write(f"{self.D}/{n}")
        return self.r.commit()

    def test_modify_delete_move_mode_fail(self):
        b = self._base()
        self.r.write(f"{self.D}/report.json", "changed\n")
        (self.r.root / self.D / "input-index.json").rename(
            self.r.root / "sim/characterization/moved.json")
        self.r.commit()
        v = self.run_check(b)
        self.assertEqual(len(v), 2, v)
        b2 = self.r.git("rev-parse", "HEAD")
        (self.r.root / self.D / "report.json").chmod(0o755)
        self.r.commit()
        self.assertEqual(len(self.run_check(b2)), 1)

    def test_additions_pass(self):
        b = self._base()
        self.r.write("sim/characterization/new-report/report.json")
        self.r.write(f"{self.D}/extra.md")
        self.r.commit()
        self.assertEqual(self.run_check(b), [])

    def test_existing_exception_mechanism_authorizes(self):
        b = self._base()
        old = self.r.oid(f"{self.D}/report.json")
        self.r.write(f"{self.D}/report.json", "fixed\n")
        self.r.commit()
        new = self.r.oid(f"{self.D}/report.json")
        tup = {"path": f"{self.D}/report.json", "old_oid": old, "old_mode": "100644",
               "new_oid": new, "new_mode": "100644"}
        self.r.write("spec/decision-records/0009-x.md",
                     "```json\n" + json.dumps(tup) + "\n```\n")
        self.r.write("sim/evidence-exceptions.json", json.dumps(
            {"version": 1, "exceptions": [dict(
                tup, decision_record="spec/decision-records/0009-x.md", reason="r")]}))
        self.r.commit()
        self.assertEqual(self.run_check(b), [])


class Revisions(Base):
    def test_merge_base_vs_diverged_main(self):
        self.r.write("sim/a/records/old.json")
        root = self.r.commit()
        self.r.git("checkout", "-q", "-b", "pr")
        self.r.write("sim/a/records/pr-new.json")
        pr_head = self.r.commit()
        self.r.git("checkout", "-q", "main")
        self.r.git("rm", "-q", "sim/a/records/old.json")
        main_tip = self.r.commit()
        mb = self.r.git("merge-base", main_tip, pr_head)
        self.assertEqual(mb, root)
        self.assertEqual(self.run_check(mb, pr_head), [])
        # naive tip-to-head comparison would (wrongly) flag a deletion
        self.assertEqual(len(self.run_check(main_tip, pr_head)), 0)  # only additions vs main
        self.assertEqual(self.main(mb, pr_head), 0)

    def test_multi_commit_push(self):
        self.r.write("sim/a/records/a.json")
        before = self.r.commit()
        self.r.write("sim/a/records/b.json")
        self.r.commit()
        self.r.write("sim/a/records/a.json", "rewritten\n")
        self.r.commit()
        self.assertEqual(len(self.run_check(before)), 1)

    def test_empty_initial_tree(self):
        self.r.write("sim/a/records/a.json")
        self.r.commit()
        self.assertEqual(self.run_check(EMPTY_TREE), [])

    def test_last_commit_audit(self):
        self.r.write("sim/a/records/a.json")
        self.r.commit()
        self.r.write("sim/a/records/a.json", "bad\n")
        self.r.commit()
        self.assertEqual(self.main("HEAD^", "HEAD"), 1)

    def test_unavailable_revisions_exit_2(self):
        self.r.write("sim/a/records/a.json")
        self.r.commit()
        self.assertEqual(self.main("0" * 40), 2)
        self.assertEqual(self.main("HEAD", "nonexistent"), 2)
        self.assertEqual(chk.main(["--repo", "/nonexistent-dir-xyz",
                                   "--base", "a", "--head", "b"]), 2)


class Exceptions(Base):
    PATH = "sim/a/records/r.json"
    REC = "spec/decision-records/0100-fix.md"

    def setup_change(self, delete=False):
        self.r.write(self.PATH, "old\n")
        self.old_oid, self.old_mode = None, "100644"
        base = self.r.commit()
        self.old_oid = self.r.oid(self.PATH)
        if delete:
            (self.r.root / self.PATH).unlink()
        else:
            self.r.write(self.PATH, "new\n")
        return base

    def finish(self, entry_over=None, block_over=None, delete=False, record=True,
               track=True, extra_entries=(), raw_registry=None):
        new_oid = None if delete else self.r.git("hash-object", self.PATH and
                                                  str(self.r.root / self.PATH))
        entry = {"path": self.PATH, "old_oid": self.old_oid, "old_mode": "100644",
                 "new_oid": new_oid, "new_mode": None if delete else "100644",
                 "decision_record": self.REC, "reason": "documented fix"}
        block = {k: entry[k] for k in chk.TUPLE_KEYS}
        entry.update(entry_over or {})
        block.update(block_over or {})
        if record:
            self.r.write(self.REC, "# Decision\n\n```json\n"
                         + json.dumps(block) + "\n```\n")
        reg = raw_registry if raw_registry is not None else json.dumps(
            {"version": 1, "exceptions": [entry, *extra_entries]})
        self.r.write("sim/evidence-exceptions.json", reg)
        if track:
            self.r.commit()
        else:
            self.r.git("add", "sim/evidence-exceptions.json", self.PATH)
            self.r.git("commit", "-q", "-m", "no record")

    def test_authorized_modify_passes(self):
        b = self.setup_change()
        self.finish()
        self.assertEqual(self.run_check(b), [])

    def test_authorized_delete_passes(self):
        b = self.setup_change(delete=True)
        self.finish(delete=True)
        self.assertEqual(self.run_check(b), [])

    def test_registry_alone_grants_nothing(self):
        b = self.setup_change()
        self.finish(record=False, track=False)
        with self.assertRaises(chk.RegistryError):
            self.run_check(b)
        self.assertEqual(self.main(b), 1)

    def test_mismatch_cases_fail(self):
        zero = "1" * 40
        cases = [
            ("old_oid", {"old_oid": zero}, None),
            ("mode", {"old_mode": "100755"}, None),
            ("new_oid", {"new_oid": zero}, None),
            ("new_mode", {"new_mode": "100755"}, None),
            ("block_mismatch", None, {"new_oid": zero}),
            ("block_path", None, {"path": "sim/a/records/other.json"}),
        ]
        for name, eo, bo in cases:
            with self.subTest(name):
                self.setUp()
                b = self.setup_change()
                self.finish(entry_over=eo, block_over=bo)
                try:
                    v = self.run_check(b)
                except chk.RegistryError:
                    continue
                self.assertEqual(len(v), 1)

    def test_bad_registry_fails_closed(self):
        bad_paths = ["sim/a/records/*", "sim/a/records", "/abs/sim/a/records/x",
                     "sim/a/records/../records/r.json", "sim/a/testbench/x",
                     "sim/a/records/", "./sim/a/records/r.json"]
        for p in bad_paths:
            with self.subTest(p):
                self.setUp()
                b = self.setup_change()
                self.finish(entry_over={"path": p})
                with self.assertRaises(chk.RegistryError):
                    self.run_check(b)

    def test_malformed_registries(self):
        for raw in ["{not json", "[]", '{"version":2,"exceptions":[]}',
                    '{"version":1}', '{"version":1,"exceptions":{}}']:
            with self.subTest(raw):
                self.setUp()
                b = self.setup_change()
                self.finish(raw_registry=raw)
                with self.assertRaises(chk.RegistryError):
                    self.run_check(b)

    def test_bad_fields(self):
        for over in [{"reason": "  "}, {"old_oid": "abc"}, {"old_mode": "644"},
                     {"decision_record": "docs/x.md"},
                     {"decision_record": "spec/decision-records/missing.md"},
                     {"new_oid": None}, {"extra": 1}]:
            with self.subTest(over):
                self.setUp()
                b = self.setup_change()
                self.finish(entry_over=over)
                with self.assertRaises(chk.RegistryError):
                    self.run_check(b)

    def test_duplicate_entries_fail(self):
        b = self.setup_change()
        dup = {"path": self.PATH, "old_oid": "2" * 40, "old_mode": "100644",
               "new_oid": "3" * 40, "new_mode": "100644",
               "decision_record": self.REC, "reason": "dup"}
        self.finish(extra_entries=[dup])
        with self.assertRaises(chk.RegistryError):
            self.run_check(b)

    def test_untracked_record_fails(self):
        b = self.setup_change()
        self.finish(record=False, track=True)
        self.r.write(self.REC, "x")  # present on disk, never committed
        with self.assertRaises(chk.RegistryError):
            self.run_check(b)

    def test_unrelated_exception_does_not_weaken(self):
        self.r.write("sim/a/records/other.json", "o\n")
        b = self.setup_change()
        self.finish()
        self.r.write("sim/a/records/other.json", "tampered\n")
        self.r.commit()
        self.assertEqual(len(self.run_check(b)), 1)


if __name__ == "__main__":
    unittest.main()

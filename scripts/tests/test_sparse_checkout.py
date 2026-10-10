"""Sparse-checkout cone proof for .github/workflows/ci.yml (issue #132).

For every CI job this builds a *clean* sparse checkout of the repository's
current HEAD commit from the job's declared `sparse-checkout:` patterns (a
local no-network clone, no blob filter), then runs the job's exact `run:`
commands from ci.yml inside it. A pattern list missing a transitive input
makes the real command fail here.

* Stdlib-only jobs (append-only/size guards, harness unit tests) always run.
* Jobs whose commands need the pinned `klt` (signoff parity, layout
  reproducibility) run only when `klt --version` matches
  manifests/klt-pin.json (set PATH to an environment holding the pinned
  klayout-tools + klayout); otherwise they are SKIPPED, never passed. CI itself
  runs those jobs with the same patterns on every change.

The test uses committed state (HEAD): commit before running it.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
NESTED = "LOOM_SPARSE_TEST_NESTED"
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
KLT_JOBS = {"signoff-manifest-parity", "layout-reproducibility"}


def parse_jobs(text):
    """Minimal parser for this workflow's shape -> {job: {checkout, steps}}."""
    jobs = {}
    m = re.search(r"^jobs:\n(.*)\Z", text, re.S | re.M)
    body = m.group(1)
    for jm in re.finditer(r"^  ([A-Za-z0-9_-]+):\n((?:(?:    .*)?\n)+)", body, re.M):
        name, jbody = jm.group(1), jm.group(2)
        jobs[name] = {"checkout": checkout_of(jbody), "runs": runs_of(jbody)}
    return jobs


def checkout_of(jbody):
    m = re.search(r"uses: actions/checkout@\S+[^\n]*\n((?:        .*\n|\n)*)", jbody)
    assert m, "job has no actions/checkout step"
    withb = m.group(1)
    sp = re.search(r"^ {10}sparse-checkout: \|\n((?: {12}\S.*\n)+)", withb, re.M)
    pats = [l.strip() for l in sp.group(1).splitlines()] if sp else []
    cone = re.search(r"^ {10}sparse-checkout-cone-mode: (\S+)", withb, re.M)
    return {"patterns": pats, "cone": cone.group(1) if cone else None,
            "with": withb}


def runs_of(jbody):
    """[(step name, env dict, script)] for each `run:` step."""
    out = []
    for sm in re.finditer(r"^      - (.*?)(?=^      - |\Z)", jbody, re.S | re.M):
        step = sm.group(0)
        rm = re.search(r"^        run: \|\n((?:          .*\n|\n)+)", step, re.M)
        if rm:
            script = "\n".join(l[10:] for l in rm.group(1).splitlines()) + "\n"
        else:
            rm = re.search(r"^        run: (.+)$", step, re.M)
            if not rm:
                continue
            script = rm.group(1) + "\n"
        nm = re.search(r"name: (.*)", step)
        out.append((nm.group(1) if nm else "?", script))
    return out


def sh(args, cwd, env=None, check=True):
    return subprocess.run(args, cwd=cwd, env=env or ENV, check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True)


def klt_matches_pin():
    import json
    pin = json.loads((ROOT / "manifests" / "klt-pin.json").read_text())
    try:
        out = sh(["klt", "--version"], ROOT, check=False).stdout
    except OSError:
        return False
    return pin["klt_version"].split("+g")[-1][:12] in out


@unittest.skipIf(os.environ.get(NESTED), "nested run inside a sparse clone")
class SparseCones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = parse_jobs(CI.read_text())
        cls.head = sh(["git", "rev-parse", "HEAD"], ROOT).stdout.strip()

    def test_every_job_declares_explicit_sparse_patterns_without_filter(self):
        self.assertEqual(
            set(self.jobs),
            {"signoff-manifest-parity", "layout-reproducibility",
             "harness-unit-tests", "append-only-evidence"})
        for name, job in self.jobs.items():
            co = job["checkout"]
            self.assertTrue(co["patterns"], name)
            self.assertEqual(co["cone"], "false", name)
            self.assertNotRegex(co["with"], r"(?m)^\s*filter:", f"{name}: blob filter forbidden")
            for p in co["patterns"]:
                self.assertTrue(p.startswith("/"), f"{name}: unanchored {p!r}")
                # only a basename wildcard (`dir/*.ext`); never `**`, `?`, `[`, `!`
                self.assertFalse(set("?[!") & set(p) or "**" in p
                                 or "*" in p.rsplit("/", 1)[0], f"{name}: wildcard {p!r}")

    def test_append_only_job_keeps_full_history(self):
        self.assertIn("fetch-depth: 0", self.jobs["append-only-evidence"]["checkout"]["with"])

    def _clone(self, tmp, patterns):
        dst = Path(tmp) / "clone"
        sh(["git", "clone", "-q", "--no-checkout", "--local",
            str(ROOT), str(dst)], tmp)
        sh(["git", "config", "core.sparseCheckout", "true"], dst)
        sh(["git", "config", "core.sparseCheckoutCone", "false"], dst)
        (dst / ".git" / "info").mkdir(exist_ok=True)
        (dst / ".git" / "info" / "sparse-checkout").write_text("\n".join(patterns) + "\n")
        sh(["git", "checkout", "-q", "--detach", self.head], dst)
        return dst

    def _run_job(self, name):
        job = self.jobs[name]
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, job["checkout"]["patterns"])
            env = {**ENV, NESTED: "1"}
            if name == "append-only-evidence":
                env.update(EVENT_NAME="push", PUSH_AFTER=self.head,
                           PUSH_BEFORE=sh(["git", "rev-parse", "HEAD~1"], dst).stdout.strip(),
                           PR_BASE_SHA="", PR_HEAD_SHA="", GITHUB_SHA_CUR=self.head,
                           TARGET_SHA=self.head)
            ran = 0
            for step, script in job["runs"]:
                if "pip install" in script:
                    continue  # tool provisioning, not a repo input
                r = sh(["bash", "-eu", "-c", script], dst, env, check=False)
                self.assertEqual(r.returncode, 0, f"{name} / {step} failed in sparse clone:\n{r.stdout[-3000:]}")
                # A test that skips because its input is outside the cone is a
                # check that cannot run: it must not look like a pass.
                # (only asserted for the harness job: elsewhere `skipped=` can be unrelated text/nested skips.)
                self.assertNotRegex(r.stdout if name == "harness-unit-tests" else "", r"skipped=\d+",
                                    f"{name} / {step}: tests skipped in sparse clone:\n{r.stdout[-3000:]}")
                ran += 1
            self.assertGreater(ran, 0)

    def test_append_only_and_size_job_from_sparse_clone(self):
        self._run_job("append-only-evidence")

    def test_harness_job_from_sparse_clone(self):
        self._run_job("harness-unit-tests")

    def test_klt_jobs_from_sparse_clone(self):
        if not klt_matches_pin():
            self.skipTest("pinned klt not on PATH (CI runs these jobs with the same patterns)")
        for name in sorted(KLT_JOBS):
            with self.subTest(job=name):
                self._run_job(name)


if __name__ == "__main__":
    unittest.main()

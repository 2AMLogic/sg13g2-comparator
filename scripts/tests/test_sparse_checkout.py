"""Sparse-checkout cone proof for .github/workflows/ci.yml (issue #132).

For every CI job this builds a *clean* checkout of the repository's current
HEAD commit with the same semantics actions/checkout uses for that job's
`with:` block, then runs the job's exact `run:` commands from ci.yml inside it.
A pattern list missing a transitive input makes the real command fail here.

actions/checkout semantics emulated (pinned v4.4.0, src/git-source-provider.ts):
an explicit `filter:` is used as given; otherwise a `sparse-checkout:` input
silently implies `--filter=blob:none` (a partial clone; an empty `filter:`
cannot disable it); without either, the clone is complete and the whole tree is
checked out. Filtered clones are made over file:// so the filter is honoured
(a `--local` clone would ignore it, which is how CI run 38029844566's hang in
the size check slipped past an earlier version of this test).

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
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
NESTED = "LOOM_SPARSE_TEST_NESTED"
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
KLT_JOBS = {"signoff-manifest-parity", "layout-reproducibility"}
SIZE_JOB = "append-only-evidence"
SIZE_STEP = "Check tracked sim/ evidence size budget"
NARROW = "git sparse-checkout set --no-cone --stdin <<'EOF'\n"
UPLOAD_PACK = "git -c uploadpack.allowFilter=true upload-pack"


def parse_jobs(text):
    """Minimal parser for this workflow's shape -> {job: {checkout, steps}}."""
    jobs = {}
    m = re.search(r"^jobs:\n(.*)\Z", text, re.S | re.M)
    body = m.group(1)
    for jm in re.finditer(r"^  ([A-Za-z0-9_-]+):\n((?:(?:    .*)?\n)+)", body, re.M):
        name, jbody = jm.group(1), jm.group(2)
        runs = runs_of(jbody)
        co = checkout_of(jbody)
        jobs[name] = {"checkout": co, "runs": runs,
                      "patterns": co["patterns"] or narrow_patterns(runs)}
    return jobs


def checkout_of(jbody):
    m = re.search(r"uses: actions/checkout@\S+[^\n]*\n((?:        .*\n|\n)*)", jbody)
    assert m, "job has no actions/checkout step"
    withb = m.group(1)
    sp = re.search(r"^ {10}sparse-checkout: \|\n((?: {12}\S.*\n)+)", withb, re.M)
    pats = [l.strip() for l in sp.group(1).splitlines()] if sp else []
    cone = re.search(r"^ {10}sparse-checkout-cone-mode: (\S+)", withb, re.M)
    filt = re.search(r"^ {10}filter: *(.*)$", withb, re.M)
    filt = filt.group(1).strip().strip("'\"") if filt else ""
    return {"patterns": pats, "cone": cone.group(1) if cone else None,
            "with": withb,
            # actions/checkout: explicit filter wins, else sparse => blob:none
            "filter": filt or ("blob:none" if pats else None)}


def narrow_patterns(runs):
    """Patterns of a post-checkout `git sparse-checkout set --stdin` heredoc."""
    for _step, script in runs:
        if NARROW in script:
            body = script.split(NARROW, 1)[1]
            return [l.strip() for l in body.split("\nEOF\n", 1)[0].splitlines()]
    return []


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
    # Read from the commit, not the working tree: this test itself runs in the
    # append-only job's sparse cone, which does not contain manifests/.
    pin = json.loads(sh(["git", "show", "HEAD:manifests/klt-pin.json"], ROOT).stdout)
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
             "harness-unit-tests", SIZE_JOB})
        for name, job in self.jobs.items():
            co = job["checkout"]
            self.assertTrue(job["patterns"], name)
            self.assertNotRegex(co["with"], r"(?m)^\s*filter:", f"{name}: blob filter forbidden")
            if co["patterns"]:
                self.assertEqual(co["cone"], "false", name)
            for p in job["patterns"]:
                self.assertTrue(p.startswith("/"), f"{name}: unanchored {p!r}")
                # only a basename wildcard (`dir/*.ext`); never `**`, `?`, `[`, `!`
                self.assertFalse(set("?[!") & set(p) or "**" in p
                                 or "*" in p.rsplit("/", 1)[0], f"{name}: wildcard {p!r}")

    def test_append_only_job_keeps_full_history(self):
        self.assertIn("fetch-depth: 0", self.jobs[SIZE_JOB]["checkout"]["with"])

    def test_size_measuring_jobs_get_a_complete_clone(self):
        """Any job running the size checker must not be a partial clone.

        A `sparse-checkout:` input on actions/checkout implies blob:none, so
        such a job narrows its working tree in a later step instead.
        """
        users = {n for n, j in self.jobs.items()
                 if any("check_evidence_size.py" in s for _, s in j["runs"])}
        self.assertEqual(users, {SIZE_JOB})
        for name in users:
            co = self.jobs[name]["checkout"]
            self.assertIsNone(co["filter"], f"{name}: actions/checkout would make a "
                              f"partial clone (filter {co['filter']})")
            self.assertEqual(co["patterns"], [], name)
            self.assertTrue(narrow_patterns(self.jobs[name]["runs"]), name)

    def _clone(self, tmp, checkout):
        """Clone HEAD the way actions/checkout would for this `with:` block."""
        dst = Path(tmp) / "clone"
        if checkout["filter"]:
            sh(["git", "clone", "-q", "--no-checkout", f"--filter={checkout['filter']}",
                "-u", UPLOAD_PACK, f"file://{ROOT}", str(dst)], tmp)
            sh(["git", "config", "remote.origin.uploadpack", UPLOAD_PACK], dst)
        else:
            sh(["git", "clone", "-q", "--no-checkout", "--local",
                str(ROOT), str(dst)], tmp)
        if checkout["patterns"]:
            sh(["git", "config", "core.sparseCheckout", "true"], dst)
            sh(["git", "config", "core.sparseCheckoutCone", "false"], dst)
            (dst / ".git" / "info").mkdir(exist_ok=True)
            (dst / ".git" / "info" / "sparse-checkout").write_text(
                "\n".join(checkout["patterns"]) + "\n")
        sh(["git", "checkout", "-q", "--detach", self.head], dst)
        return dst

    def _env(self, dst):
        return {**ENV, NESTED: "1", "EVENT_NAME": "push", "PUSH_AFTER": self.head,
                "PUSH_BEFORE": sh(["git", "rev-parse", "HEAD~1"], dst).stdout.strip(),
                "PR_BASE_SHA": "", "PR_HEAD_SHA": "", "GITHUB_SHA_CUR": self.head,
                "TARGET_SHA": self.head}

    def _run_job(self, name):
        job = self.jobs[name]
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, job["checkout"])
            env = self._env(dst)
            ran = 0
            for step, script in job["runs"]:
                if "pip install" in script:
                    continue  # tool provisioning, not a repo input
                if script.lstrip().startswith("ruff ") and shutil.which("ruff") is None:
                    continue  # CI-only linter (pinned in ci.yml); not a repo input
                r = sh(["bash", "-eu", "-c", script], dst, env, check=False)
                self.assertEqual(r.returncode, 0, f"{name} / {step} failed in sparse clone:\n{r.stdout[-3000:]}")
                # A test that skips because its input is outside the cone is a
                # check that cannot run: it must not look like a pass.
                # (only asserted for the harness job: elsewhere `skipped=` can be unrelated text/nested skips.)
                self.assertNotRegex(r.stdout if name == "harness-unit-tests" else "", r"skipped=\d+",
                                    f"{name} / {step}: tests skipped in sparse clone:\n{r.stdout[-3000:]}")
                ran += 1
            self.assertGreater(ran, 0)
            # the working tree really is narrowed to the declared patterns
            if name == SIZE_JOB:
                self.assertTrue((dst / "sim/evidence-size-budget.json").is_file())
                self.assertFalse((dst / "sim/dut.json").exists())
                # This very test module runs un-nested in that job's cone in CI
                # (the step above sets NESTED); its own inputs must be there.
                # The klt case is cheap (skips) unless the pinned klt is on PATH.
                env.pop(NESTED)
                r = sh(["python3", "-m", "unittest", "scripts.tests.test_sparse_checkout"
                        ".SparseCones.test_klt_jobs_from_sparse_clone"], dst, env, check=False)
                self.assertEqual(r.returncode, 0, r.stdout[-3000:])

    def test_size_check_fails_closed_fast_in_a_blob_filtered_clone(self):
        """The pre-fix layout (sparse-checkout input => blob:none) must exit 2
        quickly with a clear message instead of lazily fetching every blob."""
        job = self.jobs[SIZE_JOB]
        steps = dict(job["runs"])
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, {"filter": "blob:none", "cone": "false",
                                    "patterns": job["patterns"]})
            env = self._env(dst)
            for step in (SIZE_STEP, next(s for s in steps if NARROW in steps[s])):
                with self.subTest(step=step):
                    t0 = time.monotonic()
                    r = subprocess.run(["bash", "-eu", "-c", steps[step]], cwd=dst, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, timeout=60)
                    self.assertEqual(r.returncode, 2, r.stdout[-3000:])
                    self.assertIn("partial clone", r.stdout)
                    self.assertLess(time.monotonic() - t0, 30)

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

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

import fnmatch
import importlib.util
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
NETLIST_JOB = "netlist-regeneration"
SIZE_JOB = "append-only-evidence"
SIZE_STEP = "Check tracked sim/ evidence size budget"
NARROW = "git sparse-checkout set --no-cone --stdin <<'EOF'\n"
UPLOAD_PACK = "git -c uploadpack.allowFilter=true upload-pack"

# The lint-scope preflight (issue #216): its LINT_ROOTS is the maintained
# copy of the ruff step's argument list that both ci.yml and the cone below
# must agree with. Loaded, not redefined, so there is exactly one list.
PREFLIGHT = ROOT / "scripts" / "check_lint_population.py"
_spec = importlib.util.spec_from_file_location("check_lint_population", PREFLIGHT)
preflight = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preflight)


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


class ShError(subprocess.CalledProcessError):
    """CalledProcessError whose text carries the captured output.

    unittest tracebacks print only str(exc); the stock message is just
    "exit status N", which hides git's own `fatal:` line in CI logs.
    """

    def __str__(self):
        return (f"{super().__str__()}\n--- output (last 3000 chars) ---\n"
                f"{(self.output or '')[-3000:]}")


def sh(args, cwd, env=None, check=True):
    r = subprocess.run(args, cwd=cwd, env=env or ENV, check=False,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True)
    if check and r.returncode != 0:
        raise ShError(r.returncode, args, output=r.stdout)
    return r


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
             NETLIST_JOB, "harness-unit-tests", SIZE_JOB})
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
                if "pip install" in script or "apt-get" in script or "provision_netlist_env" in script:
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

    def test_readme_claims_guard_runs_in_the_signoff_cone(self):
        """Issue #193: the guard reads extra evidence sources (issues #193,
        #228, #232); the signoff job's cone must hold exactly those, and
        dropping them must fail."""
        sources = ["/sim/klt-corner-verification/campaigns/20261009-issue81/noise_full.json",
                   "/sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.json",
                   "/sim/comparator-offset-cm-band/campaigns/20261009-5185f52/comparison.json",
                   "/sim/comparator-kickback/records/20260916-022249-36773c7.json"]
        co = self.jobs["signoff-manifest-parity"]["checkout"]
        for src in sources:
            self.assertIn(src, co["patterns"])
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, co)
            for src in sources:
                self.assertTrue((dst / src.lstrip("/")).is_file(), src)
            r = sh(["python3", "scripts/check_readme_claims.py"], dst, self._env(dst), check=False)
            self.assertEqual(r.returncode, 0, r.stdout[-3000:])
            self.assertIn("source-registry README claims", r.stdout)
        # negative control: without the sources the guard fails closed, naming them
        with tempfile.TemporaryDirectory() as tmp:
            cut = dict(co, patterns=[p for p in co["patterns"] if p not in sources])
            dst = self._clone(tmp, cut)
            r = sh(["python3", "scripts/check_readme_claims.py"], dst, self._env(dst), check=False)
            self.assertEqual(r.returncode, 1, r.stdout[-3000:])
            self.assertIn("source noise-full-issue81", r.stdout)
            self.assertIn("source offset-whole-latch-ea40b57", r.stdout)
            self.assertIn("source offset-cm-band-5185f52", r.stdout)
            self.assertIn("source kickback-residue-36773c7", r.stdout)

    def test_netlist_job_inputs_are_in_its_cone(self):
        """Issue #224: the cone holds the generator, schematics, symbols, the
        committed netlist, imported harness modules, the PDK pin and the
        provisioner. Runs the job's real check step only when a real xschem
        and PDK are available (SKIPPED, never passed, otherwise; CI always
        provisions both). A cone missing an input fails the real command."""
        job = self.jobs[NETLIST_JOB]
        check = next(s for n, s in job["runs"] if "netlist.py --check" in s)
        xs = shutil.which("xschem")
        pdk_root = os.environ.get("PDK_ROOT")
        if not xs or not pdk_root:
            self.skipTest("real xschem and PDK_ROOT not available (CI provisions both)")
        # same step as ci.yml, with the ambient xschem standing in for the
        # provisioned one (the provisioned-path assertion line is dropped)
        script = "\n".join(l for l in check.splitlines() if "command -v" not in l)
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, job["checkout"])
            tracked = sh(["git", "ls-tree", "-r", "--name-only", "HEAD", "design/"], ROOT).stdout.split()
            for t in tracked:
                if t.startswith("design/tests/"):
                    continue
                self.assertTrue((dst / t).is_file(), f"{t} missing from the netlist cone")
            env = {**self._env(dst), "PATH": os.environ["PATH"], "PDK_ROOT": pdk_root,
                   "PWD": str(dst), "RUNNER_TEMP": tmp}
            r = sh(["bash", "-eu", "-c", script], dst, env, check=False)
            self.assertEqual(r.returncode, 0, r.stdout[-3000:])
            self.assertIn("is up to date", r.stdout)
            # negative control: dropping a symbol from the cone must FAIL
            (dst / "design" / "comparator_dut.sym").unlink()
            r = sh(["bash", "-eu", "-c", script], dst, env, check=False)
            self.assertNotEqual(r.returncode, 0, r.stdout[-3000:])

    def test_klt_jobs_from_sparse_clone(self):
        if not klt_matches_pin():
            self.skipTest("pinned klt not on PATH (CI runs these jobs with the same patterns)")
        for name in sorted(KLT_JOBS):
            with self.subTest(job=name):
                self._run_job(name)

    # --- issue #216: the harness job's lint population is complete ---------

    @staticmethod
    def _covered(patterns, path):
        """True when a non-cone sparse pattern list checks `path` out.

        Restricted to the grammar test_every_job_declares... enforces:
        anchored, basename globs only (`*` never crosses `/`), directory
        patterns cover their subtree.
        """
        rel = path.split("/")
        for pat in patterns:
            parts = pat.strip("/").split("/")
            if len(parts) <= len(rel) and all(
                    fnmatch.fnmatchcase(a, b) for a, b in zip(rel, parts)):
                return True
        return False

    def _ruff_step(self):
        return next(s for _, s in self.jobs["harness-unit-tests"]["runs"]
                    if "ruff check" in s)

    def _in_scope_tracked(self):
        tracked = sh(["git", "ls-tree", "-r", "--name-only", "HEAD"], ROOT).stdout.splitlines()
        return [p for p in tracked if preflight.in_scope(p)]

    def test_harness_cone_covers_every_tracked_lint_input(self):
        """Every tracked .py under the reviewed lint roots (issue #157's
        scope, held by the preflight's LINT_ROOTS) must be inside the
        harness job's sparse cone, and ci.yml's ruff command must name
        exactly those roots -- otherwise the lint population silently
        shrinks (issue #216)."""
        job = self.jobs["harness-unit-tests"]
        self.assertEqual(preflight.ci_ruff_arguments(), preflight.LINT_ROOTS)
        self.assertIn("/.github/workflows/ci.yml", job["patterns"],
                      "the preflight reads ci.yml; it must be in the cone")
        inscope = self._in_scope_tracked()
        # sentinels from every root the old cone omitted, so a broken
        # in_scope cannot make this test pass vacuously
        for sentinel in ("scripts/check_klt_pin.py", "sim/run_corners.py",
                         "sim/comparator-transient-noise/probit.py",
                         "sim/comparator-transient-noise-full/calibrate.py",
                         "sim/device-mismatch-confirm/summarize_dvgs.py",
                         "layout/comparator/check_stream.py"):
            self.assertIn(sentinel, inscope)
        uncovered = [p for p in inscope if not self._covered(job["patterns"], p)]
        self.assertEqual(uncovered, [],
                         "tracked lint inputs outside the harness cone")

    def test_preflight_fails_when_cone_omits_a_lint_root(self):
        """Dropping /scripts/ from the cone must fail the preflight with the
        omitted paths named -- even though ruff itself exits zero on the
        rump cone (F-only missing-root warnings). The preflight script is
        copied in after the clone: it is the checker here, not a subject."""
        job = self.jobs["harness-unit-tests"]
        cut = dict(job["checkout"],
                   patterns=[p for p in job["patterns"] if p != "/scripts/"])
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, cut)
            (dst / "scripts").mkdir(exist_ok=True)
            shutil.copy(PREFLIGHT, dst / "scripts" / "check_lint_population.py")
            r = sh(["python3", "scripts/check_lint_population.py"], dst,
                   self._env(dst), check=False)
            self.assertEqual(r.returncode, 1, r.stdout[-3000:])
            self.assertIn("scripts/check_klt_pin.py", r.stdout)
            if shutil.which("ruff"):
                r2 = sh(["bash", "-eu", "-c", self._ruff_step()], dst,
                        self._env(dst), check=False)
                self.assertEqual(r2.returncode, 0,
                                 "ruff alone should stay green here; the "
                                 "preflight is what fails:\n" + r2.stdout[-2000:])

    def test_preflight_fails_when_run_entry_point_glob_underexpands(self):
        """The pre-fix cone shape: one run entry point checked out, so the
        ruff step's `sim/run_*.py` glob silently expands to a subset. The
        preflight derives the intended set from git's tracked inventory and
        must fail naming the omitted entry points, while ruff stays green."""
        job = self.jobs["harness-unit-tests"]
        patterns = [p if p != "/sim/run_*.py" else "/sim/run_offset_cm_band.py"
                    for p in job["patterns"]]
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, dict(job["checkout"], patterns=patterns))
            r = sh(["python3", "scripts/check_lint_population.py"], dst,
                   self._env(dst), check=False)
            self.assertEqual(r.returncode, 1, r.stdout[-3000:])
            for omitted in ("sim/run_corners.py", "sim/run_klt_yield.py"):
                self.assertIn(omitted, r.stdout)
            if shutil.which("ruff"):
                r2 = sh(["bash", "-eu", "-c", self._ruff_step()], dst,
                        self._env(dst), check=False)
                self.assertEqual(r2.returncode, 0,
                                 "the under-expanded glob must not fail ruff; "
                                 "only the preflight catches it:\n" + r2.stdout[-2000:])

    def test_undefined_name_in_previously_omitted_root_fails_static_check(self):
        """Negative control for the coverage itself: an undefined name in
        sim/device-mismatch-confirm (absent from the pre-fix cone) reaches
        ruff -- the population is complete, the preflight stays green and
        the F821 fails the static check."""
        if shutil.which("ruff") is None:
            self.skipTest("ruff not on PATH (CI installs the pinned version "
                          "for this control)")
        job = self.jobs["harness-unit-tests"]
        with tempfile.TemporaryDirectory() as tmp:
            dst = self._clone(tmp, job["checkout"])
            victim = dst / "sim" / "device-mismatch-confirm" / "summarize_dvgs.py"
            victim.write_text(victim.read_text()
                              + "\nNEGATIVE_CONTROL = undefined_name_for_control\n")
            r = sh(["python3", "scripts/check_lint_population.py"], dst,
                   self._env(dst), check=False)
            self.assertEqual(r.returncode, 0, r.stdout[-3000:])
            r2 = sh(["bash", "-eu", "-c", self._ruff_step()], dst,
                    self._env(dst), check=False)
            self.assertNotEqual(r2.returncode, 0, r2.stdout[-3000:])
            self.assertIn("F821", r2.stdout)
            self.assertIn("sim/device-mismatch-confirm/summarize_dvgs.py", r2.stdout)


class ShDiagnostics(unittest.TestCase):
    def test_failure_text_includes_git_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(subprocess.CalledProcessError) as cm:
                sh(["git", "clone", "-q", str(Path(tmp) / "nonexistent"),
                    str(Path(tmp) / "dst")], tmp)
        self.assertIn("fatal:", str(cm.exception))

    def test_failure_output_is_truncated_to_tail(self):
        script = "import sys; print('A' * 4 + 'x' * 5000 + 'Z' * 4); sys.exit(3)"
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            sh(["python3", "-c", script], ROOT)
        self.assertEqual(cm.exception.returncode, 3)
        text = str(cm.exception)
        self.assertIn("ZZZZ", text)
        self.assertNotIn("AAAA", text)

    def test_success_does_not_raise(self):
        self.assertEqual(sh(["true"], ROOT).returncode, 0)


if __name__ == "__main__":
    unittest.main()

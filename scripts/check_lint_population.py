#!/usr/bin/env python3
"""Sparse-cone preflight for the CI static check (issue #216).

The harness job's `ruff check --select F` step names explicit roots. With
F-only rules a missing root is a warning ruff does not fail on, and a shell
glob (`sim/run_*.py`) expands to whatever the sparse cone happened to check
out -- so a green job can lint a subset of the promised files (CI run
38159735276 printed "Failed to lint scripts" and two missing directories,
then "All checks passed").

This preflight runs before ruff and fails closed. The intended file set is
git's tracked inventory (`git ls-tree -r --name-only HEAD`), read from the
commit so it is immune to the sparse working tree and to glob
under-expansion; it is compared with the files actually on disk, and every
omitted path is named. It also asserts that the ruff arguments written in
`.github/workflows/ci.yml` equal LINT_ROOTS below, so the scope cannot
drift between the workflow and this guard.

LINT_ROOTS is the single maintained copy of the reviewed lint scope
(issue #157). `scripts/tests/test_sparse_checkout.py` proves the harness
job's sparse cone covers it and carries the negative controls.

  exit 0   every tracked Python file in scope is present for linting
  exit 1   omitted paths, or ci.yml's ruff arguments != LINT_ROOTS
  exit 2   could not read the tracked inventory or ci.yml (fail closed)

Standard library only; no PDK, no ruff, no installs.
"""

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"

# Must equal the argument list of the `ruff check --select F` step in the
# harness-unit-tests job of .github/workflows/ci.yml (asserted at run time
# below and by scripts/tests/test_sparse_checkout.py). A wildcard root may
# only use a basename glob (`dir/*.py`), mirroring the sparse-pattern
# grammar that job's cone is restricted to.
LINT_ROOTS = [
    "design",
    "layout",
    "scripts",
    "sim/harness",
    "sim/kltsim",
    "sim/comparator-pex",
    "sim/run_*.py",
    "sim/comparator-transient-noise",
    "sim/comparator-transient-noise-full",
    "sim/device-mismatch-confirm",
]


def die(msg):
    print(f"::error::{msg}", file=sys.stderr)
    print(f"lint population preflight: {msg}", file=sys.stderr)
    sys.exit(2)


def tracked_files():
    try:
        r = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"],
                           cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, check=False)
    except OSError as e:
        die(f"cannot run git: {e}")
    if r.returncode != 0:
        die(f"cannot read tracked inventory: {r.stderr.strip()}")
    return r.stdout.splitlines()


def in_scope(path):
    """True for a tracked file the ruff step is responsible for.

    Directory roots cover their subtree; wildcard roots match a basename
    glob in one directory (`*` never crosses `/`), like the sparse
    patterns that must check the file out.
    """
    if not path.endswith(".py"):
        return False
    for root in LINT_ROOTS:
        if "*" in root:
            rdir, rbase = root.rsplit("/", 1)
            pdir, pbase = path.rsplit("/", 1)
            if pdir == rdir and fnmatch.fnmatchcase(pbase, rbase):
                return True
        elif path == root or path.startswith(root + "/"):
            return True
    return False


def ci_ruff_arguments():
    """The argument list of ci.yml's `ruff check --select F` command."""
    try:
        text = CI.read_text()
    except OSError as e:
        die(f"cannot read {CI}: {e}")
    m = re.search(r"ruff check --select F (.*?)(?=\n\s*\n|\Z)", text, re.S)
    if not m:
        die("no `ruff check --select F` command found in ci.yml")
    return re.sub(r"\\\s*\n\s*", " ", m.group(1)).split()


def main():
    argv = ci_ruff_arguments()
    if argv != LINT_ROOTS:
        print("::error::ci.yml's ruff arguments no longer equal "
              "scripts/check_lint_population.py LINT_ROOTS")
        print(f"  ci.yml:    {' '.join(argv)}")
        print(f"  LINT_ROOTS: {' '.join(LINT_ROOTS)}")
        print("update both (and the harness job's sparse cone) together")
        return 1
    intended = [p for p in tracked_files() if in_scope(p)]
    missing = [p for p in intended if not (ROOT / p).is_file()]
    for p in missing:
        print(f"::error::lint input missing from the sparse working tree: {p}")
    if missing:
        print(f"lint population preflight: {len(missing)} of {len(intended)} "
              f"tracked lint inputs missing; failing before ruff runs")
        return 1
    print(f"lint population preflight: all {len(intended)} tracked lint "
          f"inputs present for ruff")
    return 0


if __name__ == "__main__":
    sys.exit(main())

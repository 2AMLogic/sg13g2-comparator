#!/usr/bin/env python3
"""Tracked `sim/` evidence size budget (issue #132).

Measures committed *blob* bytes (``git ls-tree -rl <tree>``) -- never the
checked-out working tree, so a sparse checkout does not change the answer --
and enforces the growth contract recorded in ``sim/evidence-size-budget.json``:

* an evidence unit that existed at the baseline may not exceed its recorded
  baseline bytes (grandfathered at exactly that size);
* a *new* evidence unit may not exceed ``new_unit_ceiling_bytes``;
* all of ``sim/`` may not exceed ``total_ceiling_bytes``.

An evidence unit is ``sim/<bench>/<protected-dir>/<name>`` where the protected
dir is one of records, corners, netlist-snapshots, campaigns, reports (the
same set the append-only guard protects) and ``<name>`` is a run/campaign
directory or a record file.

Both initial allowances are 10% of the baseline ``sim/`` blob bytes rounded up
to the next MiB (``--emit-budget`` derives and prints the whole file). A
deliberate overage needs an exact entry in the budget's ``exceptions`` backed
by a ``spec/decision-records/*.md`` record that names the same path and
additional bytes in a fenced json block (see ``sim/README.md``). There is no
bypass flag or environment override.

Exit codes: 0 within budget, 1 budget violation or invalid budget/exception,
2 usage / git / measurement error, including a partial (blob-filtered) clone,
which is refused up front and never lazily fetched (never reported as success).

Stdlib only; needs ``git`` on PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys

BUDGET_PATH = "sim/evidence-size-budget.json"
RECORD_DIR = "spec/decision-records/"
PROTECTED_DIRS = ("records", "corners", "netlist-snapshots", "campaigns", "reports")
MIB = 1024 * 1024
POLICY_PERCENT = 10
KIND = "evidence-size"
TOTAL_KEY = "sim"
EXC_KEYS = {"path", "additional_bytes", "reason", "decision_record"}
SIZE_RE = re.compile(r"^[0-9]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
BUDGET_KEYS = {
    "version", "baseline", "allowance", "total_ceiling_bytes",
    "new_unit_ceiling_bytes", "units", "exceptions",
}


class MeasureError(Exception):
    """Git failed or sizes are missing/non-numeric (exit 2, fail closed)."""


class BudgetError(Exception):
    """Budget file or exception invalid (exit 1, fail closed)."""


def _git_env() -> dict:
    # Never lazily fetch a missing object from a promisor remote: in a
    # blob-filtered partial clone `ls-tree -l` would otherwise fetch every blob
    # one round trip at a time (CI run 38029844566 hung on ~97k of them). A
    # missing object must fail closed instead.
    return {**os.environ, "GIT_NO_LAZY_FETCH": "1"}


def git(repo: str, *args: str) -> bytes:
    try:
        p = subprocess.run(["git", "-C", repo, *args], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=False, env=_git_env())
    except OSError as exc:
        raise MeasureError(f"cannot run git: {exc}") from exc
    if p.returncode != 0:
        raise MeasureError(f"git {' '.join(args)} failed: "
                           f"{p.stderr.decode('utf-8', 'replace').strip()}")
    return p.stdout


_TRUE = {"true", "yes", "on", "1"}


def assert_complete_repo(repo: str) -> None:
    """Refuse a partial clone before reading any object (exit 2).

    A partial clone (``extensions.partialClone`` or a ``remote.<name>.promisor``
    remote, e.g. actions/checkout with ``sparse-checkout:`` which implies
    ``--filter=blob:none``) lacks blobs, so sizes are unavailable locally and
    git would lazily fetch them one by one. A *shallow* clone is not refused:
    it still holds every tree and blob of the commits it has, so a resolvable
    target tree is measured exactly (an unavailable one already exits 2).
    """
    try:
        p = subprocess.run(
            ["git", "-C", repo, "config", "--get-regexp",
             r"^(extensions\.partialclone|remote\..*\.promisor)$"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            env=_git_env())
    except OSError as exc:
        raise MeasureError(f"cannot run git: {exc}") from exc
    if p.returncode not in (0, 1):  # 1 = no matching key
        raise MeasureError("git config --get-regexp failed: "
                           f"{p.stderr.decode('utf-8', 'replace').strip()}")
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        key, _, val = line.partition(" ")
        if key == "extensions.partialclone" or val.strip().lower() in _TRUE:
            raise MeasureError(
                f"{repo} is a partial clone ({key} {val.strip()}); blob sizes "
                "are not available locally and would be lazily fetched one by "
                "one. Measure from a complete clone (no blob filter; in CI do "
                "not give actions/checkout a `sparse-checkout:` input for this "
                "job, which implies --filter=blob:none)")


def resolve_tree(repo: str, rev: str) -> str:
    if rev.startswith("-"):
        raise MeasureError(f"invalid revision {rev!r}")
    out = git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options",
              f"{rev}^{{tree}}").decode().strip()
    if not out:
        raise MeasureError(f"revision {rev!r} is unavailable")
    return out


def parse_ls_tree(raw: bytes) -> list[tuple[str, int]]:
    """Parse ``git ls-tree -rlz`` output into (path, blob bytes).

    Fails closed on any blob whose size is missing or non-numeric (which is
    what a blob-filtered partial clone would produce).
    """
    out = []
    for rec in raw.split(b"\0"):
        if not rec:
            continue
        meta, tab, name = rec.partition(b"\t")
        fields = meta.decode("utf-8", "replace").split()
        path = name.decode("utf-8", "surrogateescape")
        if not tab or len(fields) != 4:
            raise MeasureError(f"unparseable ls-tree record for {path!r}")
        _mode, typ, _oid, size = fields
        if typ == "commit":  # gitlink: no blob in this repository
            continue
        if typ != "blob" or not SIZE_RE.match(size):
            raise MeasureError(
                f"missing or non-numeric size {size!r} ({typ}) for {path!r}; "
                "the target tree must be measured with full object metadata "
                "(no blob filter)")
        out.append((path, int(size)))
    return out


def unit_of(path: str) -> str | None:
    parts = path.split("/")
    if len(parts) >= 4 and parts[0] == "sim" and parts[1] \
            and parts[2] in PROTECTED_DIRS and parts[3]:
        return "/".join(parts[:4])
    return None


def measure(repo: str, tree: str) -> dict:
    entries = parse_ls_tree(git(repo, "ls-tree", "-r", "-l", "-z", tree))
    if not entries:
        raise MeasureError(f"tree {tree} lists no blobs")
    m = {"repo_blobs": 0, "repo_bytes": 0, "sim_blobs": 0, "sim_bytes": 0,
         "units": {}}
    for path, size in entries:
        m["repo_blobs"] += 1
        m["repo_bytes"] += size
        if path.startswith("sim/"):
            m["sim_blobs"] += 1
            m["sim_bytes"] += size
            u = unit_of(path)
            if u:
                m["units"][u] = m["units"].get(u, 0) + size
    return m


def allowance_bytes(sim_bytes: int, percent: int = POLICY_PERCENT) -> int:
    """percent of sim_bytes rounded up to the next MiB (exact integer math)."""
    raw_num = sim_bytes * percent  # bytes * 100
    mib_num = MIB * 100
    return -(-raw_num // mib_num) * MIB


def build_budget(m: dict, commit: str) -> dict:
    a = allowance_bytes(m["sim_bytes"])
    return {
        "version": 1,
        "baseline": {
            "commit": commit,
            "accounting": "git ls-tree -rl <commit> blob bytes (not working tree, not pack size)",
            "repo_blobs": m["repo_blobs"], "repo_bytes": m["repo_bytes"],
            "sim_blobs": m["sim_blobs"], "sim_bytes": m["sim_bytes"],
        },
        "allowance": {
            "percent": POLICY_PERCENT,
            "operand_sim_bytes": m["sim_bytes"],
            "derivation": (f"ceil({POLICY_PERCENT}% x {m['sim_bytes']} B / {MIB} B/MiB)"
                           f" = {a // MIB} MiB"),
            "mib": a // MIB,
            "bytes": a,
        },
        "total_ceiling_bytes": m["sim_bytes"] + a,
        "new_unit_ceiling_bytes": a,
        "units": dict(sorted(m["units"].items())),
        "exceptions": [],
    }


def _canonical(path) -> bool:
    return (isinstance(path, str) and path != "" and not path.startswith("/")
            and "\0" not in path and "\\" not in path
            and not any(c in path for c in "*?[]{}!")
            and not path.endswith("/")
            and posixpath.normpath(path) == path
            and not {"..", "."} & set(path.split("/")))


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _blob(repo: str, tree: str, path: str) -> bytes | None:
    out = git(repo, "ls-tree", "-z", tree, "--", path)
    if not out:
        return None
    meta, _, name = out.rstrip(b"\0").partition(b"\t")
    mode, typ, _ = meta.decode().split(" ")
    if name.decode("utf-8", "surrogateescape") != path or typ != "blob" \
            or mode == "120000":
        return None
    return git(repo, "show", f"{tree}:{path}")


_FENCE = re.compile(r"```[ \t]*json[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.S | re.I)


def _record_authorizes(text: str, path: str, extra: int) -> bool:
    for m in _FENCE.finditer(text):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for it in data if isinstance(data, list) else [data]:
            if (isinstance(it, dict) and it.get("kind") == KIND
                    and it.get("path") == path
                    and it.get("additional_bytes") == extra
                    and _is_int(it.get("additional_bytes"))):
                return True
    return False


def validate_budget(repo: str, tree: str, b) -> dict:
    """Validate schema + derivation + exceptions. Returns {path: extra}."""
    if not isinstance(b, dict) or set(b) != BUDGET_KEYS or b["version"] != 1:
        raise BudgetError(f"{BUDGET_PATH}: keys must be exactly {sorted(BUDGET_KEYS)}"
                          " with version 1")
    base, al, units = b["baseline"], b["allowance"], b["units"]
    if not (isinstance(base, dict) and isinstance(base.get("commit"), str)
            and SHA_RE.match(base["commit"])
            and all(_is_int(base.get(k)) and base[k] >= 0
                    for k in ("repo_blobs", "repo_bytes", "sim_blobs", "sim_bytes"))):
        raise BudgetError("baseline block malformed")
    if not (isinstance(al, dict) and al.get("percent") == POLICY_PERCENT
            and al.get("operand_sim_bytes") == base["sim_bytes"]
            and al.get("bytes") == allowance_bytes(base["sim_bytes"])
            and al.get("mib") == al["bytes"] // MIB):
        raise BudgetError(
            f"allowance must be {POLICY_PERCENT}% of baseline sim bytes rounded up "
            "to the next MiB; changing the percentage or baseline needs a "
            "decision record and a reviewed change to scripts/check_evidence_size.py")
    if b["total_ceiling_bytes"] != base["sim_bytes"] + al["bytes"] \
            or b["new_unit_ceiling_bytes"] != al["bytes"]:
        raise BudgetError("ceilings do not equal baseline + allowance / allowance")
    if not isinstance(units, dict) or not all(
            unit_of(k) == k and _is_int(v) and v >= 0 for k, v in units.items()):
        raise BudgetError("units must map exact evidence-unit paths to byte counts")
    if not isinstance(b["exceptions"], list):
        raise BudgetError("exceptions must be a list")
    extras: dict[str, int] = {}
    for i, e in enumerate(b["exceptions"]):
        w = f"exceptions[{i}]"
        if not isinstance(e, dict) or set(e) != EXC_KEYS:
            raise BudgetError(f"{w}: keys must be exactly {sorted(EXC_KEYS)}")
        p, extra = e["path"], e["additional_bytes"]
        if not _canonical(p) or not (p == TOTAL_KEY or unit_of(p) == p):
            raise BudgetError(
                f"{w}.path {p!r} must be exactly 'sim' or one evidence unit "
                "sim/<bench>/<protected-dir>/<name> (no wildcards)")
        if p in extras:
            raise BudgetError(f"{w} duplicates path {p!r}")
        if not _is_int(extra) or extra <= 0:
            raise BudgetError(f"{w}.additional_bytes must be a positive integer")
        if not isinstance(e["reason"], str) or not e["reason"].strip():
            raise BudgetError(f"{w}.reason must be a nonempty string")
        rec = e["decision_record"]
        if not (isinstance(rec, str) and rec.startswith(RECORD_DIR)
                and rec.endswith(".md") and _canonical(rec)
                and "/" not in rec[len(RECORD_DIR):]):
            raise BudgetError(
                f"{w}.decision_record must be a spec/decision-records/*.md path")
        text = _blob(repo, tree, rec)
        if text is None:
            raise BudgetError(f"{w}: decision record {rec!r} is not a tracked "
                              "file in the target tree")
        if not _record_authorizes(text.decode("utf-8", "replace"), p, extra):
            raise BudgetError(
                f"{w}: {rec!r} has no fenced json block with "
                f'{{"kind": "{KIND}", "path": "{p}", "additional_bytes": {extra}}}')
        extras[p] = extra
    return extras


def evaluate(m: dict, b: dict, extras: dict) -> list[str]:
    route = ("route: add an exception to sim/evidence-size-budget.json backed by "
             "a spec/decision-records/*.md fenced json block "
             '{"kind": "evidence-size", "path": ..., "additional_bytes": ...}; '
             "see sim/README.md (\"Evidence size budget\")")
    v = []
    tot_ceiling = b["total_ceiling_bytes"] + extras.get(TOTAL_KEY, 0)
    if m["sim_bytes"] > tot_ceiling:
        v.append(f"sim: {m['sim_bytes']} B measured > total ceiling {tot_ceiling} B "
                 f"(over by {m['sim_bytes'] - tot_ceiling} B); {route}")
    for u in sorted(m["units"]):
        size = m["units"][u]
        if u in b["units"]:
            ceil, kind = b["units"][u] + extras.get(u, 0), "grandfathered baseline"
        else:
            ceil, kind = b["new_unit_ceiling_bytes"] + extras.get(u, 0), \
                "new-unit ceiling"
        if size > ceil:
            v.append(f"{u}: {size} B measured > {kind} {ceil} B "
                     f"(over by {size - ceil} B); {route}")
    return v


def load_budget(repo: str, tree: str):
    raw = _blob(repo, tree, BUDGET_PATH)
    if raw is None:
        raise BudgetError(f"{BUDGET_PATH} is not a tracked file in tree {tree}")
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BudgetError(f"{BUDGET_PATH} is not valid JSON: {exc}") from exc


def report(m: dict, b: dict, extras: dict) -> str:
    lines = [
        f"repo: {m['repo_blobs']} blobs, {m['repo_bytes']} B",
        f"sim:  {m['sim_blobs']} blobs, {m['sim_bytes']} B "
        f"(ceiling {b['total_ceiling_bytes'] + extras.get(TOTAL_KEY, 0)} B)",
        f"evidence units: {len(m['units'])} "
        f"({sum(1 for u in m['units'] if u not in b['units'])} new)",
    ]
    for u in sorted(m["units"]):
        tag = "baseline" if u in b["units"] else "new"
        lines.append(f"  {u}: {m['units'][u]} B [{tag}]")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tree", required=True,
                    help="commit or tree to measure (e.g. HEAD)")
    ap.add_argument("--repo", default=".", help="repository path (default .)")
    ap.add_argument("--emit-budget", metavar="COMMIT", default=None,
                    help="print a fresh budget file for the measured tree, "
                         "recording COMMIT as the baseline (does not enforce)")
    ap.add_argument("--quiet", action="store_true", help="omit per-unit listing")
    args = ap.parse_args(argv)
    try:
        assert_complete_repo(args.repo)
        tree = resolve_tree(args.repo, args.tree)
        m = measure(args.repo, tree)
        if args.emit_budget:
            print(json.dumps(build_budget(m, args.emit_budget), indent=2) + "\n", end="")
            return 0
        b = load_budget(args.repo, tree)
        extras = validate_budget(args.repo, tree, b)
    except MeasureError as exc:
        print(f"ERROR (measure): {exc}", file=sys.stderr)
        return 2
    except BudgetError as exc:
        print(f"FAIL (budget): {exc}", file=sys.stderr)
        return 1
    violations = evaluate(m, b, extras)
    if not args.quiet or violations:
        print(report(m, b, extras))
    if violations:
        print(f"FAIL: {len(violations)} evidence size violation(s) in {args.tree}:",
              file=sys.stderr)
        for line in violations:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"OK: tracked sim/ evidence within budget in {args.tree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

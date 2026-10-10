#!/usr/bin/env python3
"""Append-only guard for committed `sim/` evidence (issue #116).

Fails when a path under ``sim/<bench>/{records,corners,netlist-snapshots,
campaigns,reports}/`` that exists at ``--base`` is not present at ``--head``
with the same Git blob ID and mode. Aggregated characterization reports under
``sim/characterization/<report-id>/`` are protected the same way (issue #155).
Additions are always allowed. A move is a
deletion plus an addition (``--no-renames``), so moving evidence away fails on
the old path while moving something *into* a protected directory passes.

A deliberate, justified change needs an exact entry in
``sim/evidence-exceptions.json`` backed by a decision record under
``spec/decision-records/`` (see ``sim/README.md``). There is no bypass flag
and no environment override.

Exit codes: 0 clean, 1 evidence violation or invalid exception registry,
2 usage / git / revision error (never reported as success).

Stdlib only; needs ``git`` on PATH.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import sys

PROTECTED_DIRS = frozenset(
    {"records", "corners", "netlist-snapshots", "campaigns", "reports"}
)
AGGREGATE_ROOT = "characterization"
EXCEPTIONS_PATH = "sim/evidence-exceptions.json"
RECORD_DIR = "spec/decision-records/"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
ZERO_OID = re.compile(r"^0+$")
OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
MODE_RE = re.compile(r"^[0-7]{6}$")
ENTRY_KEYS = {
    "path", "old_oid", "old_mode", "new_oid", "new_mode",
    "decision_record", "reason",
}
TUPLE_KEYS = ("path", "old_oid", "old_mode", "new_oid", "new_mode")


class GitError(Exception):
    """Git failed or a revision is unavailable (exit 2)."""


class RegistryError(Exception):
    """Exception registry invalid (exit 1, fail closed)."""


def is_protected(path: str) -> bool:
    parts = path.split("/")
    if len(parts) >= 4 and parts[0] == "sim" and parts[1] == AGGREGATE_ROOT \
            and all(parts[2:]):
        # Aggregated characterization: sim/characterization/<report-id>/<file>
        return True
    return (
        len(parts) >= 4
        and parts[0] == "sim"
        and parts[1] != ""
        and parts[2] in PROTECTED_DIRS
    )


def git(repo: str, *args: str, check: bool = True) -> bytes:
    try:
        proc = subprocess.run(
            ["git", "-C", repo, *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    except OSError as exc:
        raise GitError(f"cannot run git: {exc}") from exc
    if check and proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {msg}")
    return proc.stdout if proc.returncode == 0 else b""


def resolve_tree(repo: str, rev: str, label: str) -> str:
    if rev.startswith("-"):
        raise GitError(f"invalid {label} revision {rev!r}")
    try:
        out = git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options",
                  f"{rev}^{{tree}}")
    except GitError as exc:
        raise GitError(f"{label} revision {rev!r} is unavailable: {exc}") from exc
    oid = out.decode().strip()
    if not oid:
        raise GitError(f"{label} revision {rev!r} is unavailable")
    return oid


def raw_diff(repo: str, base: str, head: str):
    """Yield (status, old_mode, new_mode, old_oid, new_oid, path)."""
    out = git(repo, "diff", "--raw", "-z", "--no-renames", "--no-abbrev",
              "--no-ext-diff", base, head, "--")
    fields = out.split(b"\0")
    i = 0
    while i < len(fields) and fields[i]:
        meta = fields[i].decode("utf-8", "replace")
        if not meta.startswith(":") or i + 1 >= len(fields):
            raise GitError(f"unparseable git diff output near {meta!r}")
        parts = meta[1:].split(" ")
        if len(parts) != 5:
            raise GitError(f"unparseable git diff record {meta!r}")
        old_mode, new_mode, old_oid, new_oid, status = parts
        path = fields[i + 1].decode("utf-8", "surrogateescape")
        yield status[:1], old_mode, new_mode, old_oid, new_oid, path
        i += 2


def head_blob(repo: str, head: str, path: str) -> bytes | None:
    """Return the blob at head:path, or None if absent / not a blob."""
    out = git(repo, "ls-tree", "-z", head, "--", path, check=False)
    if not out:
        return None
    meta, _, name = out.rstrip(b"\0").partition(b"\t")
    mode, typ, _oid = meta.decode().split(" ")
    if name.decode("utf-8", "surrogateescape") != path or typ != "blob" \
            or mode == "120000":
        return None
    return git(repo, "show", f"{head}:{path}")


def _canonical_path(path) -> bool:
    return (
        isinstance(path, str) and path != "" and not path.startswith("/")
        and "\0" not in path and "\\" not in path
        and not any(c in path for c in "*?[]")
        and not path.endswith("/")
        and posixpath.normpath(path) == path
        and ".." not in path.split("/")
        and "." not in path.split("/")
    )


def _opt_oid(v) -> bool:
    return v is None or (isinstance(v, str) and bool(OID_RE.match(v)))


def _opt_mode(v) -> bool:
    return v is None or (isinstance(v, str) and bool(MODE_RE.match(v)))


def _check_entry(e, idx: int) -> None:
    where = f"exceptions[{idx}]"
    if not isinstance(e, dict):
        raise RegistryError(f"{where} is not an object")
    if set(e) != ENTRY_KEYS:
        raise RegistryError(
            f"{where} keys must be exactly {sorted(ENTRY_KEYS)}, got {sorted(e)}")
    if not _canonical_path(e["path"]) or not is_protected(e["path"]):
        raise RegistryError(
            f"{where}.path {e['path']!r} is not an exact canonical protected path")
    if not (isinstance(e["old_oid"], str) and OID_RE.match(e["old_oid"])):
        raise RegistryError(f"{where}.old_oid invalid")
    if not (isinstance(e["old_mode"], str) and MODE_RE.match(e["old_mode"])):
        raise RegistryError(f"{where}.old_mode invalid")
    if not _opt_oid(e["new_oid"]) or not _opt_mode(e["new_mode"]):
        raise RegistryError(f"{where} new_oid/new_mode invalid")
    if (e["new_oid"] is None) != (e["new_mode"] is None):
        raise RegistryError(
            f"{where} new_oid and new_mode must both be null (deletion) or both set")
    if not isinstance(e["reason"], str) or not e["reason"].strip():
        raise RegistryError(f"{where}.reason must be a nonempty string")
    rec = e["decision_record"]
    if not (isinstance(rec, str) and rec.startswith(RECORD_DIR)
            and rec.endswith(".md") and _canonical_path(rec)
            and "/" not in rec[len(RECORD_DIR):]):
        raise RegistryError(
            f"{where}.decision_record must be a spec/decision-records/*.md path")


_FENCE = re.compile(r"```[ \t]*json[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.S | re.I)


def _record_tuples(text: str):
    for m in _FENCE.finditer(text):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict):
                yield tuple(it.get(k) for k in TUPLE_KEYS) \
                    if all(k in it for k in TUPLE_KEYS) else None


def load_exceptions(repo: str, head: str) -> list[dict]:
    raw = head_blob(repo, head, EXCEPTIONS_PATH)
    if raw is None:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RegistryError(f"{EXCEPTIONS_PATH} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"version", "exceptions"} \
            or data["version"] != 1 or not isinstance(data["exceptions"], list):
        raise RegistryError(
            f'{EXCEPTIONS_PATH} must be {{"version": 1, "exceptions": [...]}}')
    seen = set()
    for idx, e in enumerate(data["exceptions"]):
        _check_entry(e, idx)
        key = (e["path"], e["old_oid"], e["old_mode"], e["new_oid"], e["new_mode"])
        if key in seen or e["path"] in {s[0] for s in seen}:
            raise RegistryError(f"exceptions[{idx}] duplicates path {e['path']!r}")
        seen.add(key)
        rec = head_blob(repo, head, e["decision_record"])
        if rec is None:
            raise RegistryError(
                f"exceptions[{idx}] decision record {e['decision_record']!r} "
                "is not a tracked file in the head tree")
        want = tuple(e[k] for k in TUPLE_KEYS)
        if want not in set(_record_tuples(rec.decode("utf-8", "replace"))):
            raise RegistryError(
                f"exceptions[{idx}] decision record {e['decision_record']!r} has no "
                f"fenced json block authorizing exactly {dict(zip(TUPLE_KEYS, want))}")
    return data["exceptions"]


def check(repo: str, base: str, head: str) -> list[str]:
    """Return violation messages; raise GitError / RegistryError."""
    base_t = resolve_tree(repo, base, "base")
    head_t = resolve_tree(repo, head, "head")
    exceptions = load_exceptions(repo, head_t)
    allowed = {
        (e["path"], e["old_oid"], e["old_mode"], e["new_oid"], e["new_mode"])
        for e in exceptions
    }
    violations = []
    for status, om, nm, oo, no, path in raw_diff(repo, base_t, head_t):
        if status == "A" or not is_protected(path):
            continue
        deleted = status == "D"
        new_oid = None if deleted else no
        new_mode = None if deleted else nm
        if (path, oo, om, new_oid, new_mode) in allowed:
            continue
        if deleted:
            what = "deleted (or moved away)"
        elif status == "T":
            what = f"type changed {om} -> {nm}"
        elif oo == no:
            what = f"mode changed {om} -> {nm}"
        else:
            what = "modified"
        violations.append(f"{path}: {what}")
    return violations


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="base commit (or tree)")
    ap.add_argument("--head", required=True, help="head commit (or tree)")
    ap.add_argument("--repo", default=".", help="repository path (default .)")
    args = ap.parse_args(argv)
    try:
        violations = check(args.repo, args.base, args.head)
    except GitError as exc:
        print(f"ERROR (git): {exc}", file=sys.stderr)
        return 2
    except RegistryError as exc:
        print(f"FAIL (exception registry): {exc}", file=sys.stderr)
        return 1
    if violations:
        print(f"FAIL: {len(violations)} protected evidence path(s) changed "
              f"between {args.base} and {args.head}:", file=sys.stderr)
        for v in violations:
            print(f"  {v!r}", file=sys.stderr)
        print("sim/ evidence is append-only; see sim/README.md "
              "(\"Append-only evidence guard\").", file=sys.stderr)
        return 1
    print(f"OK: no protected sim/ evidence modified between "
          f"{args.base} and {args.head}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Fresh-render parity check for the T1 signoff manifest.

`manifests/sg13g2-comparator.json` is this block's `klt signoff --manifest`
block manifest, and `manifests/t1-signoff-report.json` is the rendered report
frozen at this repo's pinned `klt` build, `2AMLogic/klayout-tools` @
3a75c3ae705b7ad3803625255de93bcd982e70c6 (see `manifests/README.md`). This
script re-renders the report from the manifest right now and refuses to let
the frozen one rot:

  exit 0   fresh render succeeded (exit 0 or 3 -- both are clean runs, see
           below) AND equals the committed report semantically.
  exit 1   anything else: the render errored (exit 1), OR the fresh
           output diverges from the committed report.

Exit 3 from `klt signoff --manifest` means "report rendered fine, the block
is not yet at tier T1" -- that is this repo's *expected* state and NOT a
failure of this check. The day a cited artifact's input revision moves
(hash-pin mismatch) the affected item flips to `unmet`/`stale_evidence` in
the fresh render, which then no longer equals the committed report -- exactly
the failure this check exists to catch, per issue #37's "CI re-runs it, so a
manifest citing an artifact that has since changed fails rather than rotting"
acceptance criterion. A report frozen against a different `klt` build (a
`build` block mismatch), a moved checklist (`source_doc_content_hash`
mismatch), or a regenerated evidence file all fail the same way: the
manifest, its cited artifacts, and the frozen report move together in one
change, visibly, or not at all.

Zero dependencies beyond the Python 3 standard library and a working `klt`
on `$PATH` (or `--klt <path>`).

Usage:
    python3 scripts/check_signoff_report.py
    python3 scripts/check_signoff_report.py --klt /path/to/pinned/klt
Exit codes: 0 parity holds, 1 it does not (or the render failed).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "manifests" / "sg13g2-comparator.json"
DEFAULT_REPORT = REPO_ROOT / "manifests" / "t1-signoff-report.json"

#: `klt signoff --manifest` uses 3 for "rendered, tier not reached"
#: (docs/cli/signoff.md -- the command exits 3, and that is the point)
#: and 0 for every T1 item met. 1 is an error envelope, never a graded
#: verdict.
_ACCEPTED_EXITS = (0, 3)


_ABSENT_FRESH = "<absent in fresh>"
_ABSENT_COMMITTED = "<absent in committed>"


def _node_type(value):
    """JSON node type; bool is deliberately distinct from number."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _reject_constant(name):
    raise ValueError(f"non-standard JSON constant {name} is not allowed")


def _parse_report(text):
    """Parse JSON, rejecting NaN/Infinity; the root must be an object."""
    value = json.loads(text, parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise ValueError(
            f"report root must be a JSON object, got {_node_type(value)}"
        )
    return value


def _walk(fresh, committed, path=""):
    """Yield (path, committed_value, fresh_value) for each difference.

    Node types are compared first, then object key sets and array lengths,
    then children / scalars. Objects are order-independent, arrays ordered.
    Empty containers are real nodes, so structural changes are visible.
    """
    ft, ct = _node_type(fresh), _node_type(committed)
    if ft != ct:
        yield (path or ".", committed, fresh)
        return
    if ft == "object":
        for key in sorted(set(fresh) | set(committed)):
            sub = f"{path}.{key}"
            if key not in committed:
                yield (sub, _ABSENT_COMMITTED, fresh[key])
            elif key not in fresh:
                yield (sub, committed[key], _ABSENT_FRESH)
        for key in sorted(set(fresh) & set(committed)):
            yield from _walk(fresh[key], committed[key], f"{path}.{key}")
    elif ft == "array":
        if len(fresh) != len(committed):
            yield (
                f"{path or '.'}.length",
                len(committed),
                len(fresh),
            )
        for i in range(min(len(fresh), len(committed))):
            yield from _walk(fresh[i], committed[i], f"{path}[{i}]")
        for i in range(len(committed), len(fresh)):
            yield (f"{path}[{i}]", _ABSENT_COMMITTED, fresh[i])
        for i in range(len(fresh), len(committed)):
            yield (f"{path}[{i}]", committed[i], _ABSENT_FRESH)
    elif fresh != committed:
        yield (path or ".", committed, fresh)


def _first_differences(fresh, committed, limit=5):
    """Up to `limit` (path, committed, fresh) differences, bounded."""
    out = []
    for diff in _walk(fresh, committed):
        out.append(diff)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Re-render the T1 signoff manifest and require parity "
        "with the committed report (see manifests/README.md)."
    )
    ap.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="block manifest to grade (default: manifests/sg13g2-comparator.json)",
    )
    ap.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help="committed report to compare against "
        "(default: manifests/t1-signoff-report.json)",
    )
    ap.add_argument(
        "--klt",
        default="klt",
        help="klt executable (default: 'klt' from $PATH; use the pinned "
        "build from manifests/README.md for a locally faithful re-render)",
    )
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    report_path = Path(args.report)
    if not manifest_path.is_file():
        print(f"FAIL: manifest {manifest_path} does not exist", file=sys.stderr)
        return 1
    if not report_path.is_file():
        print(f"FAIL: committed report {report_path} does not exist", file=sys.stderr)
        return 1

    proc = subprocess.run(
        [args.klt, "signoff", "--manifest", str(manifest_path), "--format", "json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    if proc.returncode not in _ACCEPTED_EXITS:
        # `klt signoff` exit 1 is an error envelope (unreadable evidence,
        # bad manifest, unknown flag), never a graded verdict -- surface it
        # verbatim rather than guessing.
        print(
            f"FAIL: klt signoff exited {proc.returncode} (accepted: "
            f"{list(_ACCEPTED_EXITS)}; exit 3 = 'rendered, tier not "
            "reached' and is NOT a failure of this check):",
            file=sys.stderr,
        )
        for stream_name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            text = (stream or "").strip()
            if text:
                print(f"  {stream_name}: {text[:2000]}", file=sys.stderr)
        return 1

    try:
        fresh = _parse_report(proc.stdout)
    except ValueError as exc:
        print(
            f"FAIL: klt signoff exited {proc.returncode} but its stdout is "
            f"not a valid JSON report object ({exc}): {proc.stdout[:500]!r}",
            file=sys.stderr,
        )
        return 1

    try:
        committed = _parse_report(report_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(
            f"FAIL: committed report {report_path} is not a valid JSON "
            f"report object ({exc})",
            file=sys.stderr,
        )
        return 1
    frozen_build = committed.get("build", {})

    diffs = _first_differences(fresh, committed)
    if diffs:
        print(
            "FAIL: fresh render of the T1 signoff manifest diverges from the "
            "committed report -- regenerate the report in the same change "
            "that moved the manifest/evidence (see manifests/README.md):",
            file=sys.stderr,
        )
        for key, committed_value, fresh_value in diffs:
            print(
                f"  {key}: committed {json.dumps(committed_value)[:160]} "
                f"-> fresh {json.dumps(fresh_value)[:160]}",
                file=sys.stderr,
            )
        fb = fresh.get("build", {})
        if (
            fb.get("version")
            and frozen_build.get("version")
            and fb.get("version") != frozen_build.get("version")
        ):
            print(
                f"note: fresh build {fb.get('version')!r} vs frozen "
                f"{frozen_build.get('version')!r} -- a build-block mismatch "
                "is itself a divergence: re-render with the pinned klt from "
                "manifests/README.md",
                file=sys.stderr,
            )
        return 1

    print(
        f"OK: fresh render matches the committed T1 signoff report "
        f"(klt signoff exit {proc.returncode}; "
        f"tier={fresh.get('tier')!r}, "
        f"t1_met={fresh.get('t1_met_count')}/{fresh.get('t1_item_count')} "
        f"item rows, build={fresh.get('build', {}).get('version')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

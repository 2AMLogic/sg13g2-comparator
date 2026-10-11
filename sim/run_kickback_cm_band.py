#!/usr/bin/env python3
"""Kickback residue across a bounded input common-mode band (issue #165).

    python3 sim/run_kickback_cm_band.py build   --series ID [--condition C ...]
    python3 sim/run_kickback_cm_band.py run     --series ID --condition C [--klt KLT]
    python3 sim/run_kickback_cm_band.py smoke   --condition C --osdi-dir DIR [--klt KLT]
    python3 sim/run_kickback_cm_band.py compare --series ID

Conditions: vcm-m050 (dut_vcm - 50 mV), vcm-nom (dut_vcm; reproduction gate),
vcm-p050 (dut_vcm + 50 mV). Each is ONE deterministic 45-point `klt sim`
request (backend: batch, so the grid runs on the batch fleet) under
sim/comparator-kickback-cm-band/campaigns/ID/<condition>/. Evidence is
append-only: `build` refuses to change an existing input, `run` refuses to
resubmit a part whose envelope exists or whose attempt log already records a
graded run. A failed batch submit is reported, never run locally. `smoke`
runs ONE corner locally (a debug probe) in a scratch dir, writing nothing
under sim/. `compare` writes ID/comparison.json + comparison.md offline from
the saved envelopes.

See sim/kltsim/kickback_cmband.py and sim/comparator-kickback-cm-band/README.md.
Run from the repository root.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim import build as build_mod  # noqa: E402
from kltsim import cli as kcli  # noqa: E402
from kltsim import kickback_cmband as kb  # noqa: E402


def _series(args) -> Path:
    return kb.SERIES_DIR / args.series


def _extra(cond: kb.Condition) -> dict:
    return {"condition": kb.condition_metadata(cond), "kind": "campaign"}


def cmd_build(args) -> int:
    for name in args.condition or [c.name for c in kb.CONDITIONS]:
        cond = kb.condition(name)
        try:
            paths = kb.write_condition_inputs(cond, _series(args) / cond.name)
        except kb.KickbackCmBandError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        for p in paths:
            print(f"wrote {p.relative_to(build_mod.REPO_ROOT)}")
    return 0


def _submit_with_retry(request: Path, out_dir: Path, tag: str, args, extra: dict) -> int:
    code = 1
    for attempt in range(1, args.retry_refused + 2):
        code = kcli._submit(request, out_dir, tag, args, extra=extra)
        if code == 0 or not kcli._last_attempt_refused_at_cap(out_dir):
            break
        if attempt <= args.retry_refused:
            print(f"{tag}: fleet at its instance cap; retry {attempt}/{args.retry_refused} "
                  f"in {args.retry_wait}s", file=sys.stderr)
            time.sleep(args.retry_wait)
    return code


def _graded_attempts(out_dir: Path, tag: str) -> int:
    log = out_dir / "attempts.jsonl"
    if not log.is_file():
        return 0
    n = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("tag") == tag and rec.get("exit_code") in (0, 3, 4):
            n += 1
    return n


def cmd_run(args) -> int:
    cond = kb.condition(args.condition)
    out_dir = _series(args) / cond.name
    request = out_dir / f"{kb.TAG}.request.json"
    if not request.is_file():
        print(f"no request at {request}; run `build` first", file=sys.stderr)
        return 1
    if (out_dir / f"{kb.TAG}.envelope.json").exists():
        print(f"{kb.TAG}: envelope present -- append-only, not resubmitted", file=sys.stderr)
        return 0 if args.skip_existing else 1
    if _graded_attempts(out_dir, kb.TAG):
        print(f"{kb.TAG}: attempts.jsonl already records a graded run but no envelope was "
              "saved; refusing to resubmit (investigate; do not overwrite evidence)", file=sys.stderr)
        return 1
    return _submit_with_retry(request, out_dir, kb.TAG, args, _extra(cond))


def cmd_smoke(args) -> int:
    cond = kb.condition(args.condition)
    work = Path(args.work or tempfile.mkdtemp(prefix=f"kbcm-smoke-{cond.name}-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    (work / kb.BODY_NAME).write_text(kb.compose_body(cond, args.osdi_dir), encoding="utf-8")
    req = kb.compose_request(cond, kb.BODY_NAME, backend="local")
    req["corners"]["process"] = [args.process]
    req["corners"]["supply_v"] = {"vsup": [args.supply]}
    req["corners"]["temperature_c"] = [args.temperature]
    request = work / "request.json"
    request.write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")
    cmd = [args.klt, "sim", str(request), "--backend", "local", "--format", "json",
           "-o", str(work / "artifacts")]
    print("$ " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    (work / "envelope.json").write_text(proc.stdout, encoding="utf-8")
    print(f"klt sim exit {proc.returncode}; work dir {work}", file=sys.stderr)
    if proc.stderr.strip():
        print(proc.stderr.strip()[-2000:], file=sys.stderr)
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return 1
    for c in env.get("corners", []):
        print(c["corner_id"], c["status"], {m["name"]: m["value"] for m in c["measurements"]})
    return 0


def cmd_compare(args) -> int:
    series = _series(args)
    result = kb.compare_series(series, kb.REFERENCE_DIR)
    (series / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (series / "comparison.md").write_text(kb.render_markdown(result), encoding="utf-8")
    r = result["reproduction"]
    print(f"reproduction: {'PASS' if r['ok'] else 'FAIL'} "
          f"({r['values_compared']}/{r['expected_values']} values, "
          f"{len(r['mismatches'])} mismatches, {len(r['problems'])} problems)")
    for name, c in result["conditions"].items():
        ru = c["residue_uv"]
        print(f"{name}: {c['points_valid']}/{c['points_expected']} valid, residue "
              f"{ru['min']} .. {ru['max']} uV, Target {c['verdict']['target']}, "
              f"Stretch {c['verdict']['stretch']}")
    return 0 if r["ok"] else 2


def main(argv: list[str] | None = None) -> int:
    default_klt = shutil.which("klt") or "klt"
    names = [c.name for c in kb.CONDITIONS]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--series", required=True)
    b.add_argument("--condition", action="append", choices=names)
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("run")
    r.add_argument("--series", required=True)
    r.add_argument("--condition", required=True, choices=names)
    r.add_argument("--skip-existing", action="store_true")
    r.add_argument("--klt", default=default_klt)
    r.add_argument("--retry-refused", type=int, default=0)
    r.add_argument("--retry-wait", type=int, default=120)
    r.set_defaults(func=cmd_run, force=False)

    s = sub.add_parser("smoke")
    s.add_argument("--condition", required=True, choices=names)
    s.add_argument("--osdi-dir", required=True)
    s.add_argument("--process", default="mos_tt")
    s.add_argument("--supply", type=float, default=1.2)
    s.add_argument("--temperature", type=float, default=27)
    s.add_argument("--work")
    s.add_argument("--klt", default=default_klt)
    s.set_defaults(func=cmd_smoke)

    g = sub.add_parser("compare")
    g.add_argument("--series", required=True)
    g.set_defaults(func=cmd_compare)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

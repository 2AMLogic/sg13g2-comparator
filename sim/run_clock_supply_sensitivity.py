#!/usr/bin/env python3
"""Clock-edge, strobe-width and supply-disturbance sensitivity (issue #173).

    python3 sim/run_clock_supply_sensitivity.py build   --series ID [--condition C ...]
    python3 sim/run_clock_supply_sensitivity.py run     --series ID [--kind regen|offset] [--condition C ...] [--klt KLT]
    python3 sim/run_clock_supply_sensitivity.py smoke   --kind K --condition C --osdi-dir DIR [--klt KLT]
    python3 sim/run_clock_supply_sensitivity.py compare --series ID [--report-dir DIR] [--check]

Nine conditions x two benches (regen: 45-point PVT grid; offset: 5 process x
{1.08, 1.32} V x {-40, 125} C, N = 16 paired draws) = 18 ``klt sim`` requests
on the batch fleet, under
sim/comparator-clock-supply-sensitivity/campaigns/ID/<condition>/. ``smoke``
runs ONE corner (offset: one draw) locally in a scratch directory and writes
nothing under sim/. See sim/kltsim/clocksupply.py and
sim/comparator-clock-supply-sensitivity/README.md. Run from the repository root.
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

from kltsim import artifacts as artifacts_mod  # noqa: E402
from kltsim import build as build_mod  # noqa: E402
from kltsim import cli as kcli  # noqa: E402
from kltsim import clocksupply as cs  # noqa: E402
from kltsim import clocksupply_report as rep  # noqa: E402

KINDS = ("regen", "offset")


def _series(args) -> Path:
    return cs.SERIES_DIR / args.series


def _conds(args):
    return [cs.condition(n) for n in (args.condition or [c.name for c in cs.CONDITIONS])]


def _kinds(args):
    return [args.kind] if args.kind else list(KINDS)


def cmd_build(args) -> int:
    files = []
    for c in _conds(args):
        for kind in _kinds(args):
            files += cs.write_inputs(kind, c, _series(args) / c.name)
    created = build_mod.commit_inputs(files)
    for p in created:
        print(f"wrote {p.relative_to(build_mod.REPO_ROOT)}")
    return 0


def cmd_run(args) -> int:
    rc = 0
    for c in _conds(args):
        out_dir = _series(args) / c.name
        for kind in _kinds(args):
            tag = f"{kind}.{c.name}"
            request = out_dir / f"{tag}.request.json"
            if not request.is_file():
                print(f"no request at {request}; run `build` first", file=sys.stderr)
                return 1
            if (out_dir / f"{tag}.envelope.json").exists():
                print(f"{tag}: envelope present, skipped", file=sys.stderr)
                continue
            code = 1
            for attempt in range(1, args.retry_refused + 2):
                code = kcli._submit(request, out_dir, tag, args, extra={"condition": c.metadata(), "kind": kind})
                if code == 0 or not kcli._last_attempt_refused_at_cap(out_dir):
                    break
                if attempt <= args.retry_refused:
                    print(f"{tag}: fleet at its instance cap; retry {attempt}/{args.retry_refused} "
                          f"in {args.retry_wait}s", file=sys.stderr)
                    time.sleep(args.retry_wait)
            rc = max(rc, code)
    return rc


def cmd_smoke(args) -> int:
    c = cs.condition(args.condition)
    work = Path(args.work or tempfile.mkdtemp(prefix=f"cs-smoke-{args.kind}-{c.name}-"))
    work.mkdir(parents=True, exist_ok=True)
    body_name = f"{args.kind}.{c.name}.body.spice"
    (work / body_name).write_text(cs.compose_body(args.kind, c, args.osdi_dir), encoding="utf-8")
    req = cs.compose_request(args.kind, c, body_name, backend="local")
    req["corners"]["process"] = [args.process or req["corners"]["process"][0]]
    req["corners"]["supply_v"] = {k: [args.supply] for k in req["corners"]["supply_v"]}
    req["corners"]["temperature_c"] = [args.temperature]
    if "monte_carlo" in req:
        req["monte_carlo"]["n"] = 1
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
    for corner in env.get("corners", []):
        print(corner["corner_id"], corner["status"],
              {m["name"]: m["value"] for m in corner["measurements"]})
    return 0


def cmd_compare(args) -> int:
    series = _series(args)
    result = rep.compare_series(series)
    report_dir = Path(args.report_dir) if args.report_dir else series
    md = rep.render_markdown(result)
    if report_dir != series:
        result["source_series_dir"] = kcli._cite(series)
        md = kcli._cite_note(md, "series", series)
    rc = artifacts_mod.publish(
        "compare",
        [(report_dir / "comparison.json", (json.dumps(result, indent=2) + "\n").encode("utf-8")),
         (report_dir / "comparison.md", md.encode("utf-8"))],
        check_only=args.check, namespace_hint=kcli._NAMESPACE_HINT.replace("--campaign/--series", "--series"),
        require_dir=report_dir)
    if rc == 0 and not args.check:
        print(f"comparison reports preserved under {report_dir}")
    return rc


def main(argv: list[str] | None = None) -> int:
    default_klt = shutil.which("klt") or "klt"
    names = [c.name for c in cs.CONDITIONS]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--series", required=True)
    b.add_argument("--condition", action="append", choices=names)
    b.add_argument("--kind", choices=KINDS)
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("run")
    r.add_argument("--series", required=True)
    r.add_argument("--condition", action="append", choices=names)
    r.add_argument("--kind", choices=KINDS)
    r.add_argument("--klt", default=default_klt)
    r.add_argument("--retry-refused", type=int, default=0)
    r.add_argument("--retry-wait", type=int, default=120)
    r.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("smoke")
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--condition", required=True, choices=names)
    s.add_argument("--osdi-dir", required=True)
    s.add_argument("--process")
    s.add_argument("--supply", type=float, default=1.2)
    s.add_argument("--temperature", type=float, default=27)
    s.add_argument("--work")
    s.add_argument("--klt", default=default_klt)
    s.set_defaults(func=cmd_smoke)

    g = sub.add_parser("compare")
    g.add_argument("--series", required=True)
    g.add_argument("--report-dir", help="write comparison.{json,md} here instead of the series "
                   "directory (new directory; cites the series; different existing files are "
                   "never overwritten)")
    g.add_argument("--check", action="store_true",
                   help="read-only: exit 1 if the reports are missing, stale or unsafe")
    g.set_defaults(func=cmd_compare)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

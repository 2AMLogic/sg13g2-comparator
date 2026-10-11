#!/usr/bin/env python3
"""Decision time / metastability across a bounded input common-mode band (issue #164).

    python3 sim/run_decision_cm_band.py build   --series ID [--condition C ...]
    python3 sim/run_decision_cm_band.py run     --series ID --condition C [--klt KLT]
    python3 sim/run_decision_cm_band.py compare --series ID

Conditions: vcm-m050, vcm-nom (reproduction gate), vcm-p050. Each is one
campaign under sim/comparator-decision-cm-band/campaigns/ID/<condition>/: one
body, one 45-point request (backend: batch, so the grid goes to the batch
fleet), its envelope, invocation and every attempt. ``run`` refuses to
resubmit a part whose envelope exists (append-only); ``--skip-existing``
makes that a quiet skip. Run from the repository root.
See sim/kltsim/cmdecision.py and sim/comparator-decision-cm-band/README.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim import build as build_mod  # noqa: E402
from kltsim import cli as kcli  # noqa: E402
from kltsim import cmdecision as cd  # noqa: E402


def _series(args) -> Path:
    return cd.SERIES_DIR / args.series


def cmd_build(args) -> int:
    for name in args.condition or [c.name for c in cd.CONDITIONS]:
        out = _series(args) / name
        for p in (out / cd.BODY_NAME, out / cd.REQUEST_NAME):
            if p.exists():
                print(f"{p} exists -- append-only; use a new --series", file=sys.stderr)
                return 1
        body, req = cd.write_condition_inputs(cd.condition(name), out)
        print(f"wrote {body.relative_to(build_mod.REPO_ROOT)}")
        print(f"wrote {req.relative_to(build_mod.REPO_ROOT)}")
    return 0


def cmd_run(args) -> int:
    cond = cd.condition(args.condition)
    out_dir = _series(args) / cond.name
    request = out_dir / cd.REQUEST_NAME
    if not request.is_file():
        print(f"no request at {request}; run `build` first", file=sys.stderr)
        return 1
    if (out_dir / f"{cd.TAG}.envelope.json").exists() and args.skip_existing:
        print(f"{cd.TAG}: envelope present, skipped", file=sys.stderr)
        return 0
    extra = {"condition": cd.condition_metadata(cond), "kind": "campaign"}
    code = 1
    for attempt in range(1, args.retry_refused + 2):
        code = kcli._submit(request, out_dir, cd.TAG, args, extra=extra)
        if code == 0 or not kcli._last_attempt_refused_at_cap(out_dir):
            break
        if attempt <= args.retry_refused:
            print(f"fleet at its instance cap; retry {attempt}/{args.retry_refused} "
                  f"in {args.retry_wait}s", file=sys.stderr)
            time.sleep(args.retry_wait)
    return code


def cmd_compare(args) -> int:
    series = _series(args)
    result = cd.compare_series(series, reference_campaign=args.reference_campaign)
    (series / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (series / "comparison.md").write_text(cd.render_markdown(result), encoding="utf-8")
    for name, c in result["conditions"].items():
        if c.get("missing"):
            print(f"{name}: not run")
            continue
        print(f"{name}: {c['points_valid']}/{c['points_expected']} valid, "
              f"{len(c['rejected'])} rejected, "
              + ", ".join(f"{q} {g['min']:.4g}..{g['max']:.4g}" for q, g in c["grid"].items()))
    rep = result.get("reproduction")
    if rep:
        print(f"vcm-nom reproduction: bit_identical={rep['bit_identical']} "
              f"({len(rep['mismatches'])} mismatches)")
    return 0


def main(argv: list[str] | None = None) -> int:
    default_klt = shutil.which("klt") or "klt"
    names = [c.name for c in cd.CONDITIONS]
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
    r.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    r.set_defaults(func=cmd_run)
    g = sub.add_parser("compare")
    g.add_argument("--series", required=True)
    g.add_argument("--reference-campaign", default=cd.REFERENCE_CAMPAIGN)
    g.set_defaults(func=cmd_compare)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

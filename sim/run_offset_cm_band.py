#!/usr/bin/env python3
"""Whole-latch offset across a bounded input common-mode band (issue #79).

    python3 sim/run_offset_cm_band.py build   --series ID [--condition C ...]
    python3 sim/run_offset_cm_band.py run     --series ID --condition C [--klt KLT]
    python3 sim/run_offset_cm_band.py control --series ID --condition C [--klt KLT]
    python3 sim/run_offset_cm_band.py repeat  --series ID --condition C --process SECTION
    python3 sim/run_offset_cm_band.py smoke   --condition C --osdi-dir DIR [--klt KLT]
    python3 sim/run_offset_cm_band.py compare --series ID

Conditions: vcm-m050 (dut_vcm - 50 mV), vcm-nom (dut_vcm), vcm-p050
(dut_vcm + 50 mV). Each condition is one campaign under
sim/comparator-offset-cm-band/campaigns/ID/<condition>/: one body, five
per-process requests (backend: batch, so the grid runs on the batch fleet),
their envelopes, invocations and every attempt. ``control`` submits the
mismatch-off negative control (plain mos_tt, one PVT point) for a
condition; ``repeat`` resubmits the first grid point of one process at full
N as a same-seed repeatability check; both land in ID/controls/. ``smoke``
runs ONE corner, N = 1, locally (a debug probe) in a scratch dir and writes
nothing under sim/. ``compare`` writes ID/comparison.json + comparison.md.

See sim/kltsim/cmband.py and sim/comparator-offset-cm-band/README.md.
Run from the repository root.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim import build as build_mod  # noqa: E402
from kltsim import cli as kcli  # noqa: E402
from kltsim import cmband  # noqa: E402
from kltsim.benches import OFFSET_MC, SUPPLIES_V, TEMPERATURES_C  # noqa: E402


def _series(args) -> Path:
    return cmband.SERIES_DIR / args.series


def _extra(cond: cmband.Condition, kind: str) -> dict:
    return {"condition": cmband.condition_metadata(cond), "kind": kind}


def cmd_build(args) -> int:
    for name in args.condition or [c.name for c in cmband.CONDITIONS]:
        cond = cmband.condition(name)
        body, requests = cmband.write_condition_inputs(cond, _series(args) / cond.name)
        print(f"wrote {body.relative_to(build_mod.REPO_ROOT)}")
        for r in requests:
            print(f"wrote {r.relative_to(build_mod.REPO_ROOT)}")
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
            import time
            time.sleep(args.retry_wait)
    return code


def cmd_run(args) -> int:
    cond = cmband.condition(args.condition)
    out_dir = _series(args) / cond.name
    rc = 0
    for tag in cmband.part_tags():
        if args.part and tag not in args.part:
            continue
        request = out_dir / f"{tag}.request.json"
        if not request.is_file():
            print(f"no request at {request}; run `build` first", file=sys.stderr)
            return 1
        if (out_dir / f"{tag}.envelope.json").exists() and args.skip_existing:
            print(f"{tag}: envelope present, skipped", file=sys.stderr)
            continue
        rc = max(rc, _submit_with_retry(request, out_dir, tag, args, _extra(cond, "campaign")))
    return rc


def _reduced_request(cond: cmband.Condition, out_dir: Path, tag: str, *, section: str,
                     supply: float, temperature: float, n: int, note: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    body_name = f"{cmband.BENCH_NAME}.{cond.name}.body.spice"
    (out_dir / body_name).write_text(
        cmband.compose_cm_body(cond, build_mod.BATCH_OSDI_DIR), encoding="utf-8")
    req = cmband.compose_cm_request(cond, body_name, section)
    req["corners"]["process"] = [section]
    req["corners"]["supply_v"] = {k: [supply] for k in OFFSET_MC.supply_keys}
    req["corners"]["temperature_c"] = [temperature]
    req["monte_carlo"]["n"] = n
    req["_comment"].append(note)
    path = out_dir / f"{tag}.request.json"
    path.write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")
    return path


def cmd_control(args) -> int:
    cond = cmband.condition(args.condition)
    out_dir = _series(args) / "controls"
    tag = f"negctrl.{cond.name}"
    if (out_dir / f"{tag}.envelope.json").exists():
        print(f"{tag}: envelope present (append-only)", file=sys.stderr)
        return 1
    request = _reduced_request(
        cond, out_dir, tag, section=args.process, supply=args.supply,
        temperature=args.temperature, n=args.n,
        note=(f"MISMATCH-OFF NEGATIVE CONTROL: plain `{args.process}` section, so every "
              "sample must report the same offset (sigma = 0). Not spec evidence."))
    return _submit_with_retry(request, out_dir, tag, args, _extra(cond, "negative-control"))


def cmd_repeat(args) -> int:
    cond = cmband.condition(args.condition)
    out_dir = _series(args) / "controls"
    tag = f"repeat.{cond.name}.{args.process}"
    if (out_dir / f"{tag}.envelope.json").exists():
        print(f"{tag}: envelope present (append-only)", file=sys.stderr)
        return 1
    # The FIRST grid point of the per-process request (lowest supply, lowest
    # temperature) is corner_index 0 there and here, so klt derives the same
    # per-sample seeds: a same-seed repeat of the campaign's draws.
    request = _reduced_request(
        cond, out_dir, tag, section=args.process, supply=SUPPLIES_V[0],
        temperature=TEMPERATURES_C[0], n=OFFSET_MC.monte_carlo["n"],
        note=("SAME-SEED REPEAT: the campaign's first grid point of this process (corner "
              "index 0 in both requests), full N, resubmitted as a separate batch job; every "
              "draw must reproduce the campaign's. Not additional spec evidence."))
    return _submit_with_retry(request, out_dir, tag, args, _extra(cond, "same-seed-repeat"))


def cmd_smoke(args) -> int:
    cond = cmband.condition(args.condition)
    work = Path(args.work or tempfile.mkdtemp(prefix=f"cmband-smoke-{cond.name}-"))
    body = work / cmband.BODY_NAME
    body.write_text(cmband.compose_cm_body(cond, args.osdi_dir), encoding="utf-8")
    req = cmband.compose_cm_request(cond, cmband.BODY_NAME, args.process, backend="local")
    req["corners"]["supply_v"] = {k: [args.supply] for k in OFFSET_MC.supply_keys}
    req["corners"]["temperature_c"] = [args.temperature]
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
    for c in env.get("corners", []):
        print(c["corner_id"], c["status"],
              {m["name"]: m["value"] for m in c["measurements"]})
    return 0


def cmd_compare(args) -> int:
    series = _series(args)
    result = cmband.compare_series(series, reference_campaign=args.reference_campaign,
                                   harness_record=cmband.HARNESS_RECORD)
    (series / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (series / "comparison.md").write_text(cmband.render_markdown(result), encoding="utf-8")
    for name, c in result["conditions"].items():
        t = c["three_sigma_mv"]
        print(f"{name}: {c['points_valid']}/{c['points_expected']} valid, clipped "
              f"{c['clipped_draws']}, 3sigma {t['min']} .. {t['max']} mV (mean {t['mean']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    default_klt = shutil.which("klt") or "klt"
    names = [c.name for c in cmband.CONDITIONS]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def submit_opts(p):
        p.add_argument("--klt", default=default_klt)
        p.add_argument("--retry-refused", type=int, default=0)
        p.add_argument("--retry-wait", type=int, default=120)
        p.add_argument("--force", action="store_true", help=argparse.SUPPRESS)

    b = sub.add_parser("build")
    b.add_argument("--series", required=True)
    b.add_argument("--condition", action="append", choices=names)
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("run")
    r.add_argument("--series", required=True)
    r.add_argument("--condition", required=True, choices=names)
    r.add_argument("--part", action="append", choices=cmband.part_tags())
    r.add_argument("--skip-existing", action="store_true")
    submit_opts(r)
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("control")
    c.add_argument("--series", required=True)
    c.add_argument("--condition", required=True, choices=names)
    c.add_argument("--process", default="mos_tt")
    c.add_argument("--supply", type=float, default=1.2)
    c.add_argument("--temperature", type=float, default=27)
    c.add_argument("--n", type=int, default=4)
    submit_opts(c)
    c.set_defaults(func=cmd_control)

    rp = sub.add_parser("repeat")
    rp.add_argument("--series", required=True)
    rp.add_argument("--condition", required=True, choices=names)
    rp.add_argument("--process", required=True, choices=list(OFFSET_MC.process_sections))
    submit_opts(rp)
    rp.set_defaults(func=cmd_repeat)

    s = sub.add_parser("smoke")
    s.add_argument("--condition", required=True, choices=names)
    s.add_argument("--osdi-dir", required=True)
    s.add_argument("--process", default="mos_tt_mismatch")
    s.add_argument("--supply", type=float, default=1.2)
    s.add_argument("--temperature", type=float, default=27)
    s.add_argument("--work")
    s.add_argument("--klt", default=default_klt)
    s.set_defaults(func=cmd_smoke)

    g = sub.add_parser("compare")
    g.add_argument("--series", required=True)
    g.add_argument("--reference-campaign", default=cmband.REFERENCE_CAMPAIGN)
    g.set_defaults(func=cmd_compare)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

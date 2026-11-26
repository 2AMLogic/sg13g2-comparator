#!/usr/bin/env python3
"""Kickback residue across a bounded input common-mode band (issue #165).

    python3 sim/run_kickback_cm_band.py build   --series ID [--condition C ...]
    python3 sim/run_kickback_cm_band.py run     --series ID --condition C [--klt KLT]
    python3 sim/run_kickback_cm_band.py smoke   --condition C --osdi-dir DIR [--klt KLT]
    python3 sim/run_kickback_cm_band.py compare --series ID
    python3 sim/run_kickback_cm_band.py probe-build   --series ID        (issue #405)
    python3 sim/run_kickback_cm_band.py probe-run     --series ID --condition C --arm A
    python3 sim/run_kickback_cm_band.py probe-compare --series ID

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

Probe supplements (never merged into the #165 populations): the frozen
`20261108-405-probe` series (issue #405) runs arms repro/obs/xing/step20p;
a series whose name contains `552` is the issue #552 cold-edge supplement and
runs the single `init` arm (a bench-only initialization phase that releases
before the 29 ns baseline; four-point summary from `probe-compare`); any other
series defaults to the issue #415 forced-DC supplement's arms
repro/obs/optdc/icdc, whose optdc/icdc bodies append a declared block to the
#165 body (sim/kltsim/kickback_cmband.py: probe_body_supplement).
probe-compare only ever writes into the series it is pointed at; it refuses
to rewrite the frozen #405 series in place with a non-#405 arm set
(`--report-dir NEW-DIR` publishes such an analysis in a new namespace).
`compare` and `probe-compare` write their `comparison.{json,md}` pair
append-only through `kltsim.artifacts.publish` (`--check` is the read-only
twin; `--report-dir` redirects into a new, citing namespace).

The probe subcommands accept `--root DIR` to place the series under a
staging root other than sim/comparator-kickback-cm-band/campaigns/ -- the
default is unchanged. Issue #552 uses it to stage its series in git-ignored
scratch (sim/.work/...) so the campaign bytes can be stored through the
manifest workflow (sim/run_store_evidence.py) instead of committed under
sim/: `probe-build`/`probe-run`/`probe-compare` there take
`--root sim/.work/<scratch>`.

See sim/kltsim/kickback_cmband.py and sim/comparator-kickback-cm-band/README.md.
Run from the repository root.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim import cli as kcli  # noqa: E402
from kltsim import kickback_cmband as kb  # noqa: E402

#: The frozen issue #405 probe series: default arm set, and the one series
#: probe-compare may rewrite with its own comparison files (AC: byte-unchanged).
FROZEN_PROBE_SERIES = "20261108-405-probe"


def _arms_for(series_name: str, chosen: list[str] | None) -> tuple[str, ...]:
    """Default arm set by series: the frozen #405 probe keeps its four arms;
    a #552 series (name contains kb.COLD_INIT_MARK) is the cold-edge
    initialized supplement; any other series is the issue #415 forced-DC
    supplement's arm set."""
    if chosen:
        return tuple(chosen)
    if series_name == FROZEN_PROBE_SERIES:
        return kb.PROBE_ARMS
    if kb.COLD_INIT_MARK in series_name:
        return kb.PROBE_ARMS_552
    return kb.PROBE_ARMS_415


def _issue_for(series_name: str) -> int:
    """The issue identity a series carries in its requests, invocations and
    comparisons: #405 for the frozen probe, #552 for a cold-edge series (name
    contains kb.COLD_INIT_MARK), #415 for every other supplement series."""
    if series_name == FROZEN_PROBE_SERIES:
        return kb.PROBE_ISSUE
    if kb.COLD_INIT_MARK in series_name:
        return kb.COLD_ISSUE
    return kb.SUPPLEMENT_ISSUE


def _series(args) -> Path:
    # ``--root`` stages the series under another root (issue #552 stores its
    # campaign bytes through sim/run_store_evidence.py, which requires
    # git-ignored scratch); absent or non-path-like (test Mocks) -> default.
    root = getattr(args, "root", None)
    if isinstance(root, (str, Path)) and root:
        return Path(root) / args.series
    return kb.SERIES_DIR / args.series


def _extra(cond: kb.Condition) -> dict:
    return {"condition": kb.condition_metadata(cond), "kind": "campaign"}


def cmd_build(args) -> int:
    # Plan every selected condition first, then commit the whole build as one
    # batch: a conflict on any condition writes nothing (no partial build).
    series = _series(args)
    planned: list[tuple[Path, bytes]] = []
    try:
        for name in args.condition or [c.name for c in kb.CONDITIONS]:
            cond = kb.condition(name)
            out_dir = series / cond.name
            files = kb.input_bytes(cond)
            planned.extend((out_dir / n, data) for n, data in files.items())
    except kb.KickbackCmBandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return kcli.commit_build("build", planned, evidence="campaign evidence")


def _retire_unrun_submit(out_dir: Path, tag: str) -> None:
    """A batch job that FAILED before running anything (e.g. runner/client klt
    mismatch: no corner measured) leaves an all-error envelope. Keep it, renamed
    with its fleet job id (never deleted), so the arm can be submitted again."""
    env_path = out_dir / f"{tag}.envelope.json"
    if not env_path.is_file():
        return
    env = json.loads(env_path.read_text(encoding="utf-8"))
    codes = (env.get("diagnostic_counts") or {}).get("by_code") or {}
    if env.get("status") != "error" or "batch_job_failed" not in codes or env.get("passed") \
            or env.get("failed"):
        return
    job = ((env.get("environment") or {}).get("remote") or {}).get("job_id") or "unknown"
    for suffix in ("envelope", "invocation"):
        src = out_dir / f"{tag}.{suffix}.json"
        if src.is_file():
            src.rename(out_dir / f"{tag}.{suffix}.unrun-{job}.json")
    print(f"{tag}: retired unrun failed submit {job} (kept as *.unrun-{job}.json)", file=sys.stderr)


def _graded_attempts(out_dir: Path, tag: str, unrun_ok: bool = False) -> int:
    log = out_dir / "attempts.jsonl"
    if not log.is_file():
        return 0
    n = 0
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("tag") == tag and rec.get("exit_code") in ((0, 3) if unrun_ok else (0, 3, 4)):
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
    return kcli._submit_with_retry(request, out_dir, kb.TAG, args, _extra(cond))


def cmd_smoke(args) -> int:
    cond = kb.condition(args.condition)
    work = Path(args.work or tempfile.mkdtemp(prefix=f"kbcm-smoke-{cond.name}-")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    (work / kb.BODY_NAME).write_text(kb.compose_body(cond, args.osdi_dir), encoding="utf-8")
    req = kb.compose_request(cond, kb.BODY_NAME, backend="local")
    req["corners"]["process"] = [args.process]
    req["corners"]["supply_v"] = {"vsup": [args.supply]}
    req["corners"]["temperature_c"] = [args.temperature]
    return kcli.run_local_smoke(req, work, args.klt)


def cmd_compare(args) -> int:
    series = _series(args)
    result = kb.compare_series(series, kb.REFERENCE_DIR)
    rc = kcli.publish_report_pair("compare", args, series, "comparison", result,
                                  kb.render_markdown(result), "series")
    if rc or getattr(args, "check", False):
        return rc
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


def cmd_probe_build(args) -> int:
    # Plan every arm of every selected condition first (running the #165
    # reference-body check per shared-body arm), then commit the whole build
    # as one batch: a conflict on any arm writes nothing (no partial build).
    issue = _issue_for(args.series)
    series = _series(args)
    planned: dict[Path, bytes] = {}  # the shared body prints once per condition
    try:
        for name in args.condition or [c.name for c in kb.CONDITIONS]:
            cond = kb.condition(name)
            out_dir = series / cond.name
            for arm in _arms_for(args.series, args.arm):
                files = kb.probe_input_bytes(cond, arm, issue=issue)
                kb.check_probe_reference_body(cond, arm, files)
                planned.update((out_dir / n, data) for n, data in files.items())
    except kb.KickbackCmBandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return kcli.commit_build("probe-build", list(planned.items()), evidence="probe evidence")


def cmd_probe_run(args) -> int:
    """Submit one arm request on the batch fleet (capacity_wait_s is in the
    request). A failed submit is reported, never run locally."""
    cond = kb.condition(args.condition)
    out_dir = _series(args) / cond.name
    tag = kb.probe_arm_tag(args.arm)
    request = out_dir / f"{tag}.request.json"
    if not request.is_file():
        print(f"no request at {request}; run `probe-build` first", file=sys.stderr)
        return 1
    _retire_unrun_submit(out_dir, tag)
    if (out_dir / f"{tag}.envelope.json").exists():
        print(f"{tag}: envelope present -- append-only, not resubmitted", file=sys.stderr)
        return 0 if args.skip_existing else 1
    if _graded_attempts(out_dir, tag, unrun_ok=True):
        print(f"{tag}: attempts.jsonl records a graded run but no envelope; refusing to "
              "resubmit (investigate)", file=sys.stderr)
        return 1
    extra = {"condition": kb.condition_metadata(cond), "kind": "probe", "probe_arm": args.arm,
             "issue": _issue_for(args.series)}
    # --backend batch explicitly: the body's OSDI path exists only on the fleet,
    # so even the one-corner edge requests must not stay local.
    return kcli._submit_with_retry(request, out_dir, tag, args, extra, backend="batch")


def cmd_probe_compare(args) -> int:
    series = _series(args)
    arms = _arms_for(args.series, args.arm)
    report_dir = getattr(args, "report_dir", None)
    issue = _issue_for(args.series)
    if issue == kb.COLD_ISSUE:
        # The #552 cold-edge series' comparison is the init-arm four-point
        # summary; any other arm set would publish an analysis this issue
        # never defined into its namespace.
        if set(arms) != set(kb.PROBE_ARMS_552):
            print(f"{args.series} is the issue #552 cold-edge series; its comparison is the "
                  f"four-point summary of arm set {list(kb.PROBE_ARMS_552)}, not {list(arms)}; "
                  "refusing to publish that into its namespace", file=sys.stderr)
            return 1
        res = kb.coldinit_compare(series, arms=arms)
        md = kb.coldinit_render_markdown(res)
    else:
        if args.series == FROZEN_PROBE_SERIES and set(arms) != set(kb.PROBE_ARMS) and (
                not report_dir or Path(report_dir) == series):
            print(f"{args.series} is the frozen #405 probe series; refusing to rewrite it in "
                  "place with a non-#405 arm set (its committed files must stay byte-unchanged; "
                  "publish under a NEW --report-dir instead)", file=sys.stderr)
            return 1
        res = kb.probe_compare(series, arms=arms, issue=issue)
        md = kb.probe_render_markdown(res)
    rc = kcli.publish_report_pair("probe-compare", args, series, "comparison", res,
                                  md, "series")
    if rc or getattr(args, "check", False):
        return rc
    for p in res["problems"]:
        print("problem:", p, file=sys.stderr)
    if issue == kb.COLD_ISSUE:
        for p in res["points"]:
            q = p["qualification"]
            note = (f"residue {q['residue_uv']} uV vs <= {q['residue_target_uv']} uV: "
                    f"{q['residue_verdict']}" if q["qualified"] else "; ".join(q["failed"]))
            print(f"{p['key']} {p['role']} {'qualified' if q['qualified'] else 'UNQUALIFIED'}"
                  f" -- {note}")
        return 1 if res["problems"] else 0
    for r in res["points"]:
        for arm, a in r["arms"].items():
            if a.get("present"):
                v = a["values"]
                print(r["condition"], r["key"], arm, a["corner_status"],
                      "repro165" if a["equals_165_on_original_cards"] else "DIFFERS",
                      {g: v.get(g) for g in kb.PROBE_GATES})
    return 1 if res["problems"] else 0


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
    kcli.add_report_pair_args(g, "comparison", "series")
    g.set_defaults(func=cmd_compare)

    pb = sub.add_parser("probe-build")
    pb.add_argument("--series", required=True)
    pb.add_argument("--condition", action="append", choices=names)
    pb.add_argument("--arm", action="append", choices=list(kb.ALL_PROBE_ARMS))
    pb.add_argument("--root", type=Path, default=None,
                    help="stage the series under this root instead of "
                         "sim/comparator-kickback-cm-band/campaigns/ (issue #552 stages in "
                         "git-ignored scratch for the manifest store workflow)")
    pb.set_defaults(func=cmd_probe_build)

    pr = sub.add_parser("probe-run")
    pr.add_argument("--series", required=True)
    pr.add_argument("--condition", required=True, choices=names)
    pr.add_argument("--arm", required=True, choices=list(kb.ALL_PROBE_ARMS))
    pr.add_argument("--skip-existing", action="store_true")
    pr.add_argument("--klt", default=default_klt)
    pr.add_argument("--retry-refused", type=int, default=0)
    pr.add_argument("--retry-wait", type=int, default=120)
    pr.add_argument("--root", type=Path, default=None,
                    help="stage the series under this root instead of "
                         "sim/comparator-kickback-cm-band/campaigns/ (issue #552 stages in "
                         "git-ignored scratch for the manifest store workflow)")
    pr.set_defaults(func=cmd_probe_run, force=False)

    pc = sub.add_parser("probe-compare")
    pc.add_argument("--series", required=True)
    pc.add_argument("--arm", action="append", choices=list(kb.ALL_PROBE_ARMS),
                    help="arm set to compare (default: by series, see --help)")
    pc.add_argument("--root", type=Path, default=None,
                    help="read the series from this root instead of "
                         "sim/comparator-kickback-cm-band/campaigns/ (issue #552 stages in "
                         "git-ignored scratch for the manifest store workflow)")
    kcli.add_report_pair_args(pc, "comparison", "series")
    pc.set_defaults(func=cmd_probe_compare)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

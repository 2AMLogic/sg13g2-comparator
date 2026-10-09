"""Command line for the issue #62 klt sim corner-verification campaign.

    python3 sim/run_klt_corner_verification.py build  --campaign ID
    python3 sim/run_klt_corner_verification.py smoke  --bench NAME --osdi-dir DIR [--klt KLT]
    python3 sim/run_klt_corner_verification.py run    --campaign ID --bench NAME [--klt KLT]
    python3 sim/run_klt_corner_verification.py grade  --campaign ID

``build`` writes the committed (batch-form) bodies and requests into
``sim/klt-corner-verification/campaigns/ID/``. ``run`` submits one of them
with ``klt sim`` (the request itself says ``backend: batch``, so the corner
grid runs on the batch fleet, never on this host) and stores the envelope
exactly as printed, plus the invocation. ``smoke`` runs ONE corner of a
bench locally (``--backend local``) from a scratch directory, for checking
OSDI loading, model-section switching and the derived measurements before a
campaign; it writes nothing under ``sim/``. ``grade`` reads committed
envelopes and writes ``grading.json`` / ``grading.md``.

Run from the repository root: ``klt sim`` reports the netlist path relative
to the invoking repo, and ``klt signoff``'s re-hash of a cited envelope's
netlist resolves against it.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import build as build_mod
from . import grade as grade_mod
from .benches import BENCHES

CAMPAIGNS_DIR = build_mod.EXPERIMENT_DIR / "campaigns"


def _campaign_dir(campaign: str) -> Path:
    return CAMPAIGNS_DIR / campaign


def _klt_version(klt: str) -> str:
    out = subprocess.run([klt, "--version"], capture_output=True, text=True, check=False)
    return (out.stdout or out.stderr).strip()


def cmd_build(args) -> int:
    out_dir = _campaign_dir(args.campaign)
    names = args.bench or list(BENCHES)
    for name in names:
        body, requests = build_mod.write_bench_inputs(BENCHES[name], out_dir, target="batch")
        print(f"wrote {body.relative_to(build_mod.REPO_ROOT)}")
        for request in requests:
            print(f"wrote {request.relative_to(build_mod.REPO_ROOT)}")
    return 0


def cmd_smoke(args) -> int:
    bench = BENCHES[args.bench]
    work = Path(args.work or tempfile.mkdtemp(prefix=f"kltsim-smoke-{bench.name}-"))
    body, (request_path, *rest) = build_mod.write_bench_inputs(
        bench, work, target="local", osdi_dir=args.osdi_dir, split=False
    )
    request = json.loads(request_path.read_text(encoding="utf-8"))
    # ONE corner: a debug probe, which host policy allows locally.
    request["corners"]["process"] = [args.process or bench.process_sections[0]]
    request["corners"]["supply_v"] = {k: [args.supply] for k in bench.supply_keys}
    request["corners"]["temperature_c"] = [args.temperature]
    if "monte_carlo" in request:
        request["monte_carlo"]["n"] = 1
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    cmd = [args.klt, "sim", str(request_path), "--backend", "local",
           "--format", "json", "-o", str(work / "artifacts")]
    print("$ " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    (work / "envelope.json").write_text(proc.stdout, encoding="utf-8")
    print(f"klt sim exit {proc.returncode}; work dir {work}", file=sys.stderr)
    if proc.stderr.strip():
        print(proc.stderr.strip()[-2000:], file=sys.stderr)
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout[-2000:])
        return 1
    print(json.dumps({"status": env.get("status"), "corners": [
        {"corner_id": c["corner_id"], "status": c["status"],
         "diagnostics": c.get("diagnostics"),
         "measurements": {m["name"]: m["value"] for m in c["measurements"]}}
        for c in env.get("corners", [])]}, indent=1))
    return 0


def cmd_fleet_smoke(args) -> int:
    """A deliberately tiny batch job: proves the fleet path (image OSDI dir,
    model resolution, section switching, MC seeding) before a campaign.
    Its inputs and envelope are committed under campaigns/ID/smoke/ as the
    verification record; it is never graded as spec evidence."""
    bench = BENCHES[args.bench]
    out_dir = _campaign_dir(args.campaign) / "smoke"
    tag = args.tag or bench.name
    body, (request_path, *rest) = build_mod.write_bench_inputs(
        bench, out_dir, target="batch", split=False)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["_comment"].append(
        f"FLEET SMOKE `{tag}`: a reduced grid for verifying the batch path, "
        "not spec evidence (sim/kltsim/cli.py fleet-smoke)."
    )
    request["corners"]["process"] = args.process or [bench.process_sections[0]]
    request["corners"]["supply_v"] = {k: [args.supply] for k in bench.supply_keys}
    request["corners"]["temperature_c"] = [args.temperature]
    request.pop("remote", None)
    if args.analysis_args:
        # e.g. a timestep-convergence probe: same body, tighter max step.
        request["analysis"]["args"] = args.analysis_args
        request["_comment"].append(
            f"analysis args overridden to `{args.analysis_args}` (campaign: "
            f"`{bench.analysis['args']}`) for a convergence check.")
    if "monte_carlo" in request:
        request["monte_carlo"]["n"] = args.n
    final_request = out_dir / f"{tag}.request.json"
    request_path.unlink()
    final_request.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    return _submit(final_request, out_dir, tag, args)


def _submit(request_path: Path, out_dir: Path, tag: str, args, extra: dict | None = None) -> int:
    """Run ``klt sim`` on one committed request and keep what it printed.

    Every attempt -- including a refused submission (e.g. the shared batch
    fleet at its instance cap) -- is appended to ``attempts.jsonl`` beside
    the request, so a resubmission is visible rather than silent. Only a run
    that produced a graded envelope (klt sim exit 0 / 3 / 4) writes
    ``<tag>.envelope.json`` + ``<tag>.invocation.json``; those are
    append-only (``--force`` exists for scratch use, not for evidence).
    ``extra`` is merged into the invocation record (and the attempt log).
    """
    envelope_path = out_dir / f"{tag}.envelope.json"
    if envelope_path.exists() and not args.force:
        print(f"{envelope_path} exists -- campaign evidence is append-only; "
              "use a new --campaign id", file=sys.stderr)
        return 1
    artifacts = out_dir / "artifacts" / tag
    rel_request = request_path.relative_to(build_mod.REPO_ROOT)
    rel_artifacts = artifacts.relative_to(build_mod.REPO_ROOT)
    cmd = [args.klt, "sim", str(rel_request), "--format", "json", "-o", str(rel_artifacts)]
    started = _dt.datetime.now(_dt.timezone.utc)
    print("$ " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False,
                          cwd=build_mod.REPO_ROOT)
    finished = _dt.datetime.now(_dt.timezone.utc)
    invocation = {
        "tag": tag,
        "command": ["klt", *cmd[1:]],
        "cwd": ".",
        "klt_version": _klt_version(args.klt),
        "env": {k: os.environ.get(k) for k in ("KLT_SIM_BACKEND",)},
        "request_sha256": build_mod.sha256_file(request_path),
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": finished.isoformat(timespec="seconds"),
        "exit_code": proc.returncode,
        "stderr_tail": proc.stderr[-4000:],
        "envelope_sha256": build_mod.sha256_bytes(proc.stdout.encode("utf-8")),
    }
    if extra:
        # caller-side metadata (e.g. the issue #79 common-mode condition)
        invocation.update(extra)
    with (out_dir / "attempts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(invocation, sort_keys=True) + "\n")
    if proc.stderr.strip():
        print(proc.stderr.strip()[-2000:], file=sys.stderr)
    if proc.returncode not in (0, 3, 4) or not proc.stdout.strip():
        print(f"klt sim exit {proc.returncode}: no envelope written (attempt logged)",
              file=sys.stderr)
        return 1
    envelope_path.write_text(proc.stdout, encoding="utf-8")
    (out_dir / f"{tag}.invocation.json").write_text(
        json.dumps(invocation, indent=2) + "\n", encoding="utf-8")
    print(f"klt sim exit {proc.returncode} -> {envelope_path.relative_to(build_mod.REPO_ROOT)}",
          file=sys.stderr)
    return 0


def cmd_run(args) -> int:
    out_dir = _campaign_dir(args.campaign)
    bench = BENCHES[args.bench]
    tags = build_mod.part_tags(bench)
    if args.part:
        tags = [tag for tag in tags if tag in args.part]
    rc = 0
    for tag in tags:
        request_path = out_dir / f"{tag}.request.json"
        if not request_path.is_file():
            print(f"no request at {request_path}; run `build` first", file=sys.stderr)
            return 1
        if (out_dir / f"{tag}.envelope.json").exists() and args.skip_existing:
            print(f"{tag}: envelope present, skipped", file=sys.stderr)
            continue
        for attempt in range(1, args.retry_refused + 2):
            code = _submit(request_path, out_dir, tag, args)
            if code == 0 or not _last_attempt_refused_at_cap(out_dir):
                break
            if attempt <= args.retry_refused:
                print(f"{tag}: fleet at its instance cap; retry {attempt}/"
                      f"{args.retry_refused} in {args.retry_wait}s", file=sys.stderr)
                time.sleep(args.retry_wait)
        rc = max(rc, code)
    return rc


def _last_attempt_refused_at_cap(out_dir: Path) -> bool:
    """True when the most recent logged attempt was the shared fleet's
    instance-cap refusal (nothing ran; resubmitting is the remedy)."""
    lines = (out_dir / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1]) if lines else {}
    return "exceeds BATCH_MAX_CONCURRENT_INSTANCES" in (last.get("stderr_tail") or "")


def cmd_grade(args) -> int:
    out_dir = _campaign_dir(args.campaign)
    result = grade_mod.grade_campaign(out_dir)
    (out_dir / "grading.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out_dir / "grading.md").write_text(grade_mod.render_markdown(result), encoding="utf-8")
    print(grade_mod.render_summary(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    default_klt = shutil.which("klt") or "klt"
    ap = argparse.ArgumentParser(prog="run_klt_corner_verification.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="write batch-form bodies + requests for a campaign")
    b.add_argument("--campaign", required=True)
    b.add_argument("--bench", action="append", choices=sorted(BENCHES))
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("smoke", help="run ONE corner of a bench locally (scratch dir)")
    s.add_argument("--bench", required=True, choices=sorted(BENCHES))
    s.add_argument("--osdi-dir", required=True)
    s.add_argument("--process")
    s.add_argument("--supply", type=float, default=1.2)
    s.add_argument("--temperature", type=float, default=27)
    s.add_argument("--work")
    s.add_argument("--klt", default=default_klt)
    s.set_defaults(func=cmd_smoke)

    r = sub.add_parser("run", help="submit one bench of a built campaign via klt sim")
    r.add_argument("--campaign", required=True)
    r.add_argument("--bench", required=True, choices=sorted(BENCHES))
    r.add_argument("--klt", default=default_klt)
    r.add_argument("--part", action="append", help="only these request parts (tags)")
    r.add_argument("--skip-existing", action="store_true",
                   help="skip parts whose envelope already exists (resubmission)")
    r.add_argument("--retry-refused", type=int, default=0,
                   help="resubmit up to N times when the batch fleet refuses at its instance cap")
    r.add_argument("--retry-wait", type=int, default=120)
    r.add_argument("--force", action="store_true")
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("fleet-smoke", help="submit a tiny reduced-grid batch job (verification)")
    f.add_argument("--campaign", required=True)
    f.add_argument("--bench", required=True, choices=sorted(BENCHES))
    f.add_argument("--tag")
    f.add_argument("--process", action="append")
    f.add_argument("--supply", type=float, default=1.2)
    f.add_argument("--temperature", type=float, default=27)
    f.add_argument("--n", type=int, default=4)
    f.add_argument("--analysis-args", help="override the bench's tran args (convergence probe)")
    f.add_argument("--klt", default=default_klt)
    f.add_argument("--force", action="store_true")
    f.set_defaults(func=cmd_fleet_smoke)

    g = sub.add_parser("grade", help="grade a campaign's committed envelopes")
    g.add_argument("--campaign", required=True)
    g.set_defaults(func=cmd_grade)

    args = ap.parse_args(argv)
    return args.func(args)

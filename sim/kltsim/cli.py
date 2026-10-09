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
import dataclasses
import datetime as _dt
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import build as build_mod
from . import fixture as fixture_mod
from . import grade as grade_mod
from . import ibsweep as ibsweep_mod
from . import sizesweep as sizesweep_mod
from . import noise_full as noise_full_mod
from .benches import ALL_BENCHES, BENCHES, BIAS_PROBES, FIXTURE_BENCHES

CAMPAIGNS_DIR = build_mod.EXPERIMENT_DIR / "campaigns"


def _campaign_dir(campaign: str) -> Path:
    return CAMPAIGNS_DIR / campaign


def _klt_version(klt: str) -> str:
    out = subprocess.run([klt, "--version"], capture_output=True, text=True, check=False)
    return (out.stdout or out.stderr).strip()


def _parse_overrides(items) -> dict:
    overrides = {}
    for item in items or []:
        key, _, value = item.partition("=")
        overrides[key] = float(value)
    return overrides


def _rel(path: Path) -> Path:
    """Repo-relative form of ``path`` (as ``klt sim`` records it); a path
    outside the repo (tests use temporary campaign dirs) is kept absolute."""
    try:
        return path.relative_to(build_mod.REPO_ROOT)
    except ValueError:
        return path


def _json_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=2) + "\n").encode("utf-8")


def _commit_planned(planned, args, label: str) -> bool:
    """Write a helper command's precomputed inputs append-only (issue #105).

    Every destination that exists must already hold exactly the proposed
    bytes, else nothing is written (an identical regeneration leaves bytes and
    timestamps alone). ``--force`` keeps its explicit scratch contract and
    overwrites. Returns False (after printing why) on a refusal.
    """
    if getattr(args, "force", False):
        for path, data in planned:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return True
    try:
        build_mod.commit_inputs(planned)
    except build_mod.BuildError as exc:
        print(f"{label}: {exc}", file=sys.stderr)
        return False
    return True


def cmd_build(args) -> int:
    out_dir = _campaign_dir(args.campaign)
    names = args.bench or list(BENCHES)
    overrides = _parse_overrides(args.dut_param)
    geometry = build_mod.parse_geometry(getattr(args, "geometry", None)) or None
    # Compose EVERY selected bench's inputs before writing anything, then
    # commit them append-only: a conflict in any bench changes no file.
    planned: list[tuple[Path, bytes]] = []
    for name in names:
        bench = ALL_BENCHES[name]
        if args.bias_probes and name == "regeneration":
            bench = dataclasses.replace(bench, measurements=bench.measurements + BIAS_PROBES)
        planned += build_mod.plan_bench_inputs(
            bench, out_dir, target="batch", param_overrides=overrides or None,
            geometry_overrides=geometry)[2]
    if getattr(args, "screen", False):
        planned = [(path, sizesweep_mod.screen_request(data) if path.name.endswith(".request.json") else data)
                   for path, data in planned]
    try:
        created = set(build_mod.commit_inputs(planned))
    except build_mod.BuildError as exc:
        print(f"build: {exc}", file=sys.stderr)
        return 1
    for path, _ in planned:
        verb = "wrote" if path in created else "unchanged"
        try:
            shown = path.relative_to(build_mod.REPO_ROOT)
        except ValueError:  # a campaigns dir outside the repo (tests)
            shown = path
        print(f"{verb} {shown}")
    return 0


def cmd_smoke(args) -> int:
    bench = ALL_BENCHES[args.bench]
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


def cmd_fixture(args) -> int:
    """Run the DUT-free known-charge fixture as ONE local unit (a single
    corner, no grid), keep its request/body/envelope/invocation in
    ``campaigns/ID/fixture/``, and write the measured-vs-analytic table."""
    bench = FIXTURE_BENCHES[args.bench]
    out_dir = _campaign_dir(args.campaign) / "fixture"
    body_name = f"{bench.name}.body.spice"
    request_path = out_dir / f"{bench.name}.request.json"
    planned = [
        (out_dir / body_name, build_mod.compose_fixture_body(bench).encode("utf-8")),
        (request_path, _json_bytes(build_mod.compose_fixture_request(bench, body_name))),
    ]
    if not _commit_planned(planned, args, "fixture"):
        return 1
    # Same append-only submit path as the campaign; the request pins
    # backend=local and a single unit, which host policy allows.
    code = _submit(request_path, out_dir, bench.name, args, backend="local")
    if code:
        return code
    env = json.loads((out_dir / f"{bench.name}.envelope.json").read_text(encoding="utf-8"))
    report = fixture_mod.check_envelope(bench, env)
    (out_dir / f"{bench.name}.check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / f"{bench.name}.check.md").write_text(fixture_mod.render_markdown(report), encoding="utf-8")
    print(fixture_mod.render_markdown(report))
    return 0 if report["ok"] else 2


_AMMETER_LINES = ("vkp ", "vkn ", "Bqp ", "Cqp ", "Rqp ", "Bqn ", "Cqn ", "Rqn ")


def strip_instrument(body: str) -> str:
    """The kickback body with the Q_kick instrument removed and the DUT pins
    wired straight to the source network (apa_pin -> apa, ana_pin -> ana):
    the pre-#62 circuit, for the decisions-unchanged A/B."""
    kept = []
    for line in body.split("\n"):
        if line.startswith(_AMMETER_LINES):
            continue
        if line.startswith("Xa "):
            line = line.replace("apa_pin", "apa").replace("ana_pin", "ana")
        kept.append(line)
    return "\n".join(kept)


_AB_OK_STATUS = ("pass", "fail", "ok")  # a measurement-level gate fail is not an invalid control


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _expected_decisions(request: dict) -> set[str]:
    return {m["name"] for m in request.get("measurements") or []
            if str(m.get("name", "")).startswith("dout_")}


def validate_ab_envelope(env, request: dict, expected_names, arm: str) -> list[str]:
    """Why this arm's envelope cannot support a decisions-unchanged verdict
    (issue #106). Every message is prefixed ``<arm>: <field>``; empty means
    valid. Pure: the expectation comes from the arm's own generated request."""
    if not isinstance(env, dict):
        return [f"{arm}: envelope is not an object"]
    diags = []
    status = env.get("status")
    if status not in _AB_OK_STATUS:
        diags.append(f"{arm}: status {status!r} is not one of {list(_AB_OK_STATUS)}")
    corners = env.get("corners")
    if not isinstance(corners, list) or len(corners) != 1:
        n = len(corners) if isinstance(corners, list) else None
        diags.append(f"{arm}: corners must hold exactly one entry, found {n}")
        return diags
    corner = corners[0]
    if not isinstance(corner, dict):
        return diags + [f"{arm}: corners[0] is not an object"]
    if corner.get("status") == "error":
        codes = ",".join(sorted({str(d.get("code", "?")) for d in corner.get("diagnostics") or []
                                 if isinstance(d, dict)}))
        diags.append(f"{arm}: corners[0].status is error ({codes or 'no diagnostic'})")
    req = request.get("corners") or {}
    want_p = (req.get("process") or [None])[0]
    if corner.get("process") != want_p:
        diags.append(f"{arm}: corners[0].process {corner.get('process')!r} != requested {want_p!r}")
    want_t = (req.get("temperature_c") or [None])[0]
    got_t = corner.get("temperature_c")
    if not _finite(got_t) or not _finite(want_t) or abs(got_t - want_t) > 1e-9:
        diags.append(f"{arm}: corners[0].temperature_c {got_t!r} != requested {want_t!r}")
    got_s = corner.get("supply_v")
    got_s = got_s if isinstance(got_s, dict) else {}
    for key, vals in (req.get("supply_v") or {}).items():
        got = got_s.get(key)
        if not _finite(got) or abs(got - vals[0]) > 1e-9:
            diags.append(f"{arm}: corners[0].supply_v.{key} {got!r} != requested {vals[0]!r}")
    count = {}
    for m in corner.get("measurements") or []:
        if isinstance(m, dict):
            count.setdefault(m.get("name"), []).append(m)
    for name in sorted(expected_names):
        ms = count.get(name, [])
        if not ms:
            diags.append(f"{arm}: {name} missing")
        elif len(ms) > 1:
            diags.append(f"{arm}: {name} duplicated ({len(ms)} entries)")
        elif not _finite(ms[0].get("value")):
            diags.append(f"{arm}: {name} value {ms[0].get('value')!r} is not a finite number")
    return diags


def cmd_ab(args) -> int:
    """Decisions-unchanged A/B (issue #78): the kickback bench with and
    without the 0 V ammeters + integrators, ONE corner each, submitted to
    the batch fleet like every DUT run (this host's ngspice 42 cannot load
    the PDK's OSDI v0.4 models, so the DUT cannot run locally at all). Writes request/body/envelope per arm and
    ``ab.json`` comparing every dout_* / probe measurement."""
    bench = BENCHES["kickback"]
    out_dir = _campaign_dir(args.campaign) / "ab"
    base = build_mod.compose_body(bench, build_mod.BATCH_OSDI_DIR)
    arms = {"with_instrument": base, "without_instrument": strip_instrument(base)}
    # Compose BOTH arms before writing or submitting anything, so a conflict
    # in the second arm leaves the first untouched (issue #105).
    planned = []
    requests = {}
    for arm, body in arms.items():
        body_name = f"kickback-{arm}.body.spice"
        request = build_mod.compose_request(bench, body_name, "batch")
        request["_comment"].append(
            f"DECISIONS A/B arm `{arm}` (issue #78): one unit, {args.process} / {args.supply} V / "
            f"{args.temperature} C, batch. Not spec evidence.")
        request["corners"]["process"] = [args.process]
        request["corners"]["supply_v"] = {k: [args.supply] for k in bench.supply_keys}
        request["corners"]["temperature_c"] = [args.temperature]
        if arm == "without_instrument":
            # the q* measurements have no node to read; keep the decision ones
            request["measurements"] = [m for m in request["measurements"]
                                       if not m["name"].startswith(("qp", "qn", "qkick"))]
        requests[arm] = request
        planned += [(out_dir / body_name, body.encode("utf-8")),
                    (out_dir / f"kickback-{arm}.request.json", _json_bytes(request))]
    if not _commit_planned(planned, args, "ab"):
        return 1
    envs = {}
    for arm in arms:
        request_path = out_dir / f"kickback-{arm}.request.json"
        code = _submit(request_path, out_dir, f"kickback-{arm}", args)
        if code:
            return code
        envs[arm] = json.loads((out_dir / f"kickback-{arm}.envelope.json").read_text(encoding="utf-8"))

    expected = {arm: _expected_decisions(requests[arm]) for arm in arms}
    diagnostics = []
    if not expected["with_instrument"]:
        diagnostics.append("with_instrument: request.measurements has no dout_* decision")
    if expected["with_instrument"] != expected["without_instrument"]:
        diagnostics.append(
            "harness: requested dout_* sets differ between arms: with_instrument="
            f"{sorted(expected['with_instrument'])} without_instrument="
            f"{sorted(expected['without_instrument'])}")
    for arm in arms:
        diagnostics += validate_ab_envelope(envs[arm], requests[arm], expected[arm], arm)

    def values(env):
        out = {}
        corners = env.get("corners") if isinstance(env, dict) else None
        for corner in (corners if isinstance(corners, list) else [])[:1]:
            for m in (corner.get("measurements") or []) if isinstance(corner, dict) else []:
                if isinstance(m, dict) and "name" in m:
                    out.setdefault(m["name"], m.get("value"))
        return out

    a, b = values(envs["with_instrument"]), values(envs["without_instrument"])
    rows = []
    for name in sorted(set(a) | set(b)):
        va, vb = a.get(name), b.get(name)
        rows.append({"measurement": name, "with": va, "without": vb,
                     "abs_diff": abs(va - vb) if _finite(va) and _finite(vb) else None})
    wanted = sorted(expected["with_instrument"] | expected["without_instrument"])
    by_name = {r["measurement"]: r for r in rows}
    result = {
        "corner": f"{args.process}/{args.supply:.3f}V/{args.temperature:g}C",
        "decisions_identical": False,
        "decision_measurements": wanted,
        "rows": rows,
    }
    if diagnostics:
        result["control_status"] = "incomplete"
        result["diagnostics"] = diagnostics
    else:
        result["control_status"] = "complete"
        result["decisions_identical"] = all(
            by_name[n]["with"] == by_name[n]["without"] for n in wanted)
    (out_dir / "ab.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=1))
    for r in rows:
        print(f"{r['measurement']:24s} with={r['with']!r:>14} without={r['without']!r:>14} diff={r['abs_diff']}")
    if diagnostics:
        print("A/B control INCOMPLETE (decisions_identical=false):", file=sys.stderr)
        for d in diagnostics:
            print(f"  {d}", file=sys.stderr)
    return 0 if result["decisions_identical"] else 2


def cmd_fleet_smoke(args) -> int:
    """A deliberately tiny batch job: proves the fleet path (image OSDI dir,
    model resolution, section switching, MC seeding) before a campaign.
    Its inputs and envelope are committed under campaigns/ID/smoke/ as the
    verification record; it is never graded as spec evidence. Inputs are
    append-only (issue #105): each tag owns ``<tag>.body.spice`` and
    ``<tag>.request.json``, and a changed repeat of a tag is refused."""
    bench = ALL_BENCHES[args.bench]
    out_dir = _campaign_dir(args.campaign) / "smoke"
    tag = args.tag or bench.name
    overrides = _parse_overrides(args.dut_param)
    if args.bias_probes and bench.name == "regeneration":
        bench = dataclasses.replace(bench, measurements=bench.measurements + BIAS_PROBES)
    _, _, files = build_mod.plan_bench_inputs(
        bench, out_dir, target="batch", split=False, param_overrides=overrides or None)
    # Each tag owns its body (<tag>.body.spice): tags with different overrides
    # must not share, and so invalidate, one mutable bench-named body.
    body_name = f"{tag}.body.spice"
    body_bytes = files[0][1]
    request = json.loads(files[1][1].decode("utf-8"))
    request["netlist"] = body_name
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
    if not _commit_planned([(out_dir / body_name, body_bytes),
                            (final_request, _json_bytes(request))], args, "fleet-smoke"):
        return 1
    return _submit(final_request, out_dir, tag, args)


def _submit(request_path: Path, out_dir: Path, tag: str, args,
            backend: str | None = None, extra: dict | None = None) -> int:
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
    rel_request = _rel(request_path)
    rel_artifacts = _rel(artifacts)
    # A local-backend run needs an ABSOLUTE -o: with a repo-relative one the
    # pinned klt (0.7.0) ends every unit in an `error` envelope with no
    # ngspice.log and "produced no value" for every measurement (the same
    # request passes with an absolute path; 2AMLogic/klayout-tools#2966). The batch backend is unaffected.
    out_arg = str(artifacts) if backend == "local" else str(rel_artifacts)
    cmd = [args.klt, "sim", str(rel_request), "--format", "json", "-o", out_arg]
    if backend:
        # KLT_SIM_BACKEND=batch is exported on dispatch hosts; a one-unit
        # fixture must say so explicitly to stay local.
        cmd += ["--backend", backend]
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
    print(f"klt sim exit {proc.returncode} -> {_rel(envelope_path)}",
          file=sys.stderr)
    return 0


def cmd_run(args) -> int:
    out_dir = _campaign_dir(args.campaign)
    bench = ALL_BENCHES[args.bench]
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
    (out_dir / "grading.json").write_text(grade_mod.dumps_strict(result, indent=2) + "\n", encoding="utf-8")
    (out_dir / "grading.md").write_text(grade_mod.render_markdown(result), encoding="utf-8")
    print(grade_mod.render_summary(result))
    return 0


def cmd_noise_full(args) -> int:
    """Issue #81: per-config probit sigmas + quadrature split for a campaign."""
    out_dir = _campaign_dir(args.campaign)
    result = noise_full_mod.analyse(out_dir)
    result["campaign"] = out_dir.name
    (out_dir / "noise_full.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    text = noise_full_mod.render_markdown(result)
    (out_dir / "noise_full.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_ibsweep(args) -> int:
    result = ibsweep_mod.run(args.campaign, CAMPAIGNS_DIR)
    print((CAMPAIGNS_DIR / args.campaign / "ibsweep.md").read_text(encoding="utf-8"))
    return 0 if result["points"] else 1


def cmd_sizesweep(args) -> int:
    result = sizesweep_mod.run(args.campaign, CAMPAIGNS_DIR)
    print((CAMPAIGNS_DIR / args.campaign / "sizesweep.md").read_text(encoding="utf-8"))
    return 0 if result["screen"] or result["full"] else 1


def main(argv: list[str] | None = None) -> int:
    default_klt = shutil.which("klt") or "klt"
    ap = argparse.ArgumentParser(prog="run_klt_corner_verification.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="write batch-form bodies + requests for a campaign")
    b.add_argument("--campaign", required=True)
    b.add_argument("--bench", action="append", choices=sorted(ALL_BENCHES))
    b.add_argument("--dut-param", action="append", metavar="NAME=VALUE",
                   help="override a sim/dut.json param in the emitted body only (issue #80 sweep)")
    b.add_argument("--geometry", action="append", metavar="INST.FIELD=VALUE",
                   help="override a MOS w/l in the inlined DUT body only (issue #92 sizing study)")
    b.add_argument("--screen", action="store_true",
                   help="reduced screening grid (tt/ff/ss x 1.08/1.32 V x -40/27/125 C), issue #92")
    b.add_argument("--bias-probes", action="store_true",
                   help="append the mirror/headroom probes to the regeneration bench")
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("smoke", help="run ONE corner of a bench locally (scratch dir)")
    s.add_argument("--bench", required=True, choices=sorted(ALL_BENCHES))
    s.add_argument("--osdi-dir", required=True)
    s.add_argument("--process")
    s.add_argument("--supply", type=float, default=1.2)
    s.add_argument("--temperature", type=float, default=27)
    s.add_argument("--work")
    s.add_argument("--klt", default=default_klt)
    s.set_defaults(func=cmd_smoke)

    r = sub.add_parser("run", help="submit one bench of a built campaign via klt sim")
    r.add_argument("--campaign", required=True)
    r.add_argument("--bench", required=True, choices=sorted(ALL_BENCHES))
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
    f.add_argument("--bench", required=True, choices=sorted(ALL_BENCHES))
    f.add_argument("--tag")
    f.add_argument("--process", action="append")
    f.add_argument("--supply", type=float, default=1.2)
    f.add_argument("--temperature", type=float, default=27)
    f.add_argument("--n", type=int, default=4)
    f.add_argument("--dut-param", action="append", metavar="NAME=VALUE")
    f.add_argument("--bias-probes", action="store_true")
    f.add_argument("--analysis-args", help="override the bench's tran args (convergence probe)")
    f.add_argument("--klt", default=default_klt)
    f.add_argument("--force", action="store_true")
    f.set_defaults(func=cmd_fleet_smoke)

    x = sub.add_parser("fixture", help="run the DUT-free known-charge Q_kick fixture (one local unit)")
    x.add_argument("--campaign", required=True)
    x.add_argument("--bench", default="kickback_fixture", choices=sorted(FIXTURE_BENCHES))
    x.add_argument("--klt", default=default_klt)
    x.add_argument("--force", action="store_true")
    x.set_defaults(func=cmd_fixture)

    ab = sub.add_parser("ab", help="decisions-unchanged A/B of the kickback instrument (two one-corner batch requests)")
    ab.add_argument("--campaign", required=True)
    ab.add_argument("--process", default="mos_tt")
    ab.add_argument("--supply", type=float, default=1.2)
    ab.add_argument("--temperature", type=float, default=27)
    ab.add_argument("--klt", default=default_klt)
    ab.add_argument("--force", action="store_true")
    ab.set_defaults(func=cmd_ab)

    ib = sub.add_parser("ibsweep", help="tabulate a dut_ib sweep campaign (issue #80)")
    ib.add_argument("--campaign", required=True)
    ib.set_defaults(func=cmd_ibsweep)

    sz = sub.add_parser("sizesweep", help="tabulate an input-pair sizing study (issue #92)")
    sz.add_argument("--campaign", required=True)
    sz.set_defaults(func=cmd_sizesweep)

    g = sub.add_parser("grade", help="grade a campaign's committed envelopes")
    g.add_argument("--campaign", required=True)
    g.set_defaults(func=cmd_grade)

    nf = sub.add_parser("noise-full", help="issue #81: analyse the tn_full_* configurations of a campaign")
    nf.add_argument("--campaign", required=True)
    nf.set_defaults(func=cmd_noise_full)

    args = ap.parse_args(argv)
    return args.func(args)

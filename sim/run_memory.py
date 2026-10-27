#!/usr/bin/env python3
"""Memory / hysteresis characterization campaign driver (issue #159).

    python3 sim/run_memory.py auto    --series ID [--arm ARM ...] [--klt KLT] [--parallel N]
    python3 sim/run_memory.py round   --series ID --arm ARM --round K [--klt KLT] [--build-only]
    python3 sim/run_memory.py repeat  --series ID [--klt KLT]
    python3 sim/run_memory.py record  --series ID

Arms: ``nominal`` (5 process x 3 supply x 3 temperature = 45 points; one
request per process, 9 corners each), ``control-long`` (110 ns period) and
``control-short`` (11 ns period), the controls at tt / 1.20 V / 27 C only.

Every round of the 10-ary deterministic search (sim/kltsim/memory.py) is one
set of ``klt sim`` requests on the batch fleet; the next round's brackets are
derived from the committed envelopes of the previous one, so the whole search
replays from the committed files. NO ngspice is launched by this script.
``record`` replays the campaign and writes record.json / record.md. Campaign
inputs and envelopes are append-only: an existing file is only ever reused if
byte-identical.

CHARACTERIZATION, NOT COMPLIANCE (see sim/comparator-memory/README.md).
Run from the repository root.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kltsim import build as build_mod  # noqa: E402
from kltsim import cli as kcli  # noqa: E402
from kltsim import memory as mem  # noqa: E402
from kltsim.benches import PROCESSES  # noqa: E402

ARMS = {
    "nominal": {"period_ns": mem.NOMINAL_PERIOD_NS,
                "processes": [f"mos_{p}" for p in PROCESSES], "grid": None},
    "control-long": {"period_ns": mem.LONG_RESET_PERIOD_NS,
                     "processes": ["mos_tt"], "grid": [(1.2, 27)]},
    "control-short": {"period_ns": mem.SHORT_RESET_PERIOD_NS,
                      "processes": ["mos_tt"], "grid": [(1.2, 27)]},
}
DEFAULT_ARMS = list(ARMS)


def series_dir(series: str) -> Path:
    return mem.CAMPAIGNS_DIR / series


def round_dir(series: str, arm: str, k: int) -> Path:
    return series_dir(series) / arm / f"round{k}"


def arm_keys(arm: str) -> list[tuple]:
    spec = ARMS[arm]
    if spec["grid"] is None:
        return mem.grid_keys([p[4:] for p in spec["processes"]])
    return [(p, round(s, 3), float(t)) for p in spec["processes"] for s, t in spec["grid"]]


def tag_for(process: str) -> str:
    return f"{mem.BENCH_NAME}.{process}"


def git_state() -> dict:
    def run(*a):
        return subprocess.run(["git", *a], cwd=build_mod.REPO_ROOT, capture_output=True,
                              text=True, check=False).stdout.strip()
    status = [ln for ln in run("status", "--porcelain").splitlines()
              if "sim/comparator-memory/campaigns/" not in ln]
    return {"git_commit": run("rev-parse", "HEAD"), "git_branch": run("rev-parse", "--abbrev-ref", "HEAD"),
            "git_dirty_outside_campaign": bool(status)}


def plan_round(series: str, arm: str, k: int):
    """Replay rounds 1..k-1 and return (searches, plan_for_round_k)."""
    searches, done = replay(series, arm, upto=k - 1)
    if done != k - 1:
        raise SystemExit(f"{arm}: round {k - 1} is not complete (have {done}); run it first")
    return searches, mem.build_plan(searches, k)


def processes_with_work(searches, processes):
    out = []
    for proc in processes:
        if any(ps.active() for key, ps in searches.items() if key[0] == proc):
            out.append(proc)
    return out


def plan_inputs(series: str, arm: str, k: int):
    """(files, requests) for round k: [(path, bytes)], [(process, request_path, tag)]."""
    spec = ARMS[arm]
    searches, plan = plan_round(series, arm, k)
    first = k == 1
    step = mem.round_step_uv(k)
    rdir = round_dir(series, arm, k)
    files, reqs = [], []
    for proc in processes_with_work(searches, spec["processes"]):
        sub_plan = {key: v for key, v in plan.items() if key[0] == proc}
        tables = mem.lo_tables_for(sub_plan)
        title = f"memory {arm} round {k} {proc}"
        body = mem.compose_body(spec["period_ns"], first, step, tables, title=title)
        body_name = f"{tag_for(proc)}.body.spice"
        grid = spec["grid"]
        request = mem.compose_request(
            spec["period_ns"], first, body_name, [proc], grid=grid, round_no=k,
            comment=[f"arm {arm}, round {k} of {mem.MAX_ROUNDS}, process {proc}; probe spacing "
                     f"{step} uV; bracket lows are looked up per PVT point from the previous round."])
        request["_round"] = {"issue": 159, "arm": arm, "round": k, "step_uV": step,
                             "period_ns": spec["period_ns"]}
        files.append((rdir / body_name, body.encode("utf-8")))
        req_path = rdir / f"{tag_for(proc)}.request.json"
        files.append((req_path, (json.dumps(request, indent=2) + "\n").encode("utf-8")))
        reqs.append((proc, req_path, tag_for(proc)))
    return files, reqs


def replay(series: str, arm: str, upto: int | None = None):
    """Rebuild the searches of ``arm`` from the committed envelopes."""
    spec = ARMS[arm]
    searches = mem.new_searches(arm_keys(arm))
    done = 0
    for k in range(1, (upto or mem.MAX_ROUNDS) + 1):
        if not any(ps.active() for ps in searches.values()):
            break
        plan = mem.build_plan(searches, k)
        rdir = round_dir(series, arm, k)
        envs, complete = [], True
        for proc in processes_with_work(searches, spec["processes"]):
            path = rdir / f"{tag_for(proc)}.envelope.json"
            if not path.is_file():
                complete = False
                break
            envs.append(mem.load_json(path))
        if not complete:
            break
        merged = {"corners": [c for env in envs for c in (env.get("corners") or [])]}
        extracted = mem.extract_round(merged, spec["period_ns"], k == 1, plan)
        mem.apply_round(searches, extracted, k == 1)
        for key, ex in extracted.items():
            ps = searches.get(key)
            if ps is not None:
                ps.__dict__.setdefault("runtime_s", [])
                if ex.get("runtime_s") is not None:
                    ps.__dict__["runtime_s"].append(ex["runtime_s"])
        done = k
    return searches, done


def submit(request_path: Path, rdir: Path, tag: str, args, extra: dict) -> int:
    code = 1
    for attempt in range(1, args.retry_refused + 2):
        code = kcli._submit(request_path, rdir, tag, args, extra=extra)
        if code == 0 or not kcli._last_attempt_refused_at_cap(rdir):
            break
        if attempt <= args.retry_refused:
            print(f"{tag}: fleet at its instance cap; retry {attempt}/{args.retry_refused} "
                  f"in {args.retry_wait}s", file=sys.stderr)
            time.sleep(args.retry_wait)
    return code


def run_round(series: str, arms: list[str], k: int, args) -> int:
    jobs = []
    git = git_state()
    for arm in arms:
        searches, done = replay(series, arm, upto=k - 1)
        if done != k - 1:
            print(f"{arm}: round {k - 1} incomplete; skipping round {k}", file=sys.stderr)
            continue
        if not any(ps.active() for ps in searches.values()):
            print(f"{arm}: search finished before round {k}", file=sys.stderr)
            continue
        files, reqs = plan_inputs(series, arm, k)
        if not kcli._commit_planned(files, argparse.Namespace(force=False), f"{arm} r{k}"):
            return 1
        for proc, req_path, tag in reqs:
            rdir = round_dir(series, arm, k)
            if (rdir / f"{tag}.envelope.json").exists():
                print(f"{arm} r{k} {tag}: envelope present, skipped", file=sys.stderr)
                continue
            jobs.append((req_path, rdir, tag, {"issue": 159, "arm": arm, "round": k, **git}))
    if args.build_only:
        return 0
    rc = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        futs = [ex.submit(submit, *j[:3], args, j[3]) for j in jobs]
        for f in futs:
            rc = max(rc, f.result())
    return rc


def cmd_round(args) -> int:
    return run_round(args.series, [args.arm], args.round, args)


def cmd_auto(args) -> int:
    arms = args.arm or DEFAULT_ARMS
    rc = 0
    for k in range(1, mem.MAX_ROUNDS + 1):
        rc = max(rc, run_round(args.series, arms, k, args))
        if rc:
            print(f"round {k} had failures (rc={rc}); stopping so nothing runs on a partial round",
                  file=sys.stderr)
            return rc
    return rc


# --------------------------------------------------------------------------- #
# repeat (determinism)
# --------------------------------------------------------------------------- #

REPEAT_POINT = ("mos_tt", 1.2, 27.0)


def cmd_repeat(args) -> int:
    """Re-submit the nominal tt / 1.20 V / 27 C point for each round, using the
    SAME body (so the same probe plan) as the nominal campaign, narrowed to
    that one corner. Decisions must reproduce exactly."""
    git = git_state()
    jobs = []
    for k in range(1, mem.MAX_ROUNDS + 1):
        src = round_dir(args.series, "nominal", k)
        body_src = src / f"{tag_for('mos_tt')}.body.spice"
        if not body_src.is_file():
            continue
        rdir = round_dir(args.series, "repeat", k)
        body_bytes = body_src.read_bytes()
        req = mem.load_json(src / f"{tag_for('mos_tt')}.request.json")
        req["corners"]["supply_v"] = {"vsup": [1.2]}
        req["corners"]["temperature_c"] = [27]
        req["_comment"] = req["_comment"] + [
            "DETERMINISM REPEAT: the nominal campaign's round body, narrowed to tt / 1.20 V / 27 C."]
        req["_round"] = dict(req.get("_round") or {}, arm="repeat")
        files = [(rdir / body_src.name, body_bytes),
                 (rdir / f"{tag_for('mos_tt')}.request.json",
                  (json.dumps(req, indent=2) + "\n").encode("utf-8"))]
        if not kcli._commit_planned(files, argparse.Namespace(force=False), f"repeat r{k}"):
            return 1
        tag = tag_for("mos_tt")
        if (rdir / f"{tag}.envelope.json").exists():
            continue
        jobs.append((rdir / f"{tag}.request.json", rdir, tag,
                     {"issue": 159, "arm": "repeat", "round": k, **git}))
    rc = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.parallel)) as ex:
        futs = [ex.submit(submit, *j[:3], args, j[3]) for j in jobs]
        for f in futs:
            rc = max(rc, f.result())
    return rc


# --------------------------------------------------------------------------- #
# record
# --------------------------------------------------------------------------- #

def _envelope_provenance(series: str) -> dict:
    jobs, engine, models_sha = [], set(), set()
    klt_versions = set()
    for env_path in sorted(series_dir(series).glob("*/round*/*.envelope.json")):
        env = mem.load_json(env_path)
        e = env.get("environment") or {}
        remote = e.get("remote") or {}
        engine.add(str(e.get("engine_version")))
        models_sha.add(e.get("models_lib_sha256"))
        inv_path = env_path.with_name(env_path.name.replace(".envelope.json", ".invocation.json"))
        inv = mem.load_json(inv_path) if inv_path.is_file() else {}
        klt_versions.add(inv.get("klt_version"))
        jobs.append({
            "request": kcli._rel(env_path).as_posix().replace(
                ".envelope.json", ".request.json"),
            "backend": "batch" if remote.get("job_id") else "local",
            "job_id": remote.get("job_id"),
            "instance_type": remote.get("instance_type"),
            "lifecycle": remote.get("lifecycle"),
            "corner_count": env.get("corner_count"),
            "status": env.get("status"),
            "netlist_sha256": e.get("netlist_sha256"),
            "git_commit": inv.get("git_commit"),
            "started_utc": inv.get("started_utc"),
        })
    return {"requests": jobs, "ngspice_engine_versions": sorted(engine),
            "models_lib_sha256": sorted(x for x in models_sha if x),
            "klt_versions": sorted(x for x in klt_versions if x)}


def _point_row(key, ps: mem.PointSearch) -> dict:
    proc, supply, temp = key
    row = {"process": proc[4:], "supply_v": supply, "temperature_c": temp,
           "corner": f"{proc[4:]}/{supply:.2f}V/{temp:g}C"}
    if ps.problem:
        row.update({"threshold_after_P_mV": None, "threshold_after_N_mV": None,
                    "memory_shift_mV": None, "abs_memory_shift_mV": None,
                    "final_bracket_width_uV": {"P": None, "N": None},
                    "rejected": {"point": ps.problem},
                    "classification_total": {k: ps.P.tally[k] + ps.N.tally[k] for k in ps.P.tally},
                    "P": mem.history_result(ps.P), "N": mem.history_result(ps.N)})
    else:
        row.update(mem.point_result(ps.P, ps.N))
    rt = ps.__dict__.get("runtime_s") or []
    row["runtime_s_total"] = sum(rt) if rt else None
    return row


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["memory_shift_mV"] is not None]
    rej = [r for r in rows if r["memory_shift_mV"] is None]
    tot = {k: sum(r["classification_total"][k] for r in rows)
           for k in ("evaluated", "resolved_positive", "resolved_negative", "unresolved",
                     "wrong_polarity", "missing")}
    shifts = [r["memory_shift_mV"] for r in ok]
    out = {"points": len(rows), "points_with_two_thresholds": len(ok),
           "points_rejected": len(rej),
           "rejected_points": [{"corner": r["corner"], "cause": r["rejected"]} for r in rej],
           "probe_classification_total": tot,
           "points_with_any_unresolved": sum(1 for r in rows if r["classification_total"]["unresolved"]),
           "points_with_any_wrong_polarity": sum(1 for r in rows if r["classification_total"]["wrong_polarity"])}
    if shifts:
        worst = max(ok, key=lambda r: abs(r["memory_shift_mV"]))
        out.update({
            "memory_shift_mV": {"min": min(shifts), "max": max(shifts),
                                "mean": sum(shifts) / len(shifts)},
            "abs_memory_shift_mV_max": abs(worst["memory_shift_mV"]),
            "worst_point": worst["corner"],
            "max_final_bracket_width_uV": max(max(r["final_bracket_width_uV"].values()) for r in ok),
        })
    return out


def build_record(series: str) -> dict:
    arms = {}
    for arm in ARMS:
        searches, done = replay(series, arm)
        rows = [_point_row(k, searches[k]) for k in arm_keys(arm)]
        arms[arm] = {"rounds_completed": done, "all_searches_closed":
                     all(not ps.active() for ps in searches.values()), "rows": rows}
    nominal = arms["nominal"]
    record = {
        "schema": "sg13g2-comparator/memory-record/1",
        "issue": 159,
        "series": series,
        "kind": "characterization",
        "not_compliance": ("Characterization only. No specification row is added, changed or "
                           "claimed; a spec claim needs a separate DR-0002 decision record."),
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git": git_state(),
        "dut": {"sim_dut_json": "sim/dut.json",
                "netlist_sha256": build_mod.sha256_file(build_mod.load_dut_binding()["_netlist_path"])},
        "contract": {
            "histories": {"P": "3 conditioning strobes at +50 mV, then the swept probe",
                          "N": "3 conditioning strobes at -50 mV, then the identical swept probe"},
            "mismatch": "off (plain mos_<p> sections); no Monte Carlo, so no seeds or run counts",
            "search": ("deterministic 10-ary search, integer uV: 100 mV -> 10 mV -> 1 mV -> 100 uV -> "
                       "10 uV in four sequential klt sim rounds (round 1 = 11 probes incl. endpoints, "
                       "rounds 2-4 = 9 interior probes)"),
            "search_range_mV": [mem.INIT_LO_UV / 1000, mem.INIT_HI_UV / 1000],
            "final_bracket_limit_uV": mem.RESOLUTION_UV,
            "threshold": "midpoint of the final bracket whose ends resolve to opposite polarities",
            "decision": "(V(dout)-V(doutb))/VDD at 9 ns after the fourth rising edge",
            "resolved_threshold": mem.RESOLVED_THRESHOLD,
            "timing": {
                "nominal": mem.clock_times_ns(mem.NOMINAL_PERIOD_NS) | {"period_ns": mem.NOMINAL_PERIOD_NS,
                                                                       "high_ns": mem.HIGH_NS},
                "control-long": mem.clock_times_ns(mem.LONG_RESET_PERIOD_NS) | {"period_ns": mem.LONG_RESET_PERIOD_NS},
                "control-short": mem.clock_times_ns(mem.SHORT_RESET_PERIOD_NS) | {"period_ns": mem.SHORT_RESET_PERIOD_NS},
            },
            "solver_options": list(mem.OPTIONS),
        },
        "provenance": _envelope_provenance(series),
        "nominal": {"rounds_completed": nominal["rounds_completed"],
                    "all_searches_closed": nominal["all_searches_closed"],
                    "summary": summarize(nominal["rows"]), "points": nominal["rows"]},
    }
    # controls
    ctrl = {}
    for name, arm in (("long", "control-long"), ("short", "control-short")):
        row = arms[arm]["rows"][0]
        ctrl[name] = {"arm": arm, "rounds_completed": arms[arm]["rounds_completed"],
                      "closed": arms[arm]["all_searches_closed"], "point": row,
                      "shift_uV": None if row["memory_shift_mV"] is None else row["memory_shift_mV"] * 1000.0}
    lv = mem.long_reset_verdict(ctrl["long"]["shift_uV"])
    sv = mem.short_reset_verdict(ctrl["short"]["shift_uV"], ctrl["long"]["shift_uV"])
    if not ctrl["long"]["closed"] or not ctrl["short"]["closed"]:
        for v in (lv, sv):
            if v["verdict"] == "PASS":
                v["verdict"] = "INCOMPLETE"
                v["reason"] = "control search not closed"
    sensitivity = "PASS" if (lv["verdict"] == "PASS" and sv["verdict"] == "PASS") else (
        "INCOMPLETE" if "INCOMPLETE" in (lv["verdict"], sv["verdict"]) else "FAIL")
    record["controls"] = {
        "point": "tt / 1.20 V / 27 C", "long_reset": {**ctrl["long"], "verdict": lv},
        "short_reset": {**ctrl["short"], "verdict": sv},
        "bench_sensitivity_control": sensitivity,
        "interpretation": (
            "The short-reset sensitivity control PASSED: the bench resolves a history-dependent shift "
            "when reset is deliberately incomplete, so the nominal 45-point shifts are meaningful "
            "at the stated search resolution." if sensitivity == "PASS" else
            "A control did not pass. A 'no measurable memory' conclusion is NOT supported by this "
            "record; a near-zero nominal shift must not be read as evidence of no memory."),
    }
    # determinism repeat
    rep = []
    for k in range(1, mem.MAX_ROUNDS + 1):
        a = series_dir(series) / "nominal" / f"round{k}" / f"{tag_for('mos_tt')}.envelope.json"
        b = series_dir(series) / "repeat" / f"round{k}" / f"{tag_for('mos_tt')}.envelope.json"
        if not (a.is_file() and b.is_file()):
            continue
        va = _repeat_values(mem.load_json(a))
        vb = _repeat_values(mem.load_json(b))
        diffs = {n: [va.get(n), vb.get(n)] for n in sorted(set(va) | set(vb))
                 if va.get(n) != vb.get(n)}
        rep.append({"round": k, "values_compared": len(vb), "identical": not diffs,
                    "max_abs_difference": max((abs(x[0] - x[1]) for x in diffs.values()
                                               if x[0] is not None and x[1] is not None), default=0.0),
                    "differences": diffs})
    record["determinism_repeat"] = {"point": "tt / 1.20 V / 27 C", "rounds": rep,
                                    "all_identical": bool(rep) and all(r["identical"] for r in rep)}
    return record


def _repeat_values(env: dict) -> dict:
    for c in env.get("corners") or []:
        if c.get("process") == "mos_tt" and abs(c["supply_v"]["vsup"] - 1.2) < 1e-6 \
                and abs(c["temperature_c"] - 27) < 1e-6:
            return {m["name"]: m.get("value") for m in c["measurements"]}
    return {}


def render_markdown(rec: dict) -> str:
    L = [f"# Memory / hysteresis characterization record `{rec['series']}` (issue #159)", "",
         "**Characterization, not compliance.** " + rec["not_compliance"], "",
         f"- git: `{rec['git']['git_commit']}` ({rec['git']['git_branch']})",
         f"- generated: {rec['generated_utc']}",
         f"- ngspice engine(s): {', '.join(rec['provenance']['ngspice_engine_versions'])}; "
         f"klt: {', '.join(rec['provenance']['klt_versions'])}",
         f"- DUT netlist sha256: `{rec['dut']['netlist_sha256']}`",
         "- mismatch off, deterministic search: no seeds or Monte-Carlo run counts apply.",
         f"- search: {rec['contract']['search']}", ""]
    c = rec["controls"]
    L += ["## Controls (tt / 1.20 V / 27 C)", "",
          "| control | period | shift (uV) | verdict | note |", "|---|---|---|---|---|"]
    for name, per in (("long_reset", "110 ns (100 ns reset)"), ("short_reset", "11 ns (1 ns reset)")):
        x = c[name]
        s = x["shift_uV"]
        L.append(f"| {name} | {per} | {'rejected' if s is None else f'{s:+.1f}'} | "
                 f"**{x['verdict']['verdict']}** | {x['verdict'].get('reason') or x['verdict'].get('criterion')} |")
    L += ["", f"Bench sensitivity control: **{c['bench_sensitivity_control']}**. {c['interpretation']}", ""]
    n = rec["nominal"]
    s = n["summary"]
    L += ["## Nominal 45-point grid", "",
          f"- points with two thresholds: {s['points_with_two_thresholds']}/{s['points']}; rejected: {s['points_rejected']}"]
    t = s["probe_classification_total"]
    L.append(f"- probes evaluated {t['evaluated']}: resolved+ {t['resolved_positive']}, resolved- "
             f"{t['resolved_negative']}, **unresolved {t['unresolved']}**, **wrong-polarity {t['wrong_polarity']}** "
             f"(counted separately), missing {t['missing']}")
    if "memory_shift_mV" in s:
        m = s["memory_shift_mV"]
        L.append(f"- memory shift (P - N): min {m['min']*1000:+.1f} uV, max {m['max']*1000:+.1f} uV, mean "
                 f"{m['mean']*1000:+.1f} uV; largest |shift| {s['abs_memory_shift_mV_max']*1000:.1f} uV at "
                 f"`{s['worst_point']}`; widest final bracket {s['max_final_bracket_width_uV']} uV")
    for r in s["rejected_points"]:
        L.append(f"- REJECTED `{r['corner']}`: {r['cause']}")
    L += ["", "| corner | thr after P (mV) | thr after N (mV) | shift (uV) | bracket P/N (uV) | unres | wrong-pol |",
          "|---|---|---|---|---|---|---|"]
    for r in n["points"]:
        if r["memory_shift_mV"] is None:
            L.append(f"| {r['corner']} | - | - | rejected | - | {r['classification_total']['unresolved']} | "
                     f"{r['classification_total']['wrong_polarity']} |")
            continue
        L.append(f"| {r['corner']} | {r['threshold_after_P_mV']:+.5f} | {r['threshold_after_N_mV']:+.5f} | "
                 f"{r['memory_shift_mV']*1000:+.1f} | {r['final_bracket_width_uV']['P']}/{r['final_bracket_width_uV']['N']} | "
                 f"{r['classification_total']['unresolved']} | {r['classification_total']['wrong_polarity']} |")
    d = rec["determinism_repeat"]
    L += ["", "## Determinism repeat (tt / 1.20 V / 27 C)", ""]
    if d["rounds"]:
        L.append(f"All rounds bit-identical: **{d['all_identical']}** "
                 f"(rounds: {', '.join(str(r['round']) for r in d['rounds'])}).")
    else:
        L.append("Not run.")
    L += ["", "## Batch provenance", ""]
    for j in rec["provenance"]["requests"]:
        L.append(f"- `{j['request']}`: {j['backend']} job `{j['job_id']}` "
                 f"({j['corner_count']} corners, status {j['status']})")
    return "\n".join(L) + "\n"


def cmd_record(args) -> int:
    rec = build_record(args.series)
    out = series_dir(args.series)
    (out / "record.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    (out / "record.md").write_text(render_markdown(rec), encoding="utf-8")
    s = rec["nominal"]["summary"]
    print(f"nominal: {s['points_with_two_thresholds']}/{s['points']} points, rejected "
          f"{s['points_rejected']}, classification {s['probe_classification_total']}")
    for name in ("long_reset", "short_reset"):
        x = rec["controls"][name]
        print(f"control {name}: shift {x['shift_uV']} uV -> {x['verdict']['verdict']}")
    print("sensitivity control:", rec["controls"]["bench_sensitivity_control"])
    print("determinism repeat identical:", rec["determinism_repeat"]["all_identical"])
    return 0


def main(argv: list[str] | None = None) -> int:
    default_klt = shutil.which("klt") or "klt"
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def submit_opts(p):
        p.add_argument("--klt", default=default_klt)
        p.add_argument("--retry-refused", type=int, default=3)
        p.add_argument("--retry-wait", type=int, default=120)
        p.add_argument("--parallel", type=int, default=3,
                       help="concurrent klt sim submissions (each runs on the batch fleet)")
        p.add_argument("--build-only", action="store_true")
        p.add_argument("--force", action="store_true", help=argparse.SUPPRESS)

    a = sub.add_parser("auto")
    a.add_argument("--series", required=True)
    a.add_argument("--arm", action="append", choices=list(ARMS))
    submit_opts(a)
    a.set_defaults(func=cmd_auto)

    r = sub.add_parser("round")
    r.add_argument("--series", required=True)
    r.add_argument("--arm", required=True, choices=list(ARMS))
    r.add_argument("--round", type=int, required=True)
    submit_opts(r)
    r.set_defaults(func=cmd_round)

    rp = sub.add_parser("repeat")
    rp.add_argument("--series", required=True)
    submit_opts(rp)
    rp.set_defaults(func=cmd_repeat)

    rc = sub.add_parser("record")
    rc.add_argument("--series", required=True)
    rc.set_defaults(func=cmd_record)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

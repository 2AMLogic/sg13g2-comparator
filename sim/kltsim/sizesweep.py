"""Joint input-pair sizing study report (issue #92).

Reads a study campaign ``campaigns/ID/`` holding two kinds of sub-campaign
directories, each a normal ``kltsim`` campaign directory (bodies, requests,
envelopes, attempts):

``scr_<name>/``   SCREENING: the fast benches (kickback, regeneration) on the
                  reduced grid of :func:`screen_request` (tt/ff/ss x 1.08/1.32 V
                  x -40/27/125 C = 18 points, including the binding corner
                  ``ff_125c_1.32v``). Screening numbers are deterministic
                  single-draw values at those points; they are NOT a 45-point
                  verdict and are never graded as one.
``full_<name>/``  FINALISTS: the complete 45-point grid for every bench, graded
                  by the SAME ``kltsim.grade`` rules as the issue #62 campaign
                  (Rows 1-5), Monte Carlo offset N=60 / noise N=80 included.

    python3 sim/run_klt_corner_verification.py sizesweep --campaign ID

The geometry of each candidate is read back from the committed body header
(``GEOMETRY OVERRIDE`` line) so the table cannot disagree with what was
simulated. Nothing here proposes a bound or edits the DUT or the spec: it is
the evidence an operator decision (adopt a sizing / relax a row / reopen
DR-0001) would be founded on.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import build as build_mod
from . import grade as grade_mod
from . import ibsweep as ibsweep_mod

SCREEN_PROCESSES = ("mos_tt", "mos_ff", "mos_ss")
SCREEN_SUPPLIES_V = (1.08, 1.32)
SCREEN_TEMPERATURES_C = (-40, 27, 125)
#: the point Row 4a binds at in the issue #62 baseline campaign
BINDING_PT = ("mos_ff", 1.32, 125.0)

#: Target rows tabulated for finalists: (row id, label, unit)
FULL_ROWS = (
    ("1", "offset 3 sigma, worst pt (MC N=60)", "mV"),
    ("2", "noise, grid mean (probit, N=80)", "mV rms"),
    ("3a", "t_d @ 50 mV, worst", "ns"),
    ("3b", "tau, worst", "ps"),
    ("3c", "t_d @ 0.1 mV, worst", "ns"),
    ("4a", "Q_kick, worst side, worst pt", "fC"),
    ("4b", "signal-dep. residue, worst", "uV"),
    ("5b", "avg power, worst", "uW"),
)


def screen_request(data: bytes) -> bytes:
    """A built full-grid request rewritten to the screening grid."""
    request = json.loads(data.decode("utf-8"))
    keys = list((request["corners"].get("supply_v") or {}))
    request["corners"] = {
        "process": list(SCREEN_PROCESSES),
        "supply_v": {k: list(SCREEN_SUPPLIES_V) for k in keys},
        "temperature_c": list(SCREEN_TEMPERATURES_C),
    }
    request.pop("remote", None)
    request["_comment"].append(
        "SCREENING GRID (issue #92): tt/ff/ss x 1.08/1.32 V x -40/27/125 C = 18 points. "
        "Not a 45-point verdict; never graded as one.")
    return (json.dumps(request, indent=2) + "\n").encode("utf-8")


def screen_corners(bench) -> dict:
    """The expected screening grid for ``bench`` (what :func:`screen_request`
    writes): 3 processes x 2 supplies x 3 temperatures = 18 points."""
    return {
        "process": list(SCREEN_PROCESSES),
        "supply_v": {k: list(SCREEN_SUPPLIES_V) for k in bench.supply_keys},
        "temperature_c": list(SCREEN_TEMPERATURES_C),
    }


def _pt(process: str, supply: float, temp: float) -> tuple:
    return (grade_mod._process_name(process), round(float(supply), 6), float(temp))


#: the explicit expected screening grid (18 points), keyed (process, V, degC)
EXPECTED_POINTS = tuple(_pt(p, v, t) for p in SCREEN_PROCESSES
                        for v in SCREEN_SUPPLIES_V for t in SCREEN_TEMPERATURES_C)
_BINDING = _pt(*BINDING_PT)

#: screening metric -> (bench, measurement, scale to published unit, required decision gates).
#: A point supplies a metric only if the corner succeeded, its probes match the
#: corner, the value is finite and unique, and every listed gate is present,
#: finite, unique and inside the bench's own gate limits (decided both ways).
SCREEN_METRICS = {
    "qkick_worst": ("kickback", "qkick_fc", 1.0, ("dout_1k_end",)),
    "sigdep_worst": ("kickback", "kick_sigdep_uv", 1.0,
                     ("dout_float_small_end", "dout_float_big_end")),
    "td50_worst": ("regeneration", "td_od50_ns", 1.0, ("dout_od50_first", "dout_od50_end")),
    "td01_worst": ("regeneration", "td_od01_ns", 1.0, ("dout_od01_first", "dout_od01_end")),
    "tau_worst": ("regeneration", "tau_ps", 1.0,
                  ("dout_od1_first", "dout_od1_end", "dout_od01_first", "dout_od01_end")),
    "p_avg_worst": ("regeneration", "p_avg", 1e6, ()),
}
SCREEN_BENCHES = ("kickback", "regeneration")
_OK_STATUS = ("pass", "fail")  # `fail` = a Target limit missed, a valid measurement


def _geometry_report(sub: Path, bench_names) -> tuple[dict, list[str]]:
    """(candidate geometry, problems). Every bench body is read; bodies that
    declare different overrides cannot be attributed to one candidate."""
    found: dict[str, dict] = {}
    problems: list[str] = []
    for name in bench_names:
        body = sub / f"{name}.body.spice"
        if not body.is_file():
            continue
        try:
            found[name] = build_mod.extract_geometry(body.read_text(encoding="utf-8"))
        except build_mod.BuildError as exc:
            problems.append(f"{name}: unreadable geometry override ({exc})")
    distinct = {json.dumps(g, sort_keys=True) for g in found.values()}
    if len(distinct) > 1:
        problems.append("inconsistent candidate geometry across benches: " + "; ".join(
            f"{n} {_geom(g)}" for n, g in sorted(found.items())))
        return {}, problems
    return (next(iter(found.values())) if found and not problems else {}), problems


def _fmt_pt(key) -> str:
    return "?" if key is None else f"{key[0].replace('mos_', '')}_{key[2]:g}c_{key[1]:g}v"


def _gate_ok(spec_meas, value: float) -> bool:
    lim = (spec_meas.limits if spec_meas is not None else None) or {}
    return ("min" not in lim or value >= lim["min"]) and ("max" not in lim or value <= lim["max"])


def _bench_points(ev, expected_set) -> tuple[dict, list[str]]:
    """expected key -> corner dict, or None when ambiguous; plus notes."""
    seen: dict[tuple, list] = {}
    notes: list[str] = []
    for tag, env in ev.envelopes:
        for corner in env.get("corners") or []:
            if not isinstance(corner, dict):
                notes.append(f"{tag}: non-object corner entry ignored")
                continue
            if corner.get("monte_carlo") is not None:
                notes.append(f"{tag}: Monte Carlo corner {corner.get('corner_id')} is not screening evidence")
                continue
            key = grade_mod._corner_key(corner)
            if key is None:
                notes.append(f"{tag}: corner {corner.get('corner_id')} has no placeable PVT key")
                continue
            if key not in expected_set:
                notes.append(f"{tag}: corner {corner.get('corner_id')} {_fmt_pt(key)} is outside the screening grid")
                continue
            seen.setdefault(key, []).append((tag, corner))
    points = {}
    for key, hits in seen.items():
        if len(hits) > 1:
            notes.append(f"duplicate PVT result for {_fmt_pt(key)}: "
                         + "; ".join(sorted(f"{t}:{c.get('corner_id')}" for t, c in hits))
                         + "; no result selected")
            points[key] = None
        else:
            points[key] = hits[0][1]
    return points, notes


def _point_problem(corner: dict, bench_name: str) -> str | None:
    """Why NONE of this corner's numbers can be trusted, or None."""
    status = corner.get("status")
    if status not in _OK_STATUS:
        codes = ",".join(sorted({str(d.get("code", "?")) for d in corner.get("diagnostics") or []
                                 if isinstance(d, dict)}))
        return f"corner status {status!r} is not a successful run" + (f" ({codes})" if codes else "")
    ms = corner.get("measurements")
    if not isinstance(ms, list) or not all(isinstance(m, dict) and "name" in m for m in ms):
        return "malformed measurement list"
    spec = grade_mod._bench_spec(bench_name)
    probes = set(spec.probes.get("supply", ())) | ({spec.probes["temperature"]}
                                                   if spec.probes.get("temperature") else set())
    names = [m["name"] for m in ms]
    dup = sorted(n for n in probes if names.count(n) > 1)
    if dup:
        return f"duplicate probe measurement(s) {', '.join(dup)}"
    return grade_mod._corner_problems(corner, bench_name, [])


def _meas_value(corner: dict, name: str):
    hits = [m for m in corner.get("measurements") or [] if m["name"] == name]
    if not hits:
        return None, f"{name} not reported"
    if len(hits) > 1:
        return None, f"duplicate measurement name {name}"
    try:
        return grade_mod.finite(hits[0].get("value"), name), None
    except grade_mod.NonFiniteError as exc:
        return None, str(exc)


def _reduce_metric(points: dict, bench_name: str, meas: str, scale: float, gates, point_problems: dict):
    """-> (values {key: v}, rejections [str])."""
    spec = grade_mod._bench_spec(bench_name)
    by_name = {m.name: m for m in spec.measurements}
    values, rejected = {}, []
    for key in EXPECTED_POINTS:
        corner = points.get(key)
        if key not in points:
            continue
        if corner is None:
            rejected.append(f"{_fmt_pt(key)}: ambiguous duplicate PVT result")
            continue
        if point_problems.get(key):
            rejected.append(f"{_fmt_pt(key)}: {point_problems[key]}")
            continue
        reason = None
        for g in gates:
            gv, why = _meas_value(corner, g)
            if why:
                reason = f"decision gate {why}"
            elif not _gate_ok(by_name.get(g), gv):
                reason = f"decision gate {g}={gv:g} failed"
            if reason:
                break
        if reason is None:
            v, why = _meas_value(corner, meas)
            reason = why
        if reason:
            rejected.append(f"{_fmt_pt(key)}: {reason}")
        else:
            values[key] = v * scale
    return values, rejected


def _bench_reasons(ev, dut) -> list[str]:
    reasons = list(ev.chain_problems)
    if not ev.envelopes:
        reasons.append("no envelope present")
    reasons += grade_mod.check_dut(ev, dut)
    return reasons


def _metric_cell(values: dict, rejected: list[str], present: int, gates, bench_reasons) -> dict:
    n = len(EXPECTED_POINTS)
    complete = not bench_reasons and len(values) == n
    worst = max(values.items(), key=lambda kv: kv[1]) if complete else None
    return {
        "available": complete,
        "value": None if worst is None else worst[1],
        "point": None if worst is None else _fmt_pt(worst[0]),
        "expected": n, "present": present,
        "valid": 0 if bench_reasons else len(values),
        "required_gates": list(gates),
        "rejections": list(rejected),
    }


def screen(campaign_dir: Path) -> list[dict]:
    """Validated screening reduction (issue #122).

    Per candidate and per bench: the saved request must be the bench contract
    with ONLY the screening grid substituted, the request/invocation/envelope
    chain must hash-match, and the body's DUT must be today's DUT plus its
    declared geometry. Per metric, a point is valid only if the corner
    succeeded, its probes match, value and gates are finite, unique and
    passing. A worst-of-screen value is published only when all 18 points are
    valid; otherwise it is unavailable (None) with the reasons retained.
    """
    dut = grade_mod.load_dut_reference()
    expected_set = set(EXPECTED_POINTS)
    rows = []
    for sub in sorted(p for p in campaign_dir.iterdir() if p.is_dir() and p.name.startswith("scr_")):
        geometry, geom_problems = _geometry_report(sub, SCREEN_BENCHES)
        loaded = {}
        for name in SCREEN_BENCHES:
            bench = grade_mod._bench_spec(name)
            ev = grade_mod.load_campaign(sub, corners=screen_corners(bench),
                                         bench_names=(name,))[name]
            points, notes = _bench_points(ev, expected_set)
            reasons = _bench_reasons(ev, dut) + geom_problems
            ppb = {k: _point_problem(c, name) for k, c in points.items() if c is not None}
            loaded[name] = {"points": points, "notes": notes, "reasons": reasons, "ppb": ppb}
        row = {"name": sub.name[len("scr_"):], "dir": sub.name, "geometry": geometry,
               "geometry_problems": geom_problems, "metrics": {}, "benches": {}}
        for name, d in loaded.items():
            row["benches"][name] = {
                "expected": len(EXPECTED_POINTS), "present": len(d["points"]),
                "missing_points": [_fmt_pt(k) for k in EXPECTED_POINTS if k not in d["points"]],
                "evidence_rejections": d["reasons"], "notes": d["notes"],
            }
        for mname, (bname, meas, scale, gates) in SCREEN_METRICS.items():
            d = loaded[bname]
            vals, rej = _reduce_metric(d["points"], bname, meas, scale, gates, d["ppb"])
            row["metrics"][mname] = _metric_cell(vals, rej, len(d["points"]), gates, d["reasons"])
            if mname == "qkick_worst":
                # binding-point charge: same validity rules, that one point only
                bind_ok = not d["reasons"] and _BINDING in vals
                bind_why = [r for r in rej if r.startswith(_fmt_pt(_BINDING) + ":")]
                if not bind_ok and not bind_why:
                    bind_why = [f"{_fmt_pt(_BINDING)}: " + (
                        "bench evidence rejected" if d["reasons"] else "binding point not present")]
                row["metrics"]["qkick_binding"] = {
                    "available": bind_ok, "value": vals[_BINDING] if bind_ok else None,
                    "point": _fmt_pt(_BINDING), "expected": 1,
                    "present": int(_BINDING in d["points"]), "valid": int(bind_ok),
                    "required_gates": list(gates), "rejections": bind_why}
        rows.append(row)
    return rows


def full(campaign_dir: Path) -> list[dict]:
    out = []
    for sub in sorted(p for p in campaign_dir.iterdir() if p.is_dir() and p.name.startswith("full_")):
        graded = grade_mod.grade_campaign(sub)
        by_id = {r["id"]: r for r in graded["rows"]}
        cells = {}
        for row_id, _l, _u in FULL_ROWS:
            entry = by_id.get(row_id)
            if entry is not None and entry["target_verdict"] == grade_mod.INCOMPLETE \
                    and ((entry.get("target") or {}).get("points_valid") or 0) == 0:
                entry = None
            cells[row_id] = ibsweep_mod._cell(entry)
        geometry, geom_problems = _geometry_report(sub, tuple(grade_mod._bench_names()))
        out.append({"name": sub.name[len("full_"):], "dir": sub.name,
                    "geometry": geometry, "geometry_problems": geom_problems, "rows": cells})
    return out


def _geom(g: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in sorted(g.items())) or "baseline (design/comparator.spice as committed)"


def _geom_full(r: dict) -> str:
    return "INCONSISTENT / UNREADABLE" if r.get("geometry_problems") else _geom(r["geometry"])


def _f(x, d=4):
    return "-" if x is None else f"{x:.{d}g}"


def _mc(cell, binding=False):
    if not cell["available"]:
        return f"unavailable ({cell['valid']}/{cell['expected']} valid)"
    return _f(cell["value"]) if binding else f"{_f(cell['value'])} @ {cell['point']}"


def _w(cell, scale=1.0):
    return "-" if cell is None else f"{_f(cell['value'] * scale)} @ {cell['point']}"


def render_markdown(result: dict) -> str:
    L = [f"# Input-pair sizing study -- campaign `{result['campaign']}` (issue #92)", "",
         "GENERATED by `python3 sim/run_klt_corner_verification.py sizesweep`. Proposes no bound, "
         "changes no spec row, no DUT and not `sim/dut.json`. Any candidate implies a layout "
         "regeneration (the committed GDS is generated from `design/comparator.spice`) and a "
         "DRC/LVS re-run if it were adopted.", ""]
    if result["screen"]:
        L += ["## Screening (fast benches, reduced 18-point grid; NOT a 45-point verdict)", "",
              "Grid: tt/ff/ss x 1.08/1.32 V x -40/27/125 C. Deterministic, mismatch off, one draw per "
              "point. Q_kick target <= 25 fC/side (Row 4a); `Q_kick @ binding` is `ff_125c_1.32v`, the "
              "baseline's 45-point binding corner. Validated reduction (issue #122): a worst-of-screen "
              "value is shown only when all 18 expected points are valid for that metric; otherwise "
              "the cell reads `unavailable (valid/expected)` and the reasons are listed below.", "",
              "| candidate | geometry override | Q_kick @ binding [fC] | Q_kick worst of screen [fC] | t_d 50 mV worst [ns] | t_d 0.1 mV worst [ns] | tau worst [ps] | sig-dep residue worst [uV] | power worst [uW] |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in result["screen"]:
            m = r["metrics"]
            geo = _geom(r["geometry"]) if not r["geometry_problems"] else "INCONSISTENT / UNREADABLE"
            L.append(f"| {r['name']} | {geo} | {_mc(m['qkick_binding'], True)} | {_mc(m['qkick_worst'])} | "
                     f"{_mc(m['td50_worst'])} | {_mc(m['td01_worst'])} | {_mc(m['tau_worst'])} | "
                     f"{_mc(m['sigdep_worst'])} | {_mc(m['p_avg_worst'])} |")
        L += ["", "### Screening evidence validation (expected / present / valid points)", "",
              "| candidate | bench | expected | present | evidence rejections | missing points |",
              "|---|---|---|---|---|---|"]
        for r in result["screen"]:
            for bname, b in r["benches"].items():
                L.append(f"| {r['name']} | {bname} | {b['expected']} | {b['present']} | "
                         f"{'; '.join(b['evidence_rejections']) or '-'} | {', '.join(b['missing_points']) or '-'} |")
        L += ["", "| candidate | metric | required gates | present | valid | rejection reasons (first 3; all in sizesweep.json) |",
              "|---|---|---|---|---|---|"]
        for r in result["screen"]:
            for mname, c in r["metrics"].items():
                L.append(f"| {r['name']} | {mname} | {', '.join(c['required_gates']) or '-'} | "
                         f"{c['present']}/{c['expected']} | {c['valid']}/{c['expected']} | "
                         f"{'; '.join(c['rejections'][:3]) or '-'} |")
        L.append("")
    if result["full"]:
        L += ["## Finalists: full 45-point grid, Rows 1-5 graded by `kltsim.grade`", "",
              "Row 1 offset: Monte Carlo over the shipped mismatch models, N = 60 per point, worst of 45. "
              "Row 2 noise: transient-noise probit statistic, N = 80 per rung, grid-wide mean. "
              "Seeds are the bench defaults, committed in each request. Rows 3-4: deterministic "
              "corner matrix.", "",
              "| candidate | geometry override | " + " | ".join(f"{l} [{u}]" for _i, l, u in FULL_ROWS) + " |",
              "|---|---|" + "---|" * len(FULL_ROWS)]
        for r in result["full"]:
            cells = []
            for row_id, _l, _u in FULL_ROWS:
                c = r["rows"][row_id]
                if c["state"] != "measured":
                    cells.append("not run")
                else:
                    tv = "n/a" if c["target_verdict"] == grade_mod.NOT_SPECIFIED else c["target_verdict"]
                    cells.append(f"{_f(c['value'])} @ {c['at']} (T {tv}; {c['points_valid']}/{c['points_expected']} valid; "
                                 f"{c['points_failing_target']} pts fail T)")
            L.append(f"| {r['name']} | {_geom_full(r)} | " + " | ".join(cells) + " |")
        L += ["", "### Ratified Target rows per finalist", "",
              "| candidate | Target rows met | Target rows failed | incomplete | not run |", "|---|---|---|---|---|"]
        for r in result["full"]:
            met, failed, inc, unrun = _met(r)
            L.append(f"| {r['name']} | {', '.join(met) or '-'} | {', '.join(failed) or '-'} | "
                     f"{', '.join(inc) or '-'} | {', '.join(unrun) or '-'} |")
        L.append("")
    return "\n".join(L)


def _met(r: dict):
    met, failed, inc, unrun = [], [], [], []
    for row_id, _l, _u in FULL_ROWS:
        c = r["rows"][row_id]
        if c["state"] != "measured":
            if row_id != "5b":
                unrun.append(row_id)
            continue
        v = c["target_verdict"]
        if v == grade_mod.NOT_SPECIFIED:
            continue
        if v == grade_mod.INCOMPLETE:
            inc.append(row_id)
        elif v == grade_mod.PASS:
            met.append(row_id)
        else:
            failed.append(row_id)
    return met, failed, inc, unrun


def _write_once(path: Path, text: str) -> None:
    """Evidence is append-only: never replace a committed report with different bytes."""
    if path.is_file() and path.read_text(encoding="utf-8") != text:
        raise FileExistsError(
            f"{path} already exists with different content; evidence is append-only. "
            "Write the revised report under a fresh name (--report-name).")
    path.write_text(text, encoding="utf-8")


def run(campaign: str, campaigns_dir: Path, report_name: str = "sizesweep") -> dict:
    cdir = campaigns_dir / campaign
    result = {"campaign": campaign, "screen": screen(cdir), "full": full(cdir)}
    js = json.dumps(grade_mod.json_safe(result), indent=2, allow_nan=False) + "\n"
    md = render_markdown(result)
    _write_once(cdir / f"{report_name}.json", js)
    _write_once(cdir / f"{report_name}.md", md)
    return result


__all__ = ["run", "screen", "full", "render_markdown", "screen_request"]

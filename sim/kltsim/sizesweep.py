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

from . import artifacts as artifacts_mod
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


def _verdict_rows() -> tuple[str, ...]:
    """Row ids classified in the ``### Ratified Target rows per finalist``
    roll-up: every graded row of ``rows.json`` except unbounded reporting
    requirements (Row 4c today). Derived from the ratified spec rather than
    hand-listed so the set cannot drift from it (issue #447); ``FULL_ROWS``
    stays the metric-column list and deliberately omits Row 5a, a coverage
    row with no scalar or unit to tabulate."""
    spec = json.loads(
        (build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
    return tuple(r["id"] for r in spec["rows"] if not r.get("reporting_requirement"))


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


#: the screening grid a process-split bench's ONE part carries (issue #497):
#: a single process section x the screening supplies/temperatures = 6 points,
#: so the three parts (tt/ff/ss) tile the 18-point screen exactly once. A
#: request-only screen build used to rewrite EACH of the bench's five
#: full-grid parts to the whole 18-point grid (5 x 18 = 90 entries, every
#: point five times); this per-part form is the correction.
SCREEN_PART_COMMENT = (
    "SCREENING GRID part {section} (issue #497): {section} x 1.08/1.32 V x "
    "-40/27/125 C = 6 points; the tt/ff/ss parts tile the 18-point screen "
    "exactly once. Not a 45-point verdict; never graded as one.")


def screen_part_request(bench, section: str, body_name: str | None = None) -> dict:
    """The screening request of ONE part: for a process-split bench the named
    section only; for an unsplit bench the whole screening grid (identical to
    what :func:`screen_request` writes for it)."""
    processes = (section,) if bench.split_by_process else tuple(SCREEN_PROCESSES)
    request = build_mod.compose_request(
        bench, body_name or f"{bench.name}.body.spice", "batch", processes=processes)
    request["corners"] = {
        "process": list(processes),
        "supply_v": {k: list(SCREEN_SUPPLIES_V) for k in bench.supply_keys},
        "temperature_c": list(SCREEN_TEMPERATURES_C),
    }
    request.pop("remote", None)
    request["_comment"].append(
        SCREEN_PART_COMMENT.format(section=section) if bench.split_by_process else
        "SCREENING GRID (issue #92): tt/ff/ss x 1.08/1.32 V x -40/27/125 C = 18 points. "
        "Not a 45-point verdict; never graded as one.")
    return request


def plan_screen_inputs(
    bench, out_dir: Path, *,
    param_overrides: dict | None = None,
    geometry_overrides: dict | None = None,
    candidate: tuple[str, Path] | None = None,
) -> tuple[Path, list[Path], list[tuple[Path, bytes]]]:
    """Compose (without writing) a bench's SCREENING inputs with the process
    split preserved (issue #497): a ``split_by_process`` bench gets one
    six-point part per screening process section (tt/ff/ss, 18 distinct
    points in total), an unsplit bench the single 18-point request
    :func:`screen_request` writes. One body shared by all parts."""
    body_name = f"{bench.name}.body.spice"
    body_path = out_dir / body_name
    files: list[tuple[Path, bytes]] = [(
        body_path,
        build_mod.compose_body(bench, build_mod.BATCH_OSDI_DIR,
                               param_overrides=param_overrides,
                               geometry_overrides=geometry_overrides,
                               candidate=candidate).encode("utf-8"))]
    sections = list(SCREEN_PROCESSES) if bench.split_by_process else [SCREEN_PROCESSES[0]]
    requests: list[Path] = []
    union: set[tuple] = set()
    for section in sections:
        tag = f"{bench.name}.{section}" if bench.split_by_process else bench.name
        request = screen_part_request(bench, section, body_name)
        grid = request["corners"]
        for p in grid["process"]:
            for k in grid["supply_v"]:
                for v in grid["supply_v"][k]:
                    for t in grid["temperature_c"]:
                        union.add((p, k, round(float(v), 6), float(t)))
        requests.append(out_dir / f"{tag}.request.json")
        files.append((requests[-1], (json.dumps(request, indent=2) + "\n").encode("utf-8")))
    expected = {(p, k, v, t) for p in SCREEN_PROCESSES for k in bench.supply_keys
                for v in SCREEN_SUPPLIES_V for t in SCREEN_TEMPERATURES_C}
    if union != expected:
        raise build_mod.BuildError(
            f"screening parts for {bench.name} do not tile the 18-point grid "
            f"exactly once: {len(union)} distinct point/supply entries vs "
            f"{len(expected)} expected")
    return body_path, requests, files


def screen_corners_for(bench, tag: str) -> dict:
    """The screening grid the SAVED request of one part must carry: for a
    process-split bench the tag's own section (6 points), for an unsplit
    bench the whole 18-point grid. A ``corners`` callable for
    ``grade.load_campaign`` (issue #497)."""
    sections = [SCREEN_PROCESSES[0]]
    if bench.split_by_process:
        section = tag.split(".", 1)[1] if "." in tag else None
        sections = [section] if section in SCREEN_PROCESSES else []
    return {
        "process": sections,
        "supply_v": {k: list(SCREEN_SUPPLIES_V) for k in bench.supply_keys},
        "temperature_c": list(SCREEN_TEMPERATURES_C),
    }


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
            text = body.read_text(encoding="utf-8")
            # a dut.json param override (issue #92 bias study) is part of the
            # candidate's identity, so it is checked for cross-bench consistency too
            found[name] = {**build_mod.extract_geometry(text),
                           **build_mod.extract_param_overrides(text)}
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
    # Issue #122 scopes duplicate-name ambiguity per consumed measurement
    # (_meas_value rejects a repeated scored/gate name); here only the probes
    # must be unique for the whole point to be trusted.
    return grade_mod._corner_problems(corner, bench_name, [], unique=probes)


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


def _bench_reasons(ev, dut, candidate: str | None = None) -> list[str]:
    reasons = list(ev.chain_problems)
    if not ev.envelopes:
        reasons.append("no envelope present")
    reasons += grade_mod.check_dut(ev, dut, candidate)
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


def screen(campaign_dir: Path, *, subdirs: list[Path] | None = None) -> list[dict]:
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
    if subdirs is None:
        subdirs = sorted(p for p in campaign_dir.iterdir() if p.is_dir() and p.name.startswith("scr_"))
    for sub in subdirs:
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
        verdict_rows = _verdict_rows()
        cells = {}
        for row_id in verdict_rows:
            entry = by_id.get(row_id)
            # An INCOMPLETE grid with no valid points is "not swept" for the
            # metric table -- but a coverage row (e.g. 5a) carries no `target`
            # block at all, so its INCOMPLETE is real evidence and must reach
            # the roll-up (issue #447). Key the exemption on evidence_kind, not
            # on the missing target block: non-coverage rows without one stay
            # not run.
            if entry is not None and entry.get("evidence_kind") != "coverage" \
                    and entry["target_verdict"] == grade_mod.INCOMPLETE \
                    and ((entry.get("target") or {}).get("points_valid") or 0) == 0:
                entry = None
            cells[row_id] = ibsweep_mod._cell(entry)
        geometry, geom_problems = _geometry_report(sub, tuple(grade_mod._bench_names()))
        cand = {"name": sub.name[len("full_"):], "dir": sub.name,
                "geometry": geometry, "geometry_problems": geom_problems,
                "candidate_status": "available", "rejection_reasons": [], "rows": cells}
        if geom_problems:
            # Cross-bench geometry cannot be attributed to one candidate (issue
            # #269): the individually graded cells survive only as diagnostics;
            # no candidate-level row carries a verdict.
            cand["candidate_status"] = "rejected"
            cand["rejection_reasons"] = list(geom_problems)
            cand["diagnostic_rows"] = cells
            cand["rows"] = {rid: {"state": "rejected", "reason": "; ".join(geom_problems)}
                            for rid in verdict_rows}
        out.append(cand)
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
                if c["state"] == "rejected":
                    d = r["diagnostic_rows"][row_id]
                    cells.append("REJECTED (diagnostic: " + (
                        f"{_f(d['value'])} @ {d['at']}, bench T {d['target_verdict']}"
                        if d["state"] == "measured" else "not run") + ")")
                elif c["state"] != "measured":
                    cells.append("not run")
                else:
                    tv = "n/a" if c["target_verdict"] == grade_mod.NOT_SPECIFIED else c["target_verdict"]
                    cells.append(f"{_f(c['value'])} @ {c['at']} (T {tv}; {c['points_valid']}/{c['points_expected']} valid; "
                                 f"{c['points_failing_target']} pts fail T)")
            L.append(f"| {r['name']} | {_geom_full(r)} | " + " | ".join(cells) + " |")
        L += ["", "### Ratified Target rows per finalist", "",
              "| candidate | Target rows met | Target rows failed | incomplete | not run |", "|---|---|---|---|---|"]
        for r in result["full"]:
            if r.get("candidate_status") == "rejected":
                L.append(f"| {r['name']} | REJECTED: not attributable to one candidate | "
                         "REJECTED | REJECTED | REJECTED |")
                continue
            met, failed, inc, unrun = _met(r)
            L.append(f"| {r['name']} | {', '.join(met) or '-'} | {', '.join(failed) or '-'} | "
                     f"{', '.join(inc) or '-'} | {', '.join(unrun) or '-'} |")
        rejected = [r for r in result["full"] if r.get("candidate_status") == "rejected"]
        if rejected:
            L += ["", "### Rejected finalists (geometry validation, issue #269)", "",
                  "Benches of these candidates declare inconsistent or unreadable geometry "
                  "overrides, so no candidate-level Target row is claimed met or failed. The "
                  "individual bench results are kept as diagnostics (`diagnostic_rows` in "
                  "sizesweep.json). Rejected is distinct from `not run`.", ""]
            for r in rejected:
                for why in r["rejection_reasons"]:
                    L.append(f"- `{r['name']}`: {why}")
        L.append("")
    return "\n".join(L)


def _met(r: dict):
    met, failed, inc, unrun = [], [], [], []
    if r.get("candidate_status") == "rejected":
        return met, failed, inc, unrun
    for row_id in _verdict_rows():
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


def run(campaign: str, campaigns_dir: Path, report_name: str = "sizesweep") -> dict:
    cdir = campaigns_dir / campaign
    result = {"campaign": campaign, "screen": screen(cdir), "full": full(cdir)}
    js = json.dumps(grade_mod.json_safe(result), indent=2, allow_nan=False) + "\n"
    md = render_markdown(result)
    jpath, mpath = cdir / f"{report_name}.json", cdir / f"{report_name}.md"
    try:
        # Evidence is append-only: both members are preflighted before either is written.
        artifacts_mod.commit(
            [(jpath, js.encode("utf-8")), (mpath, md.encode("utf-8"))],
            differs="already exists with different content")
    except artifacts_mod.ArtifactConflict as exc:
        raise FileExistsError(
            "; ".join(exc.conflicts) + "; evidence is append-only. "
            "Write the revised report under a fresh name (--report-name).") from exc
    return result


# --------------------------------------------------------------------------- #
# issue #497: integration-node capacitance study (Row 2 noise vs Row 3c delay)
# --------------------------------------------------------------------------- #

#: the benches a capacitance-study screen carries: the Row 3c delay bench and
#: the Row 2 noise bench (the tradeoff under study). Kickback is not part of
#: this family's decision.
CAP_STUDY_BENCHES = ("regeneration", "transient_noise")

#: the noise bench's screening grid in ``rows.json`` grid form (bare process
#: names, flat supply list), for ``grade.mc_probit_noise``
CAP_SCREEN_GRID = {
    "process": ["tt", "ff", "ss"],
    "supply_v": list(SCREEN_SUPPLIES_V),
    "temperature_c": list(SCREEN_TEMPERATURES_C),
}

#: Every Row 2 figure this study publishes is labelled with this statistic.
NOISE_SCREEN_STATISTIC = (
    "mean of the per-point two-rung probit-slope sigma over the 18 screening "
    "points (tt/ff/ss x 1.08/1.32 V x -40/27/125 C), N = 80 trials per rung, "
    "injected density 36.27 nV/rtHz (the unchanged compliance bench)")

#: the archived zero-added-capacitance control (issue #92 bias study): the
#: geometry + 10 uA bias every candidate setting must hold, and the source of
#: the control's own screen numbers
CONTROL_CAMPAIGN = "20261115-issue92-bias"
CONTROL_SCR = "scr_ib10_sw20lat6"
CONTROL_FULL = "full_ib10_sw20lat6"
#: the 8 um baseline a finalist's Target rows are compared against
BASELINE_CAMPAIGN = "20261009-issue92"
BASELINE_FULL = "full_w8_l034"


def _control_identity() -> dict:
    """The archived control's geometry + dut.json param overrides, read back
    from its committed screen body (so the identity cannot drift from the
    archived evidence)."""
    body = (build_mod.EXPERIMENT_DIR / "campaigns" / CONTROL_CAMPAIGN
            / CONTROL_SCR / "regeneration.body.spice")
    text = body.read_text(encoding="utf-8")
    return {"geometry": build_mod.extract_geometry(text),
            "params": build_mod.extract_param_overrides(text)}


def _candidate_report(sub: Path, bench_names, expect_name: str | None = None
                      ) -> tuple[dict, list[str]]:
    """(candidate declaration, problems): every bench body must declare the
    SAME structural candidate, and (when ``expect_name`` is given, derived
    from the ``scr_/full_`` directory name) exactly that named setting."""
    found: dict[str, dict] = {}
    problems: list[str] = []
    for name in bench_names:
        body = sub / f"{name}.body.spice"
        if not body.is_file():
            continue
        found[name] = build_mod.extract_candidate(body.read_text(encoding="utf-8"))
    missing = sorted(n for n, c in found.items() if not c)
    if missing:
        problems.append(f"bench body/bodies declare no candidate: {', '.join(missing)}")
    declared = {json.dumps(c, sort_keys=True) for c in found.values() if c}
    if len(declared) > 1:
        problems.append("inconsistent candidate declaration across benches: " + "; ".join(
            f"{n} {json.dumps(c, sort_keys=True)}" for n, c in sorted(found.items())))
        return {}, problems
    cand = next(iter(declared)) if declared else {}
    cand = json.loads(cand) if cand else {}
    if expect_name and cand and cand.get("name") != expect_name:
        problems.append(f"directory names candidate {expect_name!r} but the benches "
                        f"declare {cand.get('name')!r}")
    return cand, problems


def _candidate_cap_fF(cand: dict, problems: list[str]) -> float | None:
    """The per-side capacitance (fF) of the candidate's reference netlist,
    re-read from the reference FILE so the table cannot disagree with what
    was simulated. Appends to ``problems`` when the reference is unusable."""
    if not cand:
        return None
    ref = Path(cand.get("path") or "")
    if not ref.is_absolute():
        ref = build_mod.REPO_ROOT / ref
    if not ref.is_file():
        problems.append(f"candidate reference {cand.get('path')!r} does not exist")
        return None
    try:
        value = build_mod.check_candidate_netlist(ref.read_text(encoding="utf-8"))
    except (build_mod.BuildError, UnicodeDecodeError) as exc:
        problems.append(f"candidate reference unusable: {exc}")
        return None
    return build_mod.cap_to_farads(value) * 1e15


def _noise_screen_cell(bench_ev, reasons: list[str]) -> dict:
    """The Row 2 screening statistic: the mean per-point probit sigma over
    the 18-point grid, N = 80 per rung, unchanged 36.27 nV/rtHz bench."""
    rows_spec = json.loads(
        (build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))
    ev = next(r for r in rows_spec["rows"] if r["id"] == "2")["evidence"]
    details, notes = grade_mod.mc_probit_noise(bench_ev, ev, CAP_SCREEN_GRID)
    valid = [d for d in details if d["sigma"] is not None]
    expected = len(grade_mod.grid_keys(CAP_SCREEN_GRID))
    mean = sum(d["sigma"] for d in valid) / len(valid) if valid else None
    return {
        "available": not reasons and len(valid) == expected,
        "value": mean, "point": None,
        "expected": expected, "present": len({d["point"] for d in details}),
        "valid": 0 if reasons else len(valid),
        "required_gates": [],
        "rejections": [] if reasons else
        [f"{d['point']}: {d['problem']}" for d in details if d["problem"]],
        "notes": list(notes),
        "noise_statistic": NOISE_SCREEN_STATISTIC,
    }


#: Row 2 Target (mV rms) and Row 3c Target (ns) the screen decision tests
#: against (DR-0002; a setting advances only when the screen noise mean is at
#: or below the Row 2 Target AND the worst screen delay is at or below Row 3c)
ROW2_TARGET_MV = 1.0
ROW3C_TARGET_NS = 2.0


def _screen_decision(noise: dict, td01: dict, control: dict) -> dict:
    """The objective advance/eliminate call for one setting (issue #497's
    question: close Row 2 WITHIN the Row 3c limit). Deterministic from the
    validated screen statistics; the noise side needs the full deficit, not
    just a trend, because the screen's own sampling error is ~ +/-3 %."""
    reasons = []
    if noise.get("available") and noise["value"] is not None \
            and noise["value"] <= ROW2_TARGET_MV:
        noise_ok, noise_why = True, f"screen mean {noise['value']:.4g} mV <= {ROW2_TARGET_MV:g}"
    else:
        value = noise.get("value")
        need = 100.0 * (1.0 - ROW2_TARGET_MV / control["value"]) if control.get("value") else None
        have = 100.0 * (1.0 - value / control["value"]) if value is not None and control.get("value") else None
        noise_ok = False
        noise_why = (f"screen mean {value:.4g} mV rms vs control {control['value']:.4g} mV: "
                     f"deficit {have:.2f} % against the {need:.2f} % reduction 1.0 mV requires"
                     if value is not None else "screen noise mean unavailable")
    reasons.append(noise_why)
    if td01.get("available") and td01["value"] is not None and td01["value"] <= ROW3C_TARGET_NS:
        reasons.append(f"worst t_d {td01['value']:.4g} ns <= {ROW3C_TARGET_NS:g}")
    else:
        reasons.append(f"worst t_d {td01.get('value')} ns exceeds {ROW3C_TARGET_NS:g}")
    advance = noise_ok and bool(td01.get("available")) and td01["value"] <= ROW3C_TARGET_NS
    return {"advance": advance,
            "decision": "advance" if advance else "eliminate",
            "reasons": reasons}


def cap_screen(campaign_dir: Path) -> list[dict]:
    """Validated screening reduction for the capacitance study (issue #497).

    Per candidate setting: both benches' request/invocation/envelope chains
    must hash-match, the body's DUT must be the NAMED structural candidate
    (verified against its reference file) carrying the archived control's
    geometry and 10 uA bias, and the noise bench's three saved parts must be
    the per-process screening parts. Statistics publish only with complete,
    valid point coverage; every rejection reason is retained.
    """
    dut = grade_mod.load_dut_reference()
    expected_set = set(EXPECTED_POINTS)
    control = _control_identity()
    control_identity = {**control["geometry"], **control["params"]}
    control_noise = cap_control()["metrics"]["noise_mean"]
    rows = []
    for sub in sorted(p for p in campaign_dir.iterdir()
                      if p.is_dir() and p.name.startswith("scr_")):
        name = sub.name[len("scr_"):]
        geometry, geom_problems = _geometry_report(sub, CAP_STUDY_BENCHES)
        cand, cand_problems = _candidate_report(sub, CAP_STUDY_BENCHES, expect_name=name)
        identity_problems = []
        if geometry != control_identity:
            identity_problems.append(
                "every setting must hold the archived control identity ("
                + _geom(control_identity) + "); the body declares " + _geom(geometry))
        cap_fF = _candidate_cap_fF(cand, cand_problems)
        loaded = {}
        for bname in CAP_STUDY_BENCHES:
            bench = grade_mod._bench_spec(bname)
            corners = screen_corners(bench) if bname == "regeneration" else screen_corners_for
            ev = grade_mod.load_campaign(sub, corners=corners, bench_names=(bname,))[bname]
            points, notes = (_bench_points(ev, expected_set) if bname == "regeneration"
                             else ({}, []))
            reasons = (_bench_reasons(ev, dut, candidate=name) + geom_problems
                       + identity_problems)
            cand_problems += [r for r in reasons if "candidate" in r]
            loaded[bname] = {
                "points": points, "notes": notes, "reasons": reasons, "ev": ev,
                "ppb": {k: _point_problem(c, bname)
                        for k, c in points.items() if c is not None},
            }
        noise = _noise_screen_cell(loaded["transient_noise"]["ev"],
                                   loaded["transient_noise"]["reasons"])
        row = {"name": name, "dir": sub.name,
               "candidate": cand, "candidate_problems": cand_problems,
               "cap_fF": cap_fF,
               "geometry": geometry, "geometry_problems": geom_problems,
               "identity_problems": identity_problems, "metrics": {}, "benches": {}}
        for bname, d in loaded.items():
            if bname == "regeneration":
                bench_cell = {
                    "expected": len(EXPECTED_POINTS), "present": len(d["points"]),
                    "missing_points": [_fmt_pt(k) for k in EXPECTED_POINTS
                                       if k not in d["points"]],
                }
            else:
                bench_cell = {"expected": noise["expected"], "present": noise["present"],
                              "missing_points": []}
            row["benches"][bname] = {
                **bench_cell,
                "evidence_rejections": d["reasons"], "notes": d["notes"]}
        d = loaded["regeneration"]
        gates = ("dout_od01_first", "dout_od01_end")
        vals, rej = _reduce_metric(d["points"], "regeneration", "td_od01_ns", 1.0,
                                   gates, d["ppb"])
        row["metrics"]["td01_worst"] = _metric_cell(vals, rej, len(d["points"]),
                                                    gates, d["reasons"])
        row["metrics"]["noise_mean"] = noise
        row["decision"] = _screen_decision(noise, row["metrics"]["td01_worst"],
                                           control_noise)
        rows.append(row)
    return rows


def cap_control() -> dict:
    """The archived zero-added-capacitance control (`ib10_sw20lat6` geometry,
    10 uA bias, no added capacitance): its screen delays re-derived from the
    committed screen campaign, its 18-point noise mean from the committed
    45-point grading of the full campaign. Chain-validated where envelopes
    are committed."""
    root = build_mod.EXPERIMENT_DIR / "campaigns"
    scr = root / CONTROL_CAMPAIGN / CONTROL_SCR
    full = root / CONTROL_CAMPAIGN / CONTROL_FULL
    bench = grade_mod._bench_spec("regeneration")
    ev = grade_mod.load_campaign(scr, corners=screen_corners(bench),
                                  bench_names=("regeneration",))["regeneration"]
    points, notes = _bench_points(ev, set(EXPECTED_POINTS))
    reasons = _bench_reasons(ev, grade_mod.load_dut_reference())
    ppb = {k: _point_problem(c, "regeneration") for k, c in points.items() if c is not None}
    gates = ("dout_od01_first", "dout_od01_end")
    vals, rej = _reduce_metric(points, "regeneration", "td_od01_ns", 1.0, gates, ppb)
    td01 = _metric_cell(vals, rej, len(points), gates, reasons)
    grading = json.loads((full / "grading.json").read_text(encoding="utf-8"))
    row2 = next(r for r in grading["rows"] if r["id"] == "2")
    screen_labels = {grade_mod.key_label(k) for k in EXPECTED_POINTS}
    per_point = row2.get("monte_carlo_per_point") or []
    sel = [d for d in per_point if d.get("point") in screen_labels]
    valid = [d for d in sel if d.get("sigma") is not None]
    identity = _control_identity()
    return {
        "name": "ib10_sw20lat6 (archived)", "archived": CONTROL_CAMPAIGN,
        "control_dirs": {"screen": f"{CONTROL_CAMPAIGN}/{CONTROL_SCR}",
                         "full": f"{CONTROL_CAMPAIGN}/{CONTROL_FULL}"},
        "cap_fF": 0.0,
        "geometry": identity["geometry"], "params": identity["params"],
        "metrics": {
            "td01_worst": td01,
            "noise_mean": {
                "available": bool(valid) and len(valid) == len(screen_labels),
                "value": sum(d["sigma"] for d in valid) / len(valid) if valid else None,
                "point": None, "expected": len(screen_labels), "present": len(sel),
                "valid": len(valid), "required_gates": [], "rejections": [
                    f"{d.get('point')}: {d.get('problem')}" for d in sel if d.get("problem")],
                "notes": ["source: committed grading.json of the archived 45-point "
                          "campaign, filtered to the 18 screening points"],
                "noise_statistic": NOISE_SCREEN_STATISTIC + " (re-derived from the "
                                   "archived 45-point grading, not re-run)",
            },
        },
        "benches": {"regeneration": {"expected": len(EXPECTED_POINTS),
                                     "present": len(points),
                                     "missing_points": [], "evidence_rejections": reasons,
                                     "notes": notes}},
    }


def cap_full(campaign_dir: Path) -> list[dict]:
    """The finalist table: full 45-point Rows 1-5 graded by ``kltsim.grade``
    with the candidate expectation, plus the archived 8 um baseline's Target
    verdicts carried alongside for the preservation question."""
    baseline = json.loads((build_mod.EXPERIMENT_DIR / "campaigns" / BASELINE_CAMPAIGN
                           / BASELINE_FULL / "grading.json").read_text(encoding="utf-8"))
    base_by_id = {r["id"]: r for r in baseline["rows"]}
    out = []
    for sub in sorted(p for p in campaign_dir.iterdir()
                      if p.is_dir() and p.name.startswith("full_")):
        name = sub.name[len("full_"):]
        cand, cand_problems = _candidate_report(sub, tuple(grade_mod._bench_names()),
                                                expect_name=name)
        if cand:
            # the reference file itself is verified before any grading spend
            ref_problems, _bytes = grade_mod._candidate_reference(cand, name)
            cand_problems += ref_problems
        geometry, geom_problems = _geometry_report(sub, tuple(grade_mod._bench_names()))
        problems = list(cand_problems)
        graded = None if problems else grade_mod.grade_campaign(sub, candidate=name)
        by_id = {r["id"]: r for r in (graded or {}).get("rows", [])}
        verdict_rows = _verdict_rows()
        cells = {}
        for row_id in verdict_rows:
            entry = by_id.get(row_id)
            if entry is not None and entry.get("evidence_kind") != "coverage" \
                    and entry["target_verdict"] == grade_mod.INCOMPLETE \
                    and ((entry.get("target") or {}).get("points_valid") or 0) == 0:
                entry = None
            cell = ibsweep_mod._cell(entry)
            base = base_by_id.get(row_id) or {}
            cell["baseline_w8_l034_target"] = base.get("target_verdict")
            if base.get("target_verdict") == grade_mod.PASS \
                    and cell["state"] == "measured" \
                    and cell["target_verdict"] != grade_mod.PASS:
                cell["preservation"] = "broken"
            elif cell["state"] == "measured" and cell["target_verdict"] == grade_mod.PASS:
                cell["preservation"] = "held"
            else:
                cell["preservation"] = None
            cells[row_id] = cell
        out.append({
            "name": name, "dir": sub.name,
            "candidate": cand, "candidate_problems": cand_problems,
            "cap_fF": _candidate_cap_fF(cand, []),
            "geometry": geometry, "geometry_problems": geom_problems,
            "candidate_status": "rejected" if problems else "available",
            "rejection_reasons": problems,
            "rows": cells if not problems else
            {rid: {"state": "rejected", "reason": "; ".join(problems)}
             for rid in verdict_rows},
            "diagnostic_rows": cells if problems else None,
            "grading_verdicts": {
                "target_rows_pass": (graded or {}).get("t1_item5", {}).get(
                    "all_target_rows_pass"),
                "row2": _full_row_summary(by_id.get("2")),
            } if graded else None,
        })
    return out


def _full_row_summary(entry: dict | None) -> dict | None:
    if not entry:
        return None
    target = entry.get("target") or {}
    return {"target_verdict": entry.get("target_verdict"),
            "value": target.get("value") if isinstance(target, dict) else None,
            "points_valid": target.get("points_valid") if isinstance(target, dict) else None,
            "points_expected": target.get("points_expected")
            if isinstance(target, dict) else None}


def render_capacitance_markdown(result: dict) -> str:
    L = ["# Integration-node capacitance study -- campaign "
         f"`{result['campaign']}` (issue #497)", "",
         "GENERATED by `python3 sim/run_klt_corner_verification.py capacitance`. "
         "Measures whether matched added capacitance at the input-pair drains "
         "(`np`/`nn`, each capacitor node-to-vss, equal per side) can narrow the "
         "effective decision bandwidth enough to close Row 2 within the Row 3c "
         "delay limit. Proposes no bound, changes no spec row, no DUT and not "
         "`sim/dut.json`. A screen row is NOT a 45-point verdict.", "",
         "Row 2 labelling: every noise figure below is `" + NOISE_SCREEN_STATISTIC + "`. "
         "The unchanged-bench comparison against the control holds the injected "
         "density at 36.27 nV/rtHz; candidate-own-density figures (Phase 1 method: "
         "differential output density at 1 MHz divided by |Av(1 Hz)|) are "
         "PROJECTIONS, labelled as such, and never a Row 2 Target verdict. Only a "
         "complete 45-point unchanged-bench mean supports a Row 2 Target verdict.", ""]
    control = result.get("control") or {}
    if control:
        m = control.get("metrics") or {}
        L += ["## Archived control (zero added capacitance)", "",
              f"Control: `ib10_sw20lat6` geometry at 10 uA bias, campaign "
              f"`{control.get('archived')}` "
              f"({control.get('control_dirs', {}).get('screen')} / "
              f"{control.get('control_dirs', {}).get('full')}), "
              f"cap {control.get('cap_fF'):g} fF per side.", "",
              "| control statistic | value | valid/expected |", "|---|---|---|"]
        noise, td01 = m.get("noise_mean") or {}, m.get("td01_worst") or {}
        L.append(f"| noise {noise.get('noise_statistic', 'mean probit sigma')} "
                 f"| {_f(noise.get('value'))} mV rms | {noise.get('valid')}/{noise.get('expected')} |")
        L.append(f"| worst Row 3c t_d @ 0.1 mV | {_mc(td01, True) if td01.get('available') else 'unavailable'}"
                 f" @ {td01.get('point')} | {td01.get('valid')}/{td01.get('expected')} |")
        L.append("")
    if result.get("screen"):
        L += ["## Screening (18-point grid: noise vs worst Row 3c delay)", "",
              "| setting | C per side [fF] | noise mean sigma [mV rms] | valid/18 | "
              "worst t_d @ 0.1 mV [ns] | its PVT point | valid/18 | decision | candidate reference |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in result["screen"]:
            m = r["metrics"]
            noise, td01 = m["noise_mean"], m["td01_worst"]
            ref = "-"
            if r.get("candidate"):
                ref = f"`{r['candidate'].get('path')}` sha256 `{str(r['candidate'].get('sha256'))[:12]}...`"
            if r.get("candidate_problems") or r.get("identity_problems"):
                ref += " REJECTED"
            decision = r.get("decision") or {}
            L.append(f"| {r['name']} | {_f(r.get('cap_fF'), 3) if r.get('cap_fF') is not None else '-'} "
                     f"| {_mc(noise, True) if noise.get('available') else _f(noise.get('value'))} "
                     f"| {noise.get('valid')}/{noise.get('expected')} "
                     f"| {_mc(td01, True) if td01.get('available') else _f(td01.get('value'))} "
                     f"| {td01.get('point') or '-'} | {td01.get('valid')}/{td01.get('expected')} "
                     f"| {decision.get('decision', '-')} | {ref} |")
        for r in result["screen"]:
            decision = r.get("decision") or {}
            for why in decision.get("reasons") or []:
                L.append(f"- `{r['name']}` {decision.get('decision', '?')}: {why}")
        advanced = [r for r in result["screen"] if (r.get("decision") or {}).get("advance")]
        if result["screen"] and not advanced and not result.get("full"):
            L += ["", "**No setting advanced to the full grid**: every setting's full-grid "
                  "Rows 1-5 remain unmeasured (a negative result completes the study -- "
                  "the elimination reasons above are the recorded rationale)."]
        L += ["", "### Screening evidence validation", "",
              "| setting | bench | expected | present | evidence rejections |", "|---|---|---|---|---|"]
        for r in result["screen"]:
            for bname, b in (r.get("benches") or {}).items():
                L.append(f"| {r['name']} | {bname} | {b.get('expected')} | {b.get('present')} | "
                         f"{'; '.join(b.get('evidence_rejections') or [])[:400] or '-'} |")
        for r in result["screen"]:
            problems = (r.get("candidate_problems") or []) + (r.get("identity_problems") or [])
            for p in problems:
                L.append(f"- `{r['name']}`: {p}")
        L.append("")
    if result.get("full"):
        L += ["## Finalist: full 45-point grid, Rows 1-5 graded by `kltsim.grade`", "",
              "Baseline for Target preservation: the archived 8 um study baseline "
              f"`{BASELINE_CAMPAIGN}/{BASELINE_FULL}`; a Target row it PASSes must "
              "still PASS for the finalist to advance.", "",
              "| finalist | C per side [fF] | " + " | ".join(f"{l} [{u}]" for _i, l, u in FULL_ROWS) + " |",
              "|---|---|---|" + "---|" * len(FULL_ROWS)]
        for r in result["full"]:
            cells = []
            for row_id, _l, _u in FULL_ROWS:
                c = r["rows"].get(row_id) or {}
                if c.get("state") == "rejected":
                    cells.append("REJECTED")
                elif c.get("state") != "measured":
                    cells.append("not run")
                else:
                    tv = "n/a" if c["target_verdict"] == grade_mod.NOT_SPECIFIED else c["target_verdict"]
                    base = c.get("baseline_w8_l034_target")
                    mark = ""
                    if c.get("preservation") == "broken":
                        mark = " **baseline-broken**"
                    elif base == grade_mod.PASS:
                        mark = " (baseline PASS held)" if c.get("preservation") == "held" else ""
                    cells.append(f"{_f(c['value'])} @ {c['at']} (T {tv}; "
                                 f"{c['points_valid']}/{c['points_expected']} valid; "
                                 f"{c['points_failing_target']} pts fail T){mark}")
            L.append(f"| {r['name']} | {_f(r.get('cap_fF'), 3) if r.get('cap_fF') is not None else '-'} | "
                     + " | ".join(cells) + " |")
        for r in result["full"]:
            gv = r.get("grading_verdicts") or {}
            row2 = gv.get("row2") or {}
            if row2:
                L += ["", f"### `{r['name']}` Row 2 (Target <= 1.0 mV rms)", "",
                      f"- 45-point unchanged-bench grid mean: **{_f(row2.get('value'))} mV rms**, "
                      f"Target verdict **{row2.get('target_verdict')}** "
                      f"({row2.get('points_valid')}/{row2.get('points_expected')} valid points).",
                      "- This is the DR-designated statistic (grid-wide mean of the "
                      "per-point two-rung probit-slope sigma, N = 80 per rung, injected "
                      "36.27 nV/rtHz); the screen's 18-point figure above is a "
                      "projection-scale comparison only."]
        L.append("")
    return "\n".join(L)


def cap_run(campaign: str, campaigns_dir: Path, report_name: str = "capacitance") -> dict:
    """The issue #497 capacitance-study report: control + screen (+ full
    finalists), written append-only beside the campaign like ``run``."""
    cdir = campaigns_dir / campaign
    result = {"campaign": campaign, "control": cap_control(),
              "screen": cap_screen(cdir), "full": cap_full(cdir)}
    js = json.dumps(grade_mod.json_safe(result), indent=2, allow_nan=False) + "\n"
    md = render_capacitance_markdown(result)
    jpath, mpath = cdir / f"{report_name}.json", cdir / f"{report_name}.md"
    try:
        artifacts_mod.commit(
            [(jpath, js.encode("utf-8")), (mpath, md.encode("utf-8"))],
            differs="already exists with different content")
    except artifacts_mod.ArtifactConflict as exc:
        raise FileExistsError(
            "; ".join(exc.conflicts) + "; evidence is append-only. "
            "Write the revised report under a fresh name (--report-name).") from exc
    return result


__all__ = ["run", "screen", "full", "render_markdown", "screen_request",
           "cap_run", "cap_screen", "cap_full", "cap_control"]

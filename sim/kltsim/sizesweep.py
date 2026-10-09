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


def _geometry_of(sub: Path) -> dict:
    for body in sorted(sub.glob("*.body.spice")):
        return build_mod.extract_geometry(body.read_text(encoding="utf-8"))
    return {}


def _values(env: dict) -> dict:
    """corner (process, supply, temp) -> {measurement: value}, with status."""
    out = {}
    for c in env.get("corners") or []:
        sup = c.get("supply_v") or {}
        v = sup[sorted(sup)[0]] if sup else None
        proc = c.get("process")
        proc = proc.split("/")[0] if isinstance(proc, str) else proc
        key = (proc, round(float(v), 3) if v is not None else None, float(c.get("temperature_c")))
        out[key] = {"status": c.get("status"),
                    "m": {m["name"]: m.get("value") for m in c.get("measurements") or []}}
    return out


def _load(sub: Path, bench: str) -> dict:
    p = sub / f"{bench}.envelope.json"
    return _values(json.loads(p.read_text(encoding="utf-8"))) if p.is_file() else {}


def _worst(vals: dict, name: str, gates=()):
    """(worst value, corner) over points whose value exists; points failing a
    decision gate count as invalid, not as a number."""
    best = None
    valid = 0
    for key, d in vals.items():
        v = d["m"].get(name)
        if v is None or any((d["m"].get(g) or 0) < 0.9 for g in gates):
            continue
        valid += 1
        if best is None or v > best[0]:
            best = (v, key)
    return best, valid


def _fmt_pt(key) -> str:
    return "?" if key is None else f"{key[0].replace('mos_', '')}_{key[2]:g}c_{key[1]:g}v"


def screen(campaign_dir: Path) -> list[dict]:
    rows = []
    for sub in sorted(p for p in campaign_dir.iterdir() if p.is_dir() and p.name.startswith("scr_")):
        kb, rg = _load(sub, "kickback"), _load(sub, "regeneration")
        qk, qn = _worst(kb, "qkick_fc", ("dout_1k_end",))
        bind = kb.get(BINDING_PT)
        t50, _ = _worst(rg, "td_od50_ns", ("dout_od50_end",))
        t01, _ = _worst(rg, "td_od01_ns", ("dout_od01_end",))
        tau, _ = _worst(rg, "tau_ps")
        pw, _ = _worst(rg, "p_avg")
        sd, _ = _worst(kb, "kick_sigdep_uv", ("dout_float_small_end", "dout_float_big_end"))
        rows.append({
            "name": sub.name[len("scr_"):], "dir": sub.name, "geometry": _geometry_of(sub),
            "qkick_binding_fc": (bind or {}).get("m", {}).get("qkick_fc"),
            "qkick_worst": None if qk is None else {"value": qk[0], "point": _fmt_pt(qk[1])},
            "kick_points_valid": qn, "kick_points": len(kb),
            "td50_worst_ns": None if t50 is None else {"value": t50[0], "point": _fmt_pt(t50[1])},
            "td01_worst_ns": None if t01 is None else {"value": t01[0], "point": _fmt_pt(t01[1])},
            "tau_worst_ps": None if tau is None else {"value": tau[0], "point": _fmt_pt(tau[1])},
            "sigdep_worst_uv": None if sd is None else {"value": sd[0], "point": _fmt_pt(sd[1])},
            "p_avg_worst_uw": None if pw is None else {"value": pw[0] * 1e6, "point": _fmt_pt(pw[1])},
            "regen_points": len(rg),
        })
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
        out.append({"name": sub.name[len("full_"):], "dir": sub.name,
                    "geometry": _geometry_of(sub), "rows": cells})
    return out


def _geom(g: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in sorted(g.items())) or "baseline (design/comparator.spice as committed)"


def _f(x, d=4):
    return "-" if x is None else f"{x:.{d}g}"


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
              "baseline's 45-point binding corner.", "",
              "| candidate | geometry override | Q_kick @ binding [fC] | Q_kick worst of screen [fC] | t_d 50 mV worst [ns] | t_d 0.1 mV worst [ns] | tau worst [ps] | sig-dep residue worst [uV] | power worst [uW] | valid kick / regen pts |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in result["screen"]:
            L.append(f"| {r['name']} | {_geom(r['geometry'])} | {_f(r['qkick_binding_fc'])} | {_w(r['qkick_worst'])} | "
                     f"{_w(r['td50_worst_ns'])} | {_w(r['td01_worst_ns'])} | {_w(r['tau_worst_ps'])} | "
                     f"{_w(r['sigdep_worst_uv'])} | {_w(r['p_avg_worst_uw'])} | "
                     f"{r['kick_points_valid']}/{r['kick_points']}, {r['regen_points']} |")
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
            L.append(f"| {r['name']} | {_geom(r['geometry'])} | " + " | ".join(cells) + " |")
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


def run(campaign: str, campaigns_dir: Path) -> dict:
    cdir = campaigns_dir / campaign
    result = {"campaign": campaign, "screen": screen(cdir), "full": full(cdir)}
    (cdir / "sizesweep.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (cdir / "sizesweep.md").write_text(render_markdown(result), encoding="utf-8")
    return result


__all__ = ["run", "screen", "full", "render_markdown", "screen_request"]

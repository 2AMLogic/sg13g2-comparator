"""Bias-point sweep report (issue #80): DR-0002 rows against ``dut_ib``.

Reads the per-bias campaigns ``campaigns/ID/ib_<X>uA/`` (each a normal
``kltsim`` campaign directory: bodies, requests, envelopes, attempts), grades
each one with the SAME rules ``kltsim.grade`` applies to the issue #62
campaign (nothing is re-derived here), and tabulates, per swept ``dut_ib``,
the verdict of every row that campaign measured plus the mirror/headroom
indicators. It proposes no bound and edits no spec: it is the evidence a
follow-up decision record would be founded on.

    python3 sim/run_klt_corner_verification.py ibsweep --campaign ID

Rows a bias point did not measure (the Monte-Carlo rows 1-2 are run for the
best candidate currents only, kickback not at all) are reported as ``not
swept``, never as PASS.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import build as build_mod
from . import grade as grade_mod

#: rows tabulated, in order: (row id, label, unit)
ROWS = (
    ("3a", "decision time @ 50 mV, worst point", "ns"),
    ("3b", "tau, worst point", "ps"),
    ("3c", "decision time @ 0.1 mV, worst point", "ns"),
    ("1", "offset 3 sigma, worst point (whole latch, MC N=60)", "mV"),
    ("2", "noise, grid-wide mean (whole latch, probit, N=80)", "mV rms"),
    ("5b", "average power incl. bias branch, worst point", "uW"),
)

#: SCREENING indicators only -- the tail current itself is not probed, so the
#: 4:1 mirror ratio is never measured directly. Both compare the tail device's
#: drain voltage early in evaluation (``tmid``) with the diode-connected
#: reference's Vds (= its Vgs, ``vref``): a mirror copies its reference
#: exactly only at equal Vds, and departs by channel-length modulation / DIBL
#: as the two diverge. The mirror is a fixed W/L 4:1 (XMB 10u/0.5u -> XMT
#: 40u/0.5u), which holds in weak inversion too (equal Vgs -> W/L ratio), so
#: weak inversion alone is reported as a note, not an invalidation.
TAIL_TO_REF_RANGE = (0.5, 2.0)
#: below ~4 thermal voltages of Vds a MOSFET leaves saturation whatever its
#: inversion level (0.1 V at 27 C and above; conservative at -40 C).
TAIL_TRIODE_V = 0.10
WEAK_INVERSION_VREF_V = 0.30


#: dut_ib values whose Monte-Carlo rows (1, 2) are taken from the issue #62
#: campaign instead of being re-run: its offset_mc / transient_noise bodies
#: were built with dut.json's dut_ib = 20 uA, so they ARE the 20 uA
#: measurement (re-running would duplicate ~6300 fleet units for the same
#: numbers). The ib_20uA regeneration is nevertheless re-run here, and
#: reproduces every measurement of that campaign's envelope exactly (see the README).
REUSE_MC = {20.0: "20261009-d73a9ac"}


def ib_of(path: Path) -> float | None:
    m = re.fullmatch(r"ib_([0-9.]+)uA", path.name)
    return float(m.group(1)) if m else None


def _worst(entry: dict, key: str) -> dict | None:
    sub = entry.get(key) or {}
    if "binding" in sub and sub["binding"]:
        return sub["binding"]
    rng = (sub.get("range") or {}).get("max")
    return rng


def _cell(entry: dict | None) -> dict:
    if entry is None:
        return {"state": "not swept"}
    t = entry["target"] if isinstance(entry.get("target"), dict) else {}
    s = entry["stretch"] if isinstance(entry.get("stretch"), dict) else {}
    binding = _worst(entry, "target") or {}
    # Row 2 grades a mean: report the mean, not a worst-point extreme.
    value = binding.get("value")
    return {
        "state": "measured",
        "target_bound": entry.get("target_bound"),
        "target_verdict": entry["target_verdict"],
        "stretch_bound": entry.get("stretch_bound"),
        "stretch_verdict": entry["stretch_verdict"],
        "value": value,
        "at": binding.get("point"),
        "points_valid": t.get("points_valid"),
        "points_expected": t.get("points_expected"),
        "points_failing_target": t.get("points_failing"),
        "points_failing_stretch": s.get("points_failing"),
        "missing": t.get("points_missing_or_invalid") or [],
    }


def probe_summary(campaign_dir: Path) -> dict:
    """Mirror/headroom indicators from the bias probes of one regeneration
    envelope: the diode-connected reference's Vgs and the tail drain voltage
    early in evaluation, over the 45 points."""
    env_path = campaign_dir / "regeneration.envelope.json"
    if not env_path.is_file():
        return {}
    env = json.loads(env_path.read_text(encoding="utf-8"))
    vref, tmid, ratio = [], [], []
    for c in env.get("corners") or []:
        v = {m["name"]: m.get("value") for m in c.get("measurements") or []}
        if v.get("vref_v") is not None and v.get("tmid_eval_v") is not None:
            vref.append((v["vref_v"], c["corner_id"]))
            tmid.append((v["tmid_eval_v"], c["corner_id"]))
            ratio.append((v["tmid_eval_v"] / v["vref_v"], c["corner_id"]))
    if not vref:
        return {}
    lo = lambda xs: min(xs)  # noqa: E731
    hi = lambda xs: max(xs)  # noqa: E731
    return {
        "vref_v": {"min": lo(vref), "max": hi(vref)},
        "tmid_eval_v": {"min": lo(tmid), "max": hi(tmid)},
        "tail_to_ref": {"min": lo(ratio), "max": hi(ratio)},
        "weak_inversion_points": sum(1 for x, _ in vref if x < WEAK_INVERSION_VREF_V),
        "tail_near_triode_points": sum(1 for x, _ in tmid if x < TAIL_TRIODE_V),
        "tail_ref_vds_mismatch_points": sum(
            1 for x, _ in ratio if not TAIL_TO_REF_RANGE[0] <= x <= TAIL_TO_REF_RANGE[1]),
        "points": len(vref),
    }


def sweep(campaign_dir: Path) -> dict:
    out = {"campaign": campaign_dir.name, "points": []}
    for sub in sorted((p for p in campaign_dir.iterdir() if ib_of(p) is not None), key=ib_of):
        graded = grade_mod.grade_campaign(sub)
        by_id = {r["id"]: r for r in graded["rows"]}
        cells = {}
        for row_id, _label, _unit in ROWS:
            entry = by_id.get(row_id)
            # A row whose bench was not run in this directory is INCOMPLETE
            # with zero valid points: that is "not swept", not a failure.
            if entry is not None and entry["target_verdict"] == grade_mod.INCOMPLETE \
                    and ((entry.get("target") or {}).get("points_valid") or 0) == 0:
                entry = None
            cells[row_id] = _cell(entry)
        reuse = REUSE_MC.get(ib_of(sub))
        if reuse is not None:
            ref = {r["id"]: r for r in grade_mod.grade_campaign(campaign_dir.parent / reuse)["rows"]}
            for row_id in ("1", "2"):
                cells[row_id] = dict(_cell(ref[row_id]), source=f"campaign {reuse} (issue #62), same dut_ib")
        out["points"].append({
            "dut_ib_ua": ib_of(sub),
            "tail_ua": 4 * ib_of(sub),
            "dir": sub.name,
            "rows": cells,
            "mirror": probe_summary(sub),
        })
    return out


def _fmt(x, digits=4) -> str:
    return "-" if x is None else f"{x:.{digits}g}"


def target_rows_met(point: dict) -> tuple[list[str], list[str], list[str], list[str]]:
    """(met, failed, incomplete, not-swept) ratified-Target row ids at one
    bias point. A row that was run but is INCOMPLETE (some grid point has no
    valid value) is neither met nor not-swept: it is reported on its own."""
    met, failed, incomplete, unswept = [], [], [], []
    for row_id, _l, _u in ROWS:
        cell = point["rows"][row_id]
        if cell["state"] != "measured":
            if row_id != "5b":
                unswept.append(row_id)
            continue
        verdict = cell["target_verdict"]
        if verdict == grade_mod.NOT_SPECIFIED:
            continue
        if verdict == grade_mod.INCOMPLETE:
            incomplete.append(row_id)
        else:
            (met if verdict == grade_mod.PASS else failed).append(row_id)
    return met, failed, incomplete, unswept


def _incomplete_detail(point: dict, row_id: str) -> str:
    cell = point["rows"][row_id]
    missing = cell.get("missing") or []
    why = "; ".join(f"{m['point']}: {m['why']}" for m in missing[:2])
    if len(missing) > 2:
        why += f"; and {len(missing) - 2} more"
    return (f"{row_id} ({cell.get('points_valid')}/{cell.get('points_expected')} points valid"
            + (f"; {why}" if why else "") + ")")


def flags(point: dict) -> list[str]:
    """Reasons the comparison at this bias is NOT like-for-like with the
    others (empty = no screening flag). Weak inversion is a note only."""
    m = point.get("mirror") or {}
    if not m:
        return ["no mirror/headroom probes"]
    out = []
    if m["tail_near_triode_points"]:
        out.append(f"tail Vds < {TAIL_TRIODE_V} V early in evaluation at {m['tail_near_triode_points']}/{m['points']} "
                   "points (tail near triode: current below the mirror's 4x)")
    if m["tail_ref_vds_mismatch_points"]:
        out.append(f"tail Vds / reference Vds outside {TAIL_TO_REF_RANGE[0]}..{TAIL_TO_REF_RANGE[1]} at "
                   f"{m['tail_ref_vds_mismatch_points']}/{m['points']} points (mirror gain departs from 4 by CLM/DIBL; not measured)")
    return out


def notes(point: dict) -> list[str]:
    m = point.get("mirror") or {}
    if m and m.get("weak_inversion_points"):
        return [f"reference Vgs < {WEAK_INVERSION_VREF_V} V at {m['weak_inversion_points']}/{m['points']} points (weak inversion)"]
    return []


def render_markdown(result: dict) -> str:
    lines = [
        f"# `dut_ib` bias-point sweep -- campaign `{result['campaign']}`",
        "",
        "GENERATED by `python3 sim/run_klt_corner_verification.py ibsweep` from the committed",
        "per-bias envelopes in this directory, graded by the same `sim/kltsim/grade.py`",
        "rules as the issue #62 campaign. It proposes no bound and changes no spec row.",
        "",
        "Tail current = 4 x `dut_ib` (fixed 4:1 mirror: `XMB` 10u/0.5u -> `XMT` 40u/0.5u).",
        "",
        "## Pareto table (worst PVT point of 45 unless stated)",
        "",
        "| dut_ib (uA) | tail (uA) | " + " | ".join(f"{label} [{unit}]" for _i, label, unit in ROWS) + " |",
        "|---|---|" + "---|" * len(ROWS),
    ]
    for p in result["points"]:
        cells = []
        for row_id, _l, _u in ROWS:
            c = p["rows"][row_id]
            if c["state"] != "measured":
                cells.append("not swept")
            else:
                tv = c["target_verdict"]
                sv = c["stretch_verdict"]
                tag = f"T {tv}" if tv != grade_mod.NOT_SPECIFIED else "T n/a"
                src = " [from `" + c["source"].split()[1] + "`]" if c.get("source") else ""
                cells.append(f"{_fmt(c['value'])} ({tag}; S {sv}){src}")
        lines.append(f"| {_fmt(p['dut_ib_ua'])} | {_fmt(p['tail_ua'])} | " + " | ".join(cells) + " |")
    lines += ["", "T = ratified Target, S = ratified Stretch (DR-0002); Row 5 has no Target bound,",
              "so its T column is `n/a`. `not swept` means that bench was not run at that bias.", "",
              "## Ratified Target rows per swept value", "",
              "| dut_ib (uA) | Target rows met | Target rows failed | Target rows incomplete | not swept at this bias | mirror / headroom flags (screening) |",
              "|---|---|---|---|---|---|"]
    for p in result["points"]:
        met, failed, incomplete, unswept = target_rows_met(p)
        fl = flags(p)
        inc = "; ".join(_incomplete_detail(p, r) for r in incomplete)
        lines.append(f"| {_fmt(p['dut_ib_ua'])} | {', '.join(met) or '-'} | {', '.join(failed) or '-'} | "
                     f"{inc or '-'} | {', '.join(unswept) or '-'} | {'; '.join(fl + notes(p)) or 'none'} |")
    lines += ["", "## Mirror and headroom indicators", "",
              "| dut_ib (uA) | reference Vgs (V) min..max | tail Vd early in evaluation (V) min..max | Vd/Vgs min..max |",
              "|---|---|---|---|"]
    for p in result["points"]:
        m = p.get("mirror") or {}
        if not m:
            lines.append(f"| {_fmt(p['dut_ib_ua'])} | - | - | - |")
            continue
        lines.append(
            f"| {_fmt(p['dut_ib_ua'])} | {m['vref_v']['min'][0]:.3f} ({m['vref_v']['min'][1].split('/')[0]}) .. "
            f"{m['vref_v']['max'][0]:.3f} | {m['tmid_eval_v']['min'][0]:.3f} .. {m['tmid_eval_v']['max'][0]:.3f} | "
            f"{m['tail_to_ref']['min'][0]:.2f} .. {m['tail_to_ref']['max'][0]:.2f} |")
    lines.append("")
    return "\n".join(lines)


def run(campaign: str, campaigns_dir: Path) -> dict:
    cdir = campaigns_dir / campaign
    result = sweep(cdir)
    (cdir / "ibsweep.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (cdir / "ibsweep.md").write_text(render_markdown(result), encoding="utf-8")
    return result


__all__ = ["run", "sweep", "render_markdown", "build_mod"]

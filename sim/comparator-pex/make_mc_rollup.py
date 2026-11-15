#!/usr/bin/env python3
"""Roll up the committed extracted whole-latch Monte Carlo point reports (issue #61).

usage: make_mc_rollup.py <out_stem>      write <out_stem>.json and <out_stem>.md (refuses to overwrite)
       make_mc_rollup.py --check <out_stem>   regenerate in memory and compare with the committed pair

Reads only `reports/batch-mc-{offset,noise}-*.json` (the per-point records that already exist); nothing is
re-simulated. For every PVT point it restates, from the committed rows, the schematic and extracted offset sigma
(sample, N-1, over samples with a value on BOTH sides) or the committed transient-noise probit fit, the sample or
trial counts, and the ratified DR-0002 bound it is read against. The bound is quoted, never changed: DR-0002 Row 1
Target is 3 sigma <= 15 mV, Row 2 Target is <= 1.0 mV rms. A single point is a Monte Carlo sigma at that point; the
roll-up lists the points covered out of the 45-point grid and does not claim the grid. Per-point offset sigma is
quantized by the 3 mV `lowcount` staircase and the per-point noise fit has about 13 % 1-sigma scatter at N = 80, so
the roll-up reports a difference only as a ratio and marks nothing as established.
"""
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
OFFSET_TARGET_3SIGMA_MV = 15.0   # DR-0002 Row 1 ratified Target (quoted, not changed)
NOISE_TARGET_MV = 1.0            # DR-0002 Row 2 ratified Target (quoted, not changed)
GRID_POINTS = 45                 # 5 process x 3 temperature x 3 supply
CORNER = re.compile(r"^(\w+)/\w+/(-?\d+)C/params:vdd_val=([0-9.]+)")


def point_key(proc, temp, vdd):
    return f"{proc}/{int(temp)}C/{float(vdd):.2f}V"


def _vos_pairs(d):
    """Return {sample: (schematic, extracted)} for vos_mv from any of the three committed layouts."""
    out = {}
    if "samples" in d:
        for s in d["samples"]:
            v = s.get("vos_mv", {})
            out[s["sample"]] = (v.get("schematic"), v.get("extracted"))
        return out
    for r in d["rows"]:
        name = r.get("spec_row", r.get("measurement"))
        if name != "vos_mv":
            continue
        cid = r.get("corner_id", r.get("corner", ""))
        sample = r["sample"] if "sample" in r else int(cid.rsplit("/mc", 1)[1])
        sch = r.get("schematic_value", r.get("schematic"))
        ext = r.get("extracted_value", r.get("extracted"))
        out[sample] = (sch, ext)
    return out


def _offset_point(d):
    if "corner" in d:  # nominal record: "tt / 27 C / vdd 1.20 V, mos_tt_mismatch"
        m = re.match(r"(\w+) / (-?\d+) C / vdd ([0-9.]+) V", d["corner"])
        return point_key(*m.groups())
    for r in d["rows"]:
        m = CORNER.match(r.get("corner_id", r.get("corner", "")))
        if m:
            return point_key(m.group(1), m.group(2), m.group(3))
    raise ValueError("no corner id found")


def offset_entry(path):
    d = json.loads(path.read_text())
    pairs = _vos_pairs(d)
    both = [(s, e) for s, e in pairs.values() if s is not None and e is not None]
    n_req = d.get("n", 60)
    if len(both) < 2:
        return {"file": path.name, "point": _offset_point(d), "n_requested": n_req, "n_compared": len(both),
                "usable": False}
    sch = [s for s, _ in both]
    ext = [e for _, e in both]
    ss, se = statistics.stdev(sch), statistics.stdev(ext)
    return {"file": path.name, "point": _offset_point(d), "n_requested": n_req, "n_compared": len(both),
            "sigma_sch_mv": round(ss, 2), "sigma_ext_mv": round(se, 2),
            "sigma_ratio_ext_over_sch": round(se / ss, 2),
            "three_sigma_sch_mv": round(3 * ss, 2), "three_sigma_ext_mv": round(3 * se, 2),
            "within_15mv_target_both": 3 * max(ss, se) <= OFFSET_TARGET_3SIGMA_MV,
            "envelope_status": d.get("status"), "usable": True}


def noise_entry(path):
    d = json.loads(path.read_text())
    p = d["point"]
    proc = p["process"].split()[0]
    key = point_key(proc, p["temperature_c"], p["vdd_v"])
    n_req = d["n"]
    n_cmp = d.get("n_compared", n_req if "n_compared" not in d else None)
    fit = d.get("fit")
    if fit is None:
        return {"file": path.name, "point": key, "n_requested": n_req, "n_compared": n_cmp, "usable": False}
    e = {"file": path.name, "point": key, "n_requested": n_req, "n_compared": n_cmp,
         "sigma_sch_mv": round(fit["schematic"]["sigma_mv"], 2),
         "sigma_ext_mv": round(fit["extracted"]["sigma_mv"], 2),
         "clamped_rungs_sch": fit["schematic"]["clamped_rungs"],
         "clamped_rungs_ext": fit["extracted"]["clamped_rungs"],
         "envelope_status": d["envelope"]["status"], "usable": True}
    e["ext_fit_rough"] = bool(e["clamped_rungs_ext"])
    e["sch_fit_rough"] = bool(e["clamped_rungs_sch"])
    e["within_1mv_target_both"] = max(e["sigma_sch_mv"], e["sigma_ext_mv"]) <= NOISE_TARGET_MV
    return e


def best_per_point(entries):
    """One entry per point: most compared samples wins, later file name breaks ties; the rest are listed superseded."""
    by = {}
    for e in entries:
        by.setdefault(e["point"], []).append(e)
    chosen, superseded = [], []
    for k in sorted(by):
        c = sorted(by[k], key=lambda x: (x["n_compared"] or 0, x["file"]))
        chosen.append(c[-1])
        superseded += [{"point": k, "file": x["file"], "n_compared": x["n_compared"]} for x in c[:-1]]
    return chosen, superseded


def build():
    off = [offset_entry(p) for p in sorted(REPORTS.glob("batch-mc-offset-*-n60.*.json"))]
    noi = [noise_entry(p) for p in sorted(REPORTS.glob("batch-mc-noise-*-n80.*.json"))]
    off_c, off_s = best_per_point(off)
    noi_c, noi_s = best_per_point(noi)
    return {
        "issue": 61,
        "purpose": "roll-up of committed per-point extracted whole-latch Monte Carlo reports; no new simulation",
        "bounds_quoted": {"offset_3sigma_target_mv": OFFSET_TARGET_3SIGMA_MV,
                          "noise_target_mv_rms": NOISE_TARGET_MV, "source": "spec/decision-records/0002"},
        "grid_points": GRID_POINTS,
        "offset": {"points": off_c, "superseded": off_s, "points_with_data": sum(e["usable"] for e in off_c)},
        "noise": {"points": noi_c, "superseded": noi_s, "points_with_data": sum(e["usable"] for e in noi_c)},
    }


def render_md(r, stem):
    L = ["# Extracted whole-latch Monte Carlo roll-up, per point (issue #61)", "",
         "Derived only from the committed per-point reports named in the last column; nothing was simulated for this "
         "file and nothing ran locally. Regenerate with `python3 sim/comparator-pex/make_mc_rollup.py --check "
         f"sim/comparator-pex/reports/{stem}`.", "",
         "## Reading rules", "",
         "- Each row is a Monte Carlo sigma **at one PVT point**. It is not a corner-matrix result and not a sigma of "
         f"the grid. {r['offset']['points_with_data']} offset and {r['noise']['points_with_data']} noise points have "
         f"data, out of {GRID_POINTS} grid points.",
         "- Offset sigma is the sample (N-1) sigma over samples with a value on both sides, quantized by the 3 mV "
         "staircase, with about 9 % relative uncertainty at N = 60. A ratio near 1 establishes no difference.",
         "- Noise is the probit-fit sigma of the committed report; a fit with a clamped rung is rough and is marked. "
         "About 13 % 1-sigma scatter at N = 80.",
         "- The DR-0002 Targets are quoted unchanged (offset 3 sigma <= 15 mV, noise <= 1.0 mV rms). The `within` column "
         "only restates that comparison for this point; it is **not** a DR-0002 verdict, because the rows require every "
         "grid point (offset) or the ratified compliance statistic (noise) and neither is complete here.", "",
         "## Offset (DR-0002 Row 1), N = 60 requested per point", "",
         "| point | compared | sigma sch | sigma ext | ratio | 3 sigma sch | 3 sigma ext | both <= 15 mV | envelope | file |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for e in r["offset"]["points"]:
        if e["usable"]:
            L.append(f"| {e['point']} | {e['n_compared']}/{e['n_requested']} | {e['sigma_sch_mv']:.2f} | "
                     f"{e['sigma_ext_mv']:.2f} | {e['sigma_ratio_ext_over_sch']:.2f} | {e['three_sigma_sch_mv']:.2f} | "
                     f"{e['three_sigma_ext_mv']:.2f} | {'yes' if e['within_15mv_target_both'] else 'NO'} | "
                     f"{e['envelope_status']} | `{e['file']}` |")
        else:
            L.append(f"| {e['point']} | {e['n_compared']}/{e['n_requested']} | - | - | - | - | - | no data | - | `{e['file']}` |")
    L += ["", "## Transient noise (DR-0002 Row 2), N = 80 trials per rung requested", "",
          "| point | trials compared | sigma sch | sigma ext | clamped rungs ext | both <= 1.0 mV | envelope | file |",
          "|---|---|---|---|---|---|---|---|"]
    for e in r["noise"]["points"]:
        if e["usable"]:
            L.append(f"| {e['point']} | {e['n_compared']}/{e['n_requested']} | {e['sigma_sch_mv']:.2f} | "
                     f"{e['sigma_ext_mv']:.2f} | {', '.join(e['clamped_rungs_ext']) or 'none'} | "
                     f"{'yes' if e['within_1mv_target_both'] else 'NO'} | {e['envelope_status']} | `{e['file']}` |")
        else:
            L.append(f"| {e['point']} | {e['n_compared']}/{e['n_requested']} | - | - | - | no fit | - | `{e['file']}` |")
    for name in ("offset", "noise"):
        if r[name]["superseded"]:
            L += ["", f"Superseded {name} files for a point that has a better record (kept, not edited): "
                  + ", ".join(f"`{s['file']}` ({s['point']}, {s['n_compared']} compared)" for s in r[name]["superseded"])]
    L += ["", "## Not established", "",
          "The remaining grid points, any DR-0002 offset or noise verdict, `td_c` (no extracted value at any corner; see "
          "`batch-extracted-grid.regeneration.20261031.md`), and the item-7 citation: `klt signoff` accepts only a `klt "
          "pex` report for item 7, and the committed one is the single-corner run. Item 7 stays `unmet`.", ""]
    return "\n".join(L)


def main(argv):
    check = argv[:1] == ["--check"]
    args = argv[1:] if check else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    stem = Path(args[0])
    r = build()
    js = json.dumps(r, indent=1, sort_keys=True) + "\n"
    md = render_md(r, stem.name)
    jp, mp = stem.parent / (stem.name + ".json"), stem.parent / (stem.name + ".md")
    if check:
        ok = jp.exists() and mp.exists() and jp.read_text() == js and mp.read_text() == md
        print("fresh" if ok else "STALE")
        return 0 if ok else 1
    if jp.exists() or mp.exists():
        print("refusing to overwrite", jp, mp, file=sys.stderr)
        return 2
    jp.write_text(js)
    mp.write_text(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

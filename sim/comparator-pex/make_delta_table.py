#!/usr/bin/env python3
"""Render the per-row schematic-vs-extracted delta table from a klt pex envelope.

usage: make_delta_table.py <pex_report.json> <out_stem>
Writes <out_stem>.json and <out_stem>.md (new files only; refuses to overwrite).

Two separate readings per row (issue #181). Availability: klt's raw status and
delta_pct, kept verbatim; `pass` only means both legs produced a value (the
requests set no limits). Interpretation: only keys in LOGIC/DELAY are graded;
every other key stays ungraded. Measurements are deterministic, so nothing
here implies a sigma or offset/noise compliance. Malformed input exits 2.
"""
import json
import math
import re
import sys
from pathlib import Path

# The benches' own polarity checks (tb.json `checks`): outputs normalised to their
# supply must read <= 0.1 (low) or >= 0.9 (high). Keyed (bench, measurement).
LOW, HIGH = 0.1, 0.9
LOGIC = {**{("regeneration", m): "low" for m in ("da_first", "db_first", "dc_first")},
         **{(b, m): "high" for b in ("regeneration", "kickback") for m in ("da_end", "db_end", "dc_end")}}
# DR-0002 Row 3 absolute bounds (seconds); apply at every point of the PVT grid.
DELAY = {("regeneration", "td_a"): (1.5e-9, "DR-0002 Row 3 Target: <= 1.5 ns at 50 mV overdrive"),
         ("regeneration", "td_c"): (2.0e-9, "DR-0002 Row 3 sub-row: <= 2.0 ns at 0.1 mV overdrive")}
GRID = ({"tt", "ff", "ss", "fs", "sf"}, {1.08, 1.2, 1.32}, {-40, 27, 125})
CORNER = re.compile(r"(\w+)/([0-9.]+)V/(-?\d+)C")
FIELDS = ("spec_row", "corner_id", "schematic_value", "extracted_value", "delta_pct", "status")


def in_grid(corner):
    m = CORNER.fullmatch(corner)
    return bool(m) and m[1] in GRID[0] and float(m[2]) in GRID[1] and int(m[3]) in GRID[2]


def state(v):
    return "missing" if v is None else "low" if v <= LOW else "high" if v >= HIGH else "indeterminate"


def interpret(r, k):
    x = r["extracted_value"]
    if k in LOGIC:
        want, se, xe = LOGIC[k], state(r["schematic_value"]), state(x)
        v = "correct" if xe == want else xe if xe in ("missing", "indeterminate") else "WRONG STATE"
        return {"kind": "logic", "expected": want, "schematic_state": se, "extracted_state": xe,
                "state_change": se != xe, "verdict": f"{v} (expected {want})"}
    if k in DELAY:
        lim, src = DELAY[k]
        if not in_grid(r["corner_id"]):
            return {"kind": "delay", "criterion": src, "verdict": "ungraded: corner outside the ratified PVT grid"}
        v = "missing: no verdict" if x is None else "EXCEEDS" if x > lim else "within"
        return {"kind": "delay", "criterion": src, "limit_s": lim, "verdict": v}
    return {"kind": None, "verdict": "ungraded (no mapped criterion)"}


def load(path):
    def bad(c):
        raise ValueError(f"non-finite JSON constant {c}")
    return json.loads(Path(path).read_text(), parse_constant=bad)


def render(env, source):
    if not isinstance(env, dict) or not isinstance(env.get("delta"), list) or not env["delta"]:
        raise ValueError("envelope has no delta[] rows")
    rows, seen, got, summary = [], set(), {}, {}
    for i, r in enumerate(env["delta"]):
        if not isinstance(r, dict) or any(k not in r for k in FIELDS):
            raise ValueError(f"delta[{i}]: missing one of {FIELDS}")
        if not all(isinstance(r[k], str) and r[k] for k in ("spec_row", "corner_id", "status")) \
                or "." not in r["spec_row"]:
            raise ValueError(f"delta[{i}]: bad spec_row/corner_id/status")
        for f in FIELDS[2:5]:
            if r[f] is not None and not (type(r[f]) in (int, float) and math.isfinite(r[f])):
                raise ValueError(f"delta[{i}].{f}: expected a finite number or null, got {r[f]!r}")
        if (r["spec_row"], r["corner_id"]) in seen:
            raise ValueError(f"delta[{i}]: duplicate {r['spec_row']} @ {r['corner_id']}")
        seen.add((r["spec_row"], r["corner_id"]))
        k = (r["spec_row"].split(".")[0], r["spec_row"].split(".")[-1])
        has = (r["schematic_value"] is not None, r["extracted_value"] is not None)
        rows.append({**{f: r[f] for f in FIELDS}, "availability": "both legs measured" if all(has) else
                     "extracted missing" if has[0] else "schematic missing" if has[1] else
                     "neither leg measured", "interpretation": interpret(r, k)})
        if "limit_s" in rows[-1]["interpretation"]:
            got.setdefault(k, {}).setdefault(rows[-1]["interpretation"]["verdict"], set()).add(r["corner_id"])
    corners = sorted({r["corner_id"] for r in rows})
    for k, g in got.items():  # the bound applies at every one of the 45 grid points
        ex, ok = g.get("EXCEEDS", ()), g.get("within", ())
        summary[".".join(k)] = (
            f"NOT MET: extracted exceeds at {len(ex)} corner(s)" if ex else
            "met at every PVT grid point" if len(ok) == 45 and len(g) == 1 else
            f"not established: {len(ok)}/45 grid points within, "
            f"{len(g.get('missing: no verdict', ()))} missing") + f" ({DELAY[k][1]})"
    out = {
        "source_envelope": str(source),
        "klt_version": (env.get("provenance") or {}).get("klt_version"),
        "envelope_status": env.get("status"),
        "passed": env.get("passed"), "failed": env.get("failed"), "errored": env.get("errored"),
        "klt_status_meaning": "measurement availability (both legs produced a value; no limits "
                              "are set in the requests), not circuit compliance",
        "corners": corners,
        "pvt_grid_points": sum(map(in_grid, corners)),
        "statistical_basis": f"none: deterministic transient measurements at {len(corners)} corner(s)"
                             "; no Monte Carlo, no seeds; no sigma or offset/noise compliance is implied",
        "delay_compliance_extracted": summary,
        "rows": rows,
    }
    return out, markdown(out)


def markdown(out):
    fmt = lambda v: "n/a (no value)" if v is None else f"{v:.6g}"  # noqa: E731
    lines = [f"Statistical basis: {out['statistical_basis']}. Corners: {', '.join(out['corners'])}.", "",
             f"klt status = {out['klt_status_meaning']}.", ""]
    lines += [f"- `{k}`: {v}" for k, v in out["delay_compliance_extracted"].items()] + [""]
    lines += ["| row | corner | schematic | extracted | delta % (raw) | klt status (availability) | interpretation |",
              "|---|---|---|---|---|---|---|"]
    for r in out["rows"]:
        i = r["interpretation"]
        d = "n/a" if r["delta_pct"] is None else f"{r['delta_pct']:+.3f}"
        if i["kind"] == "logic":
            d, v = "n/a: logic state", f"{i['schematic_state']} -> {i['extracted_state']}: {i['verdict']}"
        else:
            v = i["verdict"] + (f" vs {i['limit_s'] * 1e9:g} ns" if "limit_s" in i else "")
        lines.append(f"| {r['spec_row']} | {r['corner_id']} | {fmt(r['schematic_value'])} | "
                     f"{fmt(r['extracted_value'])} | {d} | {r['status']} | {v} |")
    return "\n".join(lines) + "\n"


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    src, stem = Path(argv[0]), Path(argv[1])
    try:
        out, md = render(load(src), src)
    except (OSError, ValueError) as e:
        print(f"error: {src}: {e}", file=sys.stderr)
        return 2
    paths = [stem.with_suffix(".json"), stem.with_suffix(".md")]
    for p in paths:
        if p.exists():
            print(f"refusing to overwrite {p}", file=sys.stderr)
            return 1
    for p, text in zip(paths, (json.dumps(out, indent=2) + "\n", md)):
        with open(p, "x") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

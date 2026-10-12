#!/usr/bin/env python3
"""Render the per-row schematic-vs-extracted delta table from a klt pex envelope.

usage: make_delta_table.py <pex_report.json> <out_stem>
Writes <out_stem>.json and <out_stem>.md (new files only; refuses to overwrite).

Two separate readings per row (issue #181). Availability: klt's raw status and
delta_pct, kept verbatim; `pass` only means both legs produced a value (the
requests set no limits). Interpretation: only keys in LOGIC/DELAY are graded;
every other key stays ungraded. Measurements are deterministic, so nothing
here implies a sigma or offset/noise compliance. Malformed input exits 2.

Evidence validation (issue #211). Corners are canonicalised to a physical
(process, voltage, temperature) identity (Decimal voltage, int temperature), so
`tt/1.2V/27C` and `tt/1.200V/27C` are one point. For every mapped key (LOGIC or
DELAY) a physical point may appear in at most one row, whatever the spelling or
nominal/pvt variant; a repeat is ambiguous evidence and is rejected, never
merged. Full-grid compliance compares the set of canonical identities that are
`within` with the explicit Cartesian product of GRID, not a count. A negative
mapped delay (target before trigger) is invalid evidence and is rejected with
the row and corner. Zero is a finite measurement (target coincident with the
trigger at the sampling resolution): it is accepted and graded against the
upper bound only; no lower spec bound exists in DR-0002 and none is invented.
Out-of-grid measurements stay ungraded. Raw fields and statuses are preserved.

Decision validity (issue #240). A decision time is only meaningful if the node
it times actually made the expected decision. TIMING_STATES maps each graded
delay to the first/end state measurements of the same bench and channel (from
the staged regeneration request cards: td_a times v(dan) so needs da_first low
and da_end high; td_c likewise with dc_*). Rows are joined through the canonical
physical point, so row order and voltage spelling do not matter; kickback.*
states are a different bench and never satisfy the join. A wrong, indeterminate
or missing (absent row or null value) required state leaves that point's delay
"decision state not valid": the numeric verdict (within/EXCEEDS) and raw values
stay visible, but the point does not count toward "met at every PVT grid point".
EXCEEDS still reports NOT MET whatever the validity. No bound is invented.
"""
import itertools
import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

# The benches' own polarity checks (tb.json `checks`): outputs normalised to their
# supply must read <= 0.1 (low) or >= 0.9 (high). Keyed (bench, measurement).
LOW, HIGH = 0.1, 0.9
LOGIC = {**{("regeneration", m): "low" for m in ("da_first", "db_first", "dc_first")},
         **{(b, m): "high" for b in ("regeneration", "kickback") for m in ("da_end", "db_end", "dc_end")}}
# DR-0002 Row 3 absolute bounds (seconds); apply at every point of the PVT grid.
DELAY = {("regeneration", "td_a"): (1.5e-9, "DR-0002 Row 3 Target: <= 1.5 ns at 50 mV overdrive"),
         ("regeneration", "td_c"): (2.0e-9, "DR-0002 Row 3 sub-row: <= 2.0 ns at 0.1 mV overdrive")}
# Required decision states per graded delay: same bench, same channel (issue #240).
TIMING_STATES = {("regeneration", "td_a"): (("regeneration", "da_first"), ("regeneration", "da_end")),
                 ("regeneration", "td_c"): (("regeneration", "dc_first"), ("regeneration", "dc_end"))}
GRID = ({"tt", "ff", "ss", "fs", "sf"}, {Decimal("1.08"), Decimal("1.2"), Decimal("1.32")}, {-40, 27, 125})
GRID_POINTS = frozenset(itertools.product(*GRID))
CORNER = re.compile(r"(\w+)/([0-9.]+)V/(-?\d+)C")
FIELDS = ("spec_row", "corner_id", "schematic_value", "extracted_value", "delta_pct", "status")


def canonical(corner):
    """Physical identity (process, volts, deg C); unparseable labels keep their raw text."""
    m = CORNER.fullmatch(corner)
    try:
        return (m[1], Decimal(m[2]), int(m[3])) if m else ("raw", corner)
    except InvalidOperation:
        return ("raw", corner)


def in_grid(corner):
    return canonical(corner) in GRID_POINTS


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


def decision_validity(rows, phys, got):
    """Per graded delay: which in-grid points have every required state correct (issue #240).

    Annotates each graded delay row's interpretation with `decision_validity` and returns
    a per-key summary. Does not change the numeric verdict.
    """
    out = {}
    for k, g in got.items():
        checked = set().union(*g.values())
        valid, invalid, counts = set(), [], {"wrong": 0, "indeterminate": 0, "missing": 0}
        for cid in sorted(checked, key=str):
            reasons = []
            for sk in TIMING_STATES[k]:
                j = phys.get((sk, cid))
                want = LOGIC[sk]
                have = None if j is None else rows[j]["interpretation"]["extracted_state"]
                if have == want:
                    continue
                cat = "missing" if have in (None, "missing") else "indeterminate" if have == "indeterminate" else "wrong"
                counts[cat] += 1
                reasons.append(f"{'.'.join(sk)} {cat}" + (" (no row)" if j is None else f" (expected {want})"))
            label = "/".join(str(x) for x in cid)
            if reasons:
                invalid.append({"corner": label, "reasons": reasons})
            else:
                valid.add(cid)
            for i in phys_rows(phys, k, cid):
                rows[i]["interpretation"]["decision_validity"] = (
                    "valid: " + ", ".join(".".join(x) for x in TIMING_STATES[k]) + " correct" if not reasons
                    else "decision state not valid: " + "; ".join(reasons))
        out[".".join(k)] = {"checked_points": checked, "valid_points": valid, "invalid": invalid, "counts": counts}
    return out


def phys_rows(phys, k, cid):
    return [phys[k, cid]] if (k, cid) in phys else []


def render(env, source):
    if not isinstance(env, dict) or not isinstance(env.get("delta"), list) or not env["delta"]:
        raise ValueError("envelope has no delta[] rows")
    rows, seen, phys, got, summary = [], set(), {}, {}, {}
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
        if k in LOGIC or k in DELAY:
            cid = canonical(r["corner_id"])
            if (k, cid) in phys:
                j = phys[k, cid]
                raise ValueError(
                    f"delta[{i}]: {r['spec_row']} @ {r['corner_id']} repeats the physical point of "
                    f"delta[{j}] ({env['delta'][j]['spec_row']} @ {env['delta'][j]['corner_id']}) "
                    f"for mapped measurement {'.'.join(k)}; ambiguous evidence")
            phys[k, cid] = i
        if k in DELAY and r["extracted_value"] is not None and r["extracted_value"] < 0:
            raise ValueError(
                f"delta[{i}]: {r['spec_row']} @ {r['corner_id']}: negative extracted delay "
                f"{r['extracted_value']!r} s is invalid evidence (target preceded trigger)")
        has = (r["schematic_value"] is not None, r["extracted_value"] is not None)
        rows.append({**{f: r[f] for f in FIELDS}, "availability": "both legs measured" if all(has) else
                     "extracted missing" if has[0] else "schematic missing" if has[1] else
                     "neither leg measured", "interpretation": interpret(r, k)})
        if "limit_s" in rows[-1]["interpretation"]:
            got.setdefault(k, {}).setdefault(rows[-1]["interpretation"]["verdict"], set()).add(canonical(r["corner_id"]))
    corners = sorted({r["corner_id"] for r in rows})
    validity = decision_validity(rows, phys, got)
    for k, g in got.items():  # the bound applies at every one of the 45 grid points
        ex, ok = g.get("EXCEEDS", ()), g.get("within", ())
        vd = validity[".".join(k)]
        nvalid = len(vd["valid_points"])
        bad = vd["counts"]
        vtxt = (f"decision states valid at {nvalid}/{len(vd['checked_points'])} graded point(s); "
                f"wrong {bad['wrong']}, indeterminate {bad['indeterminate']}, missing {bad['missing']}")
        summary[".".join(k)] = (
            f"NOT MET: extracted exceeds at {len(ex)} corner(s); {vtxt}" if ex else
            f"met at every PVT grid point (all 45 within, all required decision states correct)"
            if set(ok) == GRID_POINTS and len(g) == 1 and nvalid == len(GRID_POINTS) else
            f"not established: {len(ok)}/45 grid points within, "
            f"{len(g.get('missing: no verdict', ()))} missing; {vtxt}") + f" ({DELAY[k][1]})"
    out = {
        "source_envelope": str(source),
        "klt_version": (env.get("provenance") or {}).get("klt_version"),
        "envelope_status": env.get("status"),
        "passed": env.get("passed"), "failed": env.get("failed"), "errored": env.get("errored"),
        "klt_status_meaning": "measurement availability (both legs produced a value; no limits "
                              "are set in the requests), not circuit compliance",
        "corners": corners,
        "pvt_grid_points": len({canonical(c) for c in corners} & GRID_POINTS),
        "statistical_basis": f"none: deterministic transient measurements at {len({canonical(c) for c in corners})} corner(s)"
                             "; no Monte Carlo, no seeds; no sigma or offset/noise compliance is implied",
        "delay_compliance_extracted": summary,
        "delay_decision_validity": {k: {"required_states": [".".join(x) for x in TIMING_STATES[tuple(k.split(".", 1))]],
                                        "counts": v["counts"], "invalid": v["invalid"]}
                                    for k, v in validity.items()},
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
            if "decision_validity" in i:
                v += f" [{i['decision_validity']}]"
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

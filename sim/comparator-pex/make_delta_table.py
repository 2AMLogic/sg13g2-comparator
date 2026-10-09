#!/usr/bin/env python3
"""Render the per-row schematic-vs-extracted delta table from a klt pex envelope.

usage: make_delta_table.py <pex_report.json> <out_stem>
Writes <out_stem>.json and <out_stem>.md (new files only; refuses to overwrite).
Single corner (tt/1.200V/27C); no statistics: these are deterministic
transient measurements, not sigmas.
"""
import json
import sys
from pathlib import Path

src, stem = Path(sys.argv[1]), Path(sys.argv[2])
env = json.loads(src.read_text())
rows = [
    {k: r[k] for k in ("spec_row", "corner_id", "schematic_value", "extracted_value", "delta_pct", "status")}
    for r in env["delta"]
]
out = {
    "source_envelope": str(src),
    "klt_version": env["provenance"]["klt_version"],
    "envelope_status": env["status"],
    "passed": env["passed"], "failed": env["failed"], "errored": env["errored"],
    "corners": sorted({r["corner_id"] for r in rows}),
    "statistical_basis": "none: deterministic single-corner transient measurements; no Monte Carlo, no seeds; no sigma is implied",
    "rows": rows,
}
for ext in (".json", ".md"):
    if stem.with_suffix(ext).exists():
        sys.exit(f"refusing to overwrite {stem.with_suffix(ext)}")
stem.with_suffix(".json").write_text(json.dumps(out, indent=2) + "\n")
fmt = lambda v: "n/a (no value)" if v is None else f"{v:.6g}"
lines = ["| row | corner | schematic | extracted | delta % | klt status |", "|---|---|---|---|---|---|"]
for r in rows:
    d = "n/a" if r["delta_pct"] is None else f"{r['delta_pct']:+.3f}"
    lines.append(f"| {r['spec_row']} | {r['corner_id']} | {fmt(r['schematic_value'])} | {fmt(r['extracted_value'])} | {d} | {r['status']} |")
stem.with_suffix(".md").write_text("\n".join(lines) + "\n")

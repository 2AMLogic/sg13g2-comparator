#!/usr/bin/env python3
"""Render the three-leg DIAGNOSTIC attribution report (issue #191).

usage: make_devonly_report.py <devonly_sim.json> <pex_nominal.json> <devonly_pvt_sim.json> <out_stem>
Writes <out_stem>.json and <out_stem>.md (new files only; refuses to overwrite).

Legs (same regeneration stimulus, wrapper, tt / 1.20 V / 27 C):
  schematic, extracted-device-only, full PEX. The device-representation and
routing increments are conditional differences in a nonlinear circuit, not a
unique additive physical decomposition. One deterministic corner: no sigma,
no compliance claim, no separation of finger count from junction geometry.
"""
import json
import sys
from pathlib import Path

DELAYS = {"td_a": "50 mV overdrive", "td_b": "1 mV overdrive", "td_c": "0.1 mV overdrive"}
STATE = {"da": "50 mV", "db": "1 mV", "dc": "0.1 mV"}


def fmt(v, unit=1e-9):
    return "no value" if v is None else f"{v / unit:.3f} ns"


def main(dev, pex, pvt, stem):
    dev = json.loads(Path(dev).read_text())
    pex = json.loads(Path(pex).read_text())
    pvt = json.loads(Path(pvt).read_text())
    dm = {m["name"]: m["value"] for m in dev["corners"][0]["measurements"]}
    pm = {r["spec_row"]: r for r in pex["delta"]}
    rows, reasons = {}, {}
    for k in dm:
        s, x = pm[k]["schematic_value"], pm[k]["extracted_value"]
        rows[k] = {"schematic": s, "device_only": dm[k], "full_pex": x}
        if x is None:
            reasons[k] = ("full_pex: measurement produced no value (td_c waits for a rising "
                          "transition of dcn that never occurs; dc_first already high)")
    out = {
        "kind": "diagnostic-attribution",
        "issue": 191,
        "compliance": "NOT compliance evidence; original full PEX (layout/comparator/pex_report.json) remains the item-7 artifact",
        "statistical_basis": "none: deterministic single-corner transient; no MC, no seeds, no sigma",
        "corner": "tt/1.200V/27C",
        "inputs": {
            "extracted_netlist": pex["netlist"] if isinstance(pex["netlist"], str) else pex["netlist"],
            "device_only_envelope_netlist_closure": dev["environment"]["netlist_closure"],
            "klt_sim_version_note": "device-only leg via klt sim; schematic and full PEX legs re-run via klt pex with the committed request on the same klt, and reproduce the 20261009 values exactly",
        },
        "extraction_scope": "lumped model: one series R per net terminal, one ground C per net, vertical-overlap coupling only; no lateral coupling, no distributed RC, quasi-static. The device-only leg keeps all 64 fingers (model, W, L, AS, AD, PS, PD verbatim) and removes 252 terminal R (collapsed to parent nets), 16 ground C and 52 coupling C. The bias mirror XMB is outside the layout and identical on all legs.",
        "rows": rows,
        "missing_measurement_reasons": reasons,
        "pvt": {
            "request": "requests/regeneration.devonly.pvt.json (+ stage_model_inputs, throwaway copy)",
            "backend": "batch", "status": pvt["status"], "corners": pvt["corner_count"],
            "passed": pvt["passed"], "failed": pvt["failed"], "errored": pvt["errored"],
            "job_id": pvt["environment"]["remote"]["job_id"],
            "runner_klt_version": pvt["environment"]["remote"]["runner_klt_version"],
            "cause": "batch_job_failed on every corner: batch_runner_version_mismatch (runner klt 0.5.0, client "
                     + pvt["environment"]["remote"]["client_klt_version"] + ")",
            "local_fallback": "none launched (host rule)",
            "envelope": "devonly-pvt-batch.20261011.json (all 45 points retained, all errored)",
        },
    }
    tda = rows["td_a"]
    inc_dev = tda["device_only"] - tda["schematic"]
    inc_rt = tda["full_pex"] - tda["device_only"]
    out["conditional_increments_td_a_s"] = {"schematic_to_device_only": inc_dev, "device_only_to_full_pex": inc_rt}
    for suf in (".json", ".md"):
        if Path(stem + suf).exists():
            sys.exit(f"refusing to overwrite {stem + suf}")
    Path(stem + ".json").write_text(json.dumps(out, indent=2) + "\n")
    L = ["# Extracted-device-only attribution (issue #191) -- DIAGNOSTIC, single corner", "",
         "Not compliance evidence and not a statistic: tt / 1.20 V / 27 C, deterministic transient, "
         "no Monte Carlo, no seeds, no sigma. The original full PEX stays the compliance artifact; "
         "DR-0002 bounds are unchanged.", "",
         "## Extraction scope", "", out["extraction_scope"], "",
         "## Decision delay (absolute)", "",
         "| Measure | Schematic | Extracted-device-only | Full PEX | DR-0002 Row 3 |", "|---|---|---|---|---|"]
    bound = {"td_a": "<= 1.5 ns", "td_c": "<= 2.0 ns", "td_b": "ungraded"}
    for k, why in DELAYS.items():
        r = rows[k]
        L.append(f"| {k} ({why}) | {fmt(r['schematic'])} | {fmt(r['device_only'])} | {fmt(r['full_pex'])} | {bound[k]} |")
    L += ["", "## Decision states (v at 18 ns, before the input flip, and at end)", "",
          "| Row | Schematic | Extracted-device-only | Full PEX |", "|---|---|---|---|"]
    for k in ("da_first", "db_first", "dc_first", "da_end", "db_end", "dc_end"):
        r = rows[k]
        L.append(f"| {k} | {r['schematic']:.3g} | {r['device_only']:.3g} | {r['full_pex']:.3g} |")
    L += ["", "## Conditional increments at 50 mV overdrive (td_a)", "",
          f"- schematic -> device-only: {inc_dev * 1e9:+.3f} ns (device representation and junction geometry, routing absent)",
          f"- device-only -> full PEX: {inc_rt * 1e9:+.3f} ns (routing RC, conditional on the extracted devices)", "",
          "These are conditional differences in a nonlinear circuit, not a unique additive decomposition. "
          "The device-only leg changes finger count and AS/AD/PS/PD together; they are not separated from each other. "
          "One corner cannot size a cause across PVT.", "",
          "## Missing measurements", ""]
    L += [f"- `{k}`: {v}" for k, v in reasons.items()] or ["- none"]
    L += ["", "## PVT staging (batch)", "",
          f"`klt sim --backend batch` on the 45-point device-only request: status `{pvt['status']}`, "
          f"{pvt['passed']} pass / {pvt['failed']} fail / {pvt['errored']} error, job `{out['pvt']['job_id']}`, "
          f"{out['pvt']['cause']}. No local grid fallback. All 45 points are retained in "
          "`devonly-pvt-batch.20261011.json`. No PVT claim is made.", ""]
    Path(stem + ".md").write_text("\n".join(L))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])

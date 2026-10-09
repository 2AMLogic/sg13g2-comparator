#!/usr/bin/env python3
"""Emit the `klt sim` request JSONs for the klt-pex run from tb.json.

requests/<row>.nominal.json  one corner (mos_tt / 27 C / 1.20 V) -- single unit, local
requests/<row>.pvt.json      the 45-point PVT grid of the schematic benches
                             (5 process x 3 supply x 3 temp) -- batch only
Measurement cards are the original `meas tran` analyses, verbatim; the derived
`measure` expressions (tau, kick_*_mv, ...) are recomputed from the reported raw
values in the delta table, because klt pex diffs reported measurement names.

    python3 sim/comparator-pex/make_requests.py [--check]

`--check` writes nothing; it exits non-zero naming every missing or stale
request, nominal and PVT alike (issue #123).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # --check must leave the tree untouched
sys.path.insert(0, str(HERE))  # also under `python3 -I`
from make_reference import emit  # noqa: E402

SIM = HERE.parent
OSDI = [f"$PDK_ROOT/ihp-sg13g2/libs.tech/ngspice/osdi/{n}"
        for n in ("psp103.osdi", "psp103_nqs.osdi", "r3_cmc.osdi", "mosvar.osdi")]
SECTIONS = ["tt", "ff", "ss", "fs", "sf"]


def request(name: str, grid: bool) -> dict:
    tb = json.loads((SIM / f"comparator-{name}/testbench/tb.json").read_text())
    tran = next(a for a in tb["analyses"] if a.startswith("tran "))[5:]
    meas = []
    for a in tb["analyses"]:
        if a.startswith("meas tran "):
            meas.append({"name": a.split()[2], "spice": "." + a})
    if grid:
        corners = {
            "process": [{"name": s, "sections": [f"mos_{s}"]} for s in SECTIONS],
            "supply_v": {"vdd_val": [round(1.2 * (1 + k), 6) for k in (-0.1, 0.0, 0.1)]},
            "temperature_c": [-40, 27, 125],
        }
    else:
        corners = {"process": [{"name": "tt", "sections": ["mos_tt"]}],
                   "supply_v": {"vdd_val": [1.2]}, "temperature_c": [27]}
    return {
        "engine": "ngspice",
        "netlist": f"../dut/tb_{name}.sp",
        "netlist_source": "schematic",
        "models": {"pdk": "ihp-sg13g2", "lib": "libs.tech/ngspice/models/cornerMOSlv.lib"},
        "corners": corners,
        "analysis": {"kind": "tran", "args": tran},
        "measurements": meas,
        "options": {"osdi_preload": OSDI, "timeout_s": 3600, "keep_artifacts": False},
    }


if __name__ == "__main__":
    emit({HERE / "requests" / f"{name}.{'pvt' if grid else 'nominal'}.json":
          json.dumps(request(name, grid), indent=2) + "\n"
          for name in ("regeneration", "kickback") for grid in (False, True)},
         "--check" in sys.argv)

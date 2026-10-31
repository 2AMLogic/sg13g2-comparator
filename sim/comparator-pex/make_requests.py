#!/usr/bin/env python3
"""Emit the `klt sim` request JSONs for the klt-pex run from tb.json.

requests/<row>.nominal.json  one corner (mos_tt / 27 C / 1.20 V) -- single unit, local
requests/<row>.pvt.json      the 45-point PVT grid of the schematic benches
                             (5 process x 3 supply x 3 temp) -- batch only
Measurement cards are the original `meas tran` analyses, verbatim; the derived
`measure` expressions (tau, kick_*_mv, ...) are recomputed from the reported raw
values in the delta table, because klt pex diffs reported measurement names.
The supply is a `corners.params` axis (`vdd_val` is a `.param`, not a source, so
current klt rejects it under `supply_v`); `timeout_s` (600, ~3x the measured 173 s/unit) lets the client split the grid under the fleet's 3600 s whole-job ceiling.

Monte-Carlo rows (issue #61 acceptance row 3), whole latch, mismatch models:
requests/offset_mc.mc.json   N=60 per PVT point, seed 20260916 (the schematic bench's)
requests/noise.mc.json       N=80 per PVT point, seed 20260916 (the schematic bench's)
requests/<row>.mc.probe.json same bench, one point (mismatch tt / 27 C / 1.20 V), N=3 -- the
                             bounded live probe that precedes any grid submit
The per-sample reductions are the original bench's own (`lowcount`, `vos_mv`); the
dlevK reads live in the body as `.meas` cards, as in the schematic klt port.

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
            "params": {"vdd_val": [round(1.2 * (1 + k), 6) for k in (-0.1, 0.0, 0.1)]},
            "temperature_c": [-40, 27, 125],
        }
    else:
        corners = {"process": [{"name": "tt", "sections": ["mos_tt"]}],
                   "params": {"vdd_val": [1.2]}, "temperature_c": [27]}
    return {
        "engine": "ngspice",
        "netlist": f"../dut/tb_{name}.sp",
        "netlist_source": "schematic",
        "models": {"pdk": "ihp-sg13g2", "lib": "libs.tech/ngspice/models/cornerMOSlv.lib"},
        "corners": corners,
        "analysis": {"kind": "tran", "args": tran},
        "measurements": meas,
        "options": {"osdi_preload": OSDI, "timeout_s": 600, "keep_artifacts": False,
                    "stage_model_inputs": True},
    }


SEED = 20260916  # the schematic benches' setseed (tb.json evidence.mc_seed)
MC = {  # stem -> (bench dir, process section suffix, n per point)
    "offset_mc": ("offset-transient-mc", "_mismatch", 60),
    "noise": ("transient-noise", "", 80),
}


def mc_request(stem: str, probe: bool) -> dict:
    bench, suffix, n = MC[stem]
    tb = json.loads((SIM / f"comparator-{bench}/testbench/tb.json").read_text())
    tran = next(a.strip() for a in tb["analyses"] if a.strip().startswith("tran "))[5:]
    if stem == "offset_mc":
        levels = sum(a.strip().startswith("meas tran dlev") for a in tb["analyses"])
        step = 0.003  # DV_STEP of the staircase (tb.json 'let vos' line)
        dv_min = float(next(a for a in tb["analyses"] if a.strip().startswith("let vos")
                            ).split("=")[1].split("+")[0])
        low = "+".join(f"dlev{i}" for i in range(levels))
        meas = [
            {"name": "lowcount", "spice": f".meas tran lowcount param='{levels}-({low})'",
             "unit": "levels"},
            {"name": "vos_mv",
             "spice": f".meas tran vos_mv param='({dv_min}+(lowcount-0.5)*{step})*1e3'",
             "unit": "mV"},
            {"name": "vbias_mv", "spice": ".meas tran vbias_mv find par('v(ibn)*1e3') at=5n",
             "unit": "mV"},
        ]
    else:
        meas = [{"name": nm, "spice": f".meas tran {nm} find par('v({node})/v(vdd)') at=5n",
                 "unit": "V/V"}
                for nm, node in (("d_zero", "dout0"), ("d_plus", "dout1"), ("d_minus", "dout2"))]
    if probe:
        corners = {"process": [{"name": "tt", "sections": [f"mos_tt{suffix}"]}],
                   "params": {"vdd_val": [1.2]}, "temperature_c": [27]}
        n = 3
    else:
        corners = {
            "process": [{"name": s, "sections": [f"mos_{s}{suffix}"]} for s in SECTIONS],
            "params": {"vdd_val": [round(1.2 * (1 + k), 6) for k in (-0.1, 0.0, 0.1)]},
            "temperature_c": [-40, 27, 125],
        }
    return {
        "engine": "ngspice",
        "netlist": f"../dut/tb_{stem}.sp",
        "netlist_source": "schematic",
        "models": {"pdk": "ihp-sg13g2", "lib": "libs.tech/ngspice/models/cornerMOSlv.lib"},
        "corners": corners,
        "analysis": {"kind": "tran", "args": tran},
        "measurements": meas,
        "options": {"osdi_preload": OSDI, "timeout_s": 900, "keep_artifacts": False,
                    "stage_model_inputs": True},
        "monte_carlo": {"n": n, "seed": SEED, "vary": "mismatch"},
    }


if __name__ == "__main__":
    outputs = {HERE / "requests" / f"{name}.{'pvt' if grid else 'nominal'}.json":
               json.dumps(request(name, grid), indent=2) + "\n"
               for name in ("regeneration", "kickback") for grid in (False, True)}
    outputs.update({HERE / "requests" / f"{stem}.mc{'.probe' if probe else ''}.json":
                    json.dumps(mc_request(stem, probe), indent=2) + "\n"
                    for stem in MC for probe in (False, True)})
    emit(outputs, "--check" in sys.argv)

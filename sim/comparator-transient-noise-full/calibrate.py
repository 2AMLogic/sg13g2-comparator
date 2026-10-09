#!/usr/bin/env python3
"""Issue #81 density-calibration probe: ONE noise-free ngspice transient.

Derives the per-device conductances ``g`` that sim/kltsim/benches.py
INTERNAL_NOISE_DEVICES states (4 k T gamma g density, README "Density
calibration"). One run, one corner per invocation (a single-corner debug
probe; this is not a grid). The body is a campaign's ``tn_full_fe.body.spice``
with the front-end source scaled to zero, driven at the +od_x rung (``x1``).

    python3 calibrate.py --body ../klt-corner-verification/campaigns/<id>/tn_full_fe.body.spice \
        --process mos_tt --supply 1.2 --temp 27 [--out cal_tt_1p20_27.json]

Reduction:
* XM3..XM6: time-weighted mean |gm| over the regeneration-onset window
  1 mV < |v(ln)-v(lp)| < 100 mV, per device, then symmetrised per pair
  (XM3/XM4 nmos, XM5/XM6 pmos).
* XM7..XM10: triode gds at t = 0.9 ns (end of reset).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PDK = Path(os.environ.get("PDK_ROOT", Path.home() / "share/pdk")) / "ihp-sg13g2/libs.tech/ngspice"
EVAL = {"XM3": "nmos", "XM4": "nmos", "XM5": "pmos", "XM6": "pmos"}
RESET = {"XM7": "pmos", "XM8": "pmos", "XM9": "pmos", "XM10": "pmos"}
WIN = (1e-3, 100e-3)
T_RESET_END = 0.9e-9


def reduce_rows(rows: list[list[float]]) -> dict:
    """rows: [t, dv, (t, gm)*4, (t, gds)*4] as written by wrdata."""
    t = [r[0] for r in rows]
    dv = [r[1] for r in rows]
    out: dict = {"eval_gm_mean_abs": {}, "reset_gds": {}}
    window = 0.0
    for k, name in enumerate(EVAL):
        num = den = 0.0
        for i in range(1, len(t)):
            if WIN[0] < dv[i] < WIN[1]:
                dt = t[i] - t[i - 1]
                num += abs(rows[i][3 + 2 * k]) * dt
                den += dt
        out["eval_gm_mean_abs"][name] = num / den if den else None
        window = den
    out["window_seconds"] = window
    i = next(j for j, x in enumerate(t) if x >= T_RESET_END)
    for k, name in enumerate(RESET):
        out["reset_gds"][name] = rows[i][11 + 2 * k]
    gm = out["eval_gm_mean_abs"]
    out["symmetrised_g"] = {
        "XM3/XM4": (gm["XM3"] + gm["XM4"]) / 2, "XM5/XM6": (gm["XM5"] + gm["XM6"]) / 2,
        "XM7/XM8": (out["reset_gds"]["XM7"] + out["reset_gds"]["XM8"]) / 2,
        "XM9/XM10": (out["reset_gds"]["XM9"] + out["reset_gds"]["XM10"]) / 2,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", required=True)
    ap.add_argument("--process", default="mos_tt")
    ap.add_argument("--supply", type=float, default=1.2)
    ap.add_argument("--temp", type=float, default=27.0)
    ap.add_argument("--out")
    args = ap.parse_args()
    body = Path(args.body).read_text(encoding="utf-8")
    body = re.sub(r"/opt/pdk/ihp-sg13g2/libs\.tech/ngspice/osdi", str(PDK / "osdi"), body)
    body = re.sub(r"^\.param fe_scale=.*$", ".param fe_scale=0.0", body, flags=re.M)
    nets = [f"@n.x1.x1.{d}.nsg13_lv_{t}[gm]" for d, t in ((k.lower(), v) for k, v in EVAL.items())]
    nets += [f"@n.x1.x1.{d}.nsg13_lv_{t}[gds]" for d, t in ((k.lower(), v) for k, v in RESET.items())]
    with tempfile.TemporaryDirectory(prefix="cal81-") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "body.sp").write_text(body, encoding="utf-8")
        deck = "\n".join([
            "issue 81 density calibration (noise-free)",
            f".lib {PDK / 'models/cornerMOSlv.lib'} {args.process}",
            f".temp {args.temp}", ".include body.sp", ".options reltol=1e-2 abstol=1e-12", ".control",
            f"alter vsup={args.supply}",
            "save x1.x1.ln x1.x1.lp clk " + " ".join(nets),
            "tran 20p 5.1n 0 20p",
            "let dv = abs(v(x1.x1.ln)-v(x1.x1.lp))",
            "wrdata cal.out dv " + " ".join(nets), ".endc", ".end", ""])
        (tmp_path / "deck.cir").write_text(deck, encoding="utf-8")
        proc = subprocess.run(["ngspice", "-b", "deck.cir"], cwd=tmp_path, capture_output=True, text=True)
        if not (tmp_path / "cal.out").is_file():
            print(proc.stdout[-2000:], proc.stderr[-2000:], file=sys.stderr)
            return 1
        rows = [[float(x) for x in line.split()] for line in (tmp_path / "cal.out").read_text().splitlines()]
    result = {"process": args.process, "supply_v": args.supply, "temp_c": args.temp,
              "window_mV": [1, 100], "t_reset_end_s": T_RESET_END, **reduce_rows(rows)}
    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

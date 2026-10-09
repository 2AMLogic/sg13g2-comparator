#!/usr/bin/env python3
"""Derive the klt-pex testbench bodies in dut/ from the committed whole-latch
benches in sim/comparator-*/testbench/ (stimulus lines verbatim).

What changes, and why (see README.md):
  * exactly one `.include` (the schematic `comparator` core) -- the line klt pex
    re-points at the extraction;
  * the `comparator_dut` wrapper (bias mirror XMB + the core) is defined inline,
    because the layout covers only the core `comparator` cell;
  * `.param`s the harness would have supplied (vdd_val, dut_ib, dut_vcm) are
    stated, and the .options of the original tb.json are carried.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parent

PRELUDE = """\
* {name}: klt-pex body derived from sim/comparator-{name}/testbench/ by make_testbenches.py
* Stimulus/probe lines are verbatim from the original fragment.
.include comparator.schematic.sp
.param vdd_val=1.2
.param dut_ib={dut_ib}
.param dut_vcm={dut_vcm}
.options {options}
* comparator_dut wrapper (design/comparator.spice): bias mirror + the core cell.
* The mirror XMB is NOT in the layout; it is the same device on both legs.
.subckt comparator_dut vinp vinn clk ibias dout doutb vdd vss
XMB ibias ibias vss vss sg13_lv_nmos w=10u l=0.5u ng=1 m=1
x1 clk dout doutb ibias vdd vinn vinp vss comparator
.ends comparator_dut
"""


def build(name: str) -> str:
    tb = json.loads((SIM / f"comparator-{name}/testbench/tb.json").read_text())
    dut = json.loads((SIM / "dut.json").read_text())["params"]
    frag = (SIM / f"comparator-{name}/testbench/{tb['netlist']}").read_text().splitlines()
    body = [l for l in frag if l.strip() and not l.lstrip().startswith("*")]
    head = PRELUDE.format(name=name, dut_ib=dut["dut_ib"], dut_vcm=dut["dut_vcm"],
                          options=" ".join(tb["options"]))
    return head + "\n".join(body) + "\n"


if __name__ == "__main__":
    for name in ("regeneration", "kickback"):
        out = HERE / "dut" / f"tb_{name}.sp"
        text = build(name)
        if "--check" in sys.argv:
            if out.read_text() != text:
                sys.exit(f"stale: {out}")
        else:
            out.write_text(text)

#!/usr/bin/env python3
"""Derive the klt-pex testbench bodies in dut/ from the committed whole-latch
benches in sim/comparator-*/testbench/ (stimulus lines verbatim).

What changes, and why (see README.md):
  * exactly one `.include` (the schematic `comparator` core) -- the line klt pex
    re-points at the extraction;
  * the `comparator_dut` wrapper (bias mirror XMB + the core) is defined inline,
    because the layout covers only the core `comparator` cell. It is derived
    from the `.subckt comparator_dut` block of design/comparator.spice: header
    and non-core cards (XMB) verbatim, and the core instance's nets re-ordered
    to the extractor's pin order (make_reference.PINS), since the extracted
    `comparator` is instantiated positionally;
  * `.param`s the harness would have supplied (vdd_val, dut_ib, dut_vcm) are
    stated, and the .options of the original tb.json are carried.

    python3 sim/comparator-pex/make_testbenches.py [--check]

`--check` writes nothing; it exits non-zero naming every missing or stale
output (issue #123).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # --check must leave the tree untouched
sys.path.insert(0, str(HERE))  # also under `python3 -I`
import make_reference  # noqa: E402
from make_reference import PINS, emit, subckt  # noqa: E402

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
"""


def wrapper() -> str:
    """The schematic's `comparator_dut` wrapper, with its core instance
    re-pinned to the extractor's order."""
    src = make_reference.SRC.relative_to(make_reference.ROOT)
    core_pins, _ = subckt("comparator")
    pins, body = subckt("comparator_dut")
    cores = [i for i, l in enumerate(body) if l.split()[-1:] == ["comparator"]]
    if len(cores) != 1:
        sys.exit(f"{src}: expected exactly one `comparator` instance in "
                 f".subckt comparator_dut, found {len(cores)}")
    card = body[cores[0]].split()
    nets = card[1:-1]
    if len(nets) != len(core_pins):
        sys.exit(f"{src}: comparator_dut's core instance has {len(nets)} nets, "
                 f"the core declares {len(core_pins)} pins")
    by_pin = dict(zip(core_pins, nets))
    body[cores[0]] = " ".join([card[0], *(by_pin[p] for p in PINS), "comparator"])
    return "\n".join([".subckt comparator_dut " + " ".join(pins), *body,
                      ".ends comparator_dut", ""])


def build(name: str) -> str:
    tb = json.loads((SIM / f"comparator-{name}/testbench/tb.json").read_text())
    dut = json.loads((SIM / "dut.json").read_text())["params"]
    frag = (SIM / f"comparator-{name}/testbench/{tb['netlist']}").read_text().splitlines()
    body = [l for l in frag if l.strip() and not l.lstrip().startswith("*")]
    head = PRELUDE.format(name=name, dut_ib=dut["dut_ib"], dut_vcm=dut["dut_vcm"],
                          options=" ".join(tb["options"]))
    return head + wrapper() + "\n".join(body) + "\n"


if __name__ == "__main__":
    emit({HERE / "dut" / f"tb_{name}.sp": build(name) for name in ("regeneration", "kickback")},
         "--check" in sys.argv)

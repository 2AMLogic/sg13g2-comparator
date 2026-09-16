#!/usr/bin/env python3
"""Regenerate ``design/comparator.spice`` from the xschem sources in ``design/``.

The schematics are the source of record; ``design/comparator.spice`` is a
DERIVED artefact that must be regenerated (and re-committed) on every design
change.  ``CLAUDE.md``'s bar for this repo is "committed schematic sources (or
generator) plus the derived netlist, regenerated on design change" -- this
script is what makes the second half of that sentence mechanical rather than a
promise.

    python3 design/netlist.py            # regenerate design/comparator.spice
    python3 design/netlist.py --check    # fail if the committed file is stale

How it works, and why it is shaped this way:

* ``design/comparator_netlist_top.sch`` is a NETLIST-ASSEMBLY CELL.  It
  instantiates all three contract subcircuits once each so that a SINGLE
  xschem run emits every ``.subckt`` block (including the shared
  ``comparator`` core, emitted once) with no hand-merging of three separate
  netlists.  The assembly cell itself is never simulated: this script keeps
  only the ``.subckt`` ... ``.ends`` blocks and discards everything else,
  which is also what strips xschem's ``.end`` line.

* **The interface contract is imported, not restated.**  ``REQUIRED_SUBCKTS``
  comes from ``sim/harness/dut.py`` itself, so this generator and the
  harness's own load-time check can never disagree about the pin order.
  ``sim/dut/README.md`` warns that "a silently reordered pin list would
  miswire all four benches into plausible-looking wrong answers"; asserting
  the order here, at generation time, means a wrong xschem symbol pin order
  fails loudly at the moment it is introduced rather than at the moment
  somebody reads a record.

* The harness also forbids ``.include`` / ``.lib`` / ``.temp`` / ``.control``
  / ``.endc`` / ``.end`` in a DUT netlist (it owns all of those).  That is
  re-checked here for the same reason.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DESIGN_DIR = Path(__file__).resolve().parent
REPO_ROOT = DESIGN_DIR.parent

sys.path.insert(0, str(REPO_ROOT / "sim"))

from harness.dut import REQUIRED_SUBCKTS  # noqa: E402  (path set above)
from harness import pdk as pdk_mod  # noqa: E402

TOP_CELL = DESIGN_DIR / "comparator_netlist_top.sch"
OUTPUT = DESIGN_DIR / "comparator.spice"

#: Emission order in the generated file.  Definitions before uses is not
#: required by ngspice, but it makes the file readable top-down: the core
#: first, then the three contract wrappers around it.
SUBCKT_ORDER = (
    "comparator",
    "comparator_dut_analog",
    "comparator_dut_latch",
    "comparator_dut",
)

FORBIDDEN = (".control", ".endc", ".end", ".lib", ".temp", ".include")

HEADER = """\
* ============================================================================
* sg13g2-comparator -- DERIVED NETLIST.  DO NOT EDIT BY HAND.
* ============================================================================
*
* Generated from the xschem sources in design/ by:
*
*     python3 design/netlist.py
*
* The schematics are the source of record:
*
*   design/comparator.sch              the design -- a single-tail StrongARM
*                                      dynamic latch (spec/decision-records/
*                                      0001-comparator-topology.md), plus the
*                                      isolation inverters and NOR SR latch
*                                      that make its outputs HELD between
*                                      strobes as the interface contract
*                                      requires
*   design/comparator_dut.sch          contract wrapper: tail-bias reference
*                                      on the `ibias` pin + the core
*   design/comparator_dut_latch.sch    contract wrapper: the core with its
*                                      tail-bias node tied to vdd
*   design/comparator_dut_analog.sch   the LOOP-BROKEN reduced sub-model --
*                                      an offset/noise LOWER BOUND, not the
*                                      design's front end.  Read
*                                      design/README.md before quoting any
*                                      number measured against it.
*
* Interface contract: sim/dut/README.md.  Asserted at generation time by
* design/netlist.py (against sim/harness/dut.py's own REQUIRED_SUBCKTS) and
* again at load time by the harness.
*
* Parameters supplied by the harness, not by this file: dut_ib, dut_vcm,
* vdd_val, vdd_nom, temp_c (sim/harness/runner.py compose_deck).  This file
* deliberately contains no .include / .lib / .temp / .control / .endc / .end.
* ============================================================================

"""


def _xschemrc() -> Path:
    pdk = pdk_mod.find_pdk()
    rc = pdk.path / "libs.tech" / "xschem" / "xschemrc"
    if not rc.is_file():
        raise SystemExit(f"no xschemrc at {rc}; is this a complete {pdk.variant} install?")
    return rc


def _run_xschem(outdir: Path) -> str:
    if not shutil.which("xschem"):
        raise SystemExit(
            "xschem not found on PATH.  design/comparator.spice is derived from "
            "the xschem sources in design/; see sim/README.md 'Cold start'."
        )
    cmd = [
        "xschem",
        "--rcfile", str(_xschemrc()),
        "-n", "-s", "-q", "-x",
        "-o", str(outdir),
        str(TOP_CELL),
    ]
    env = dict(os.environ)
    # The PDK's own xschemrc flushes XSCHEM_LIBRARY_PATH to its own
    # directories and then appends whatever XSCHEM_USER_LIBRARY_PATH names
    # (see the installed checkout's libs.tech/xschem/xschemrc, bottom
    # "allow a user-specific path add-on" block). design/*.sym files
    # (comparator_dut.sym, comparator_dut_analog.sym, comparator_dut_latch.sym,
    # comparator.sym) live next to their .sch, NOT under the PDK's own
    # library tree, so without this xschem resolves every instance of them
    # to an EMPTY subcircuit with no error at all -- it prints
    # "IS MISSING !!!!" per missing instance and still exits nonzero, which
    # is what a first cut of this script (before this fix) hit. Pointing
    # XSCHEM_USER_LIBRARY_PATH at DESIGN_DIR, rather than blanking it, is
    # the fix; a stray real user library cannot leak in here regardless,
    # because this assignment always overwrites whatever the ambient
    # environment set.
    env["XSCHEM_USER_LIBRARY_PATH"] = str(DESIGN_DIR)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    produced = outdir / (TOP_CELL.stem + ".spice")
    if proc.returncode != 0 or not produced.is_file():
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"xschem netlisting failed (exit {proc.returncode})")
    return produced.read_text()


def _extract_subckts(text: str) -> dict[str, list[str]]:
    """Keep only complete ``.subckt`` ... ``.ends`` blocks.

    xschem brackets the top-level assembly cell with COMMENTED ``**.subckt`` /
    ``**.ends`` lines, so matching on a line that starts with ``.subckt``
    already excludes it; everything outside a block (``.end``, the
    ``* expanding symbol:`` banners, the top-level instance lines) is dropped.
    """
    blocks: dict[str, list[str]] = {}
    current: list[str] | None = None
    name = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        low = line.strip().lower()
        if low.startswith(".subckt "):
            name = line.split()[1]
            current = [line]
        elif current is not None:
            current.append(line)
            if low.startswith(".ends"):
                blocks[name] = current
                current = None
    if current is not None:
        raise SystemExit("xschem netlist ended inside an unterminated .subckt block")
    return blocks


def _assert_contract(blocks: dict[str, list[str]]) -> None:
    for name, pins in REQUIRED_SUBCKTS.items():
        if name not in blocks:
            raise SystemExit(
                f"generated netlist does not define `.subckt {name}` "
                f"(sim/dut/README.md 'Interface contract'); "
                f"found: {', '.join(sorted(blocks)) or '<none>'}"
            )
        declared = tuple(t.lower() for t in blocks[name][0].split()[2:] if "=" not in t)
        if declared != pins:
            raise SystemExit(
                f"`.subckt {name}` pin order is {' '.join(declared)}, contract "
                f"requires {' '.join(pins)} (sim/dut/README.md 'Interface "
                f"contract').  Fix the pin order in design/{name}.sym -- a "
                "reordered pin list silently miswires every testbench."
            )


def _assert_no_forbidden(lines: list[str]) -> None:
    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped.startswith("."):
            continue
        if stripped.lower().split()[0] in FORBIDDEN:
            raise SystemExit(
                f"generated netlist line {lineno}: {stripped.split()[0]} is owned "
                "by the harness and must not appear in a DUT netlist "
                "(sim/dut/README.md 'Interface contract')"
            )


def build() -> str:
    with tempfile.TemporaryDirectory(prefix="sg13g2-netlist-") as tmp:
        raw = _run_xschem(Path(tmp))
    blocks = _extract_subckts(raw)
    _assert_contract(blocks)
    unknown = sorted(set(blocks) - set(SUBCKT_ORDER))
    if unknown:
        raise SystemExit(
            f"generated netlist defines unexpected subcircuit(s): {', '.join(unknown)}.  "
            "Add them to SUBCKT_ORDER in design/netlist.py if that is intended."
        )
    body: list[str] = []
    for name in SUBCKT_ORDER:
        if name not in blocks:
            raise SystemExit(f"generated netlist is missing `.subckt {name}`")
        body += blocks[name] + [""]
    _assert_no_forbidden(body)
    return HEADER + "\n".join(body).rstrip("\n") + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit non-zero if the committed netlist is stale",
    )
    args = parser.parse_args()

    text = build()
    if args.check:
        current = OUTPUT.read_text() if OUTPUT.is_file() else ""
        if current != text:
            sys.stderr.write(
                f"{OUTPUT.relative_to(REPO_ROOT)} is stale with respect to the "
                "xschem sources in design/.  Re-run: python3 design/netlist.py\n"
            )
            return 1
        print(f"{OUTPUT.relative_to(REPO_ROOT)} is up to date with design/*.sch")
        return 0

    OUTPUT.write_text(text)
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

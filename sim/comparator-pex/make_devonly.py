#!/usr/bin/env python3
"""Derive the extracted-device-only DIAGNOSTIC leg (issue #191).

Input : layout/comparator/comparator.pex.spice (`klt pex` lumped-RC netlist).
Output: dut/comparator.devonly.sp -- the same 64 extracted finger devices with
        every model / W / L / AS / AD / PS / PD parameter preserved, but with
        the routing parasitics removed. Each device terminal `<net>__t<k>` is
        collapsed back to its parent net `<net>` (the node the series
        resistor `R<net>_t<k>` ties it to), then every extracted R and C is
        dropped. Terminals are never left floating.

This leg exists only to attribute the schematic -> full-PEX delay change
between (a) device representation / junction geometry and (b) routing RC.
It is a diagnostic, never compliance evidence; the original full PEX leg stays
the compliance artifact. The two increments are conditional differences in a
nonlinear circuit, not a unique additive decomposition.

The adapter REFUSES (exit non-zero / ValueError) anything it cannot map
unambiguously: unknown elements or directives, a series R that is not a
terminal-node resistor, a terminal node with no or several resistors, a
device node `*__t*` with no resistor, a capacitor touching a terminal node.

    python3 sim/comparator-pex/make_devonly.py [--check]

Also generates the diagnostic testbench bodies and requests
(`dut/tb_regeneration.devonly.sp`, `requests/regeneration.devonly.*.json`).
`--check` writes nothing (same contract as the other generators, issue #123).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # --check must leave the tree untouched
sys.path.insert(0, str(HERE))  # also under `python3 -I`
from make_reference import emit, ROOT, PINS  # noqa: E402

PEX = ROOT / "layout" / "comparator" / "comparator.pex.spice"
OUT = HERE / "dut" / "comparator.devonly.sp"
TERM = re.compile(r"^(?P<net>.+)__t(?P<k>\d+)$")
# Nodes the extractor ties to ground through a lone DC resistor; not routing.
GROUND_TIES = {"vsubs": "0"}


def logical_lines(text: str) -> list[str]:
    """Non-comment, non-blank cards with `+` continuations joined."""
    cards: list[str] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("*"):
            continue
        if raw.startswith("+"):
            if not cards:
                raise ValueError("continuation line before any card")
            cards[-1] += " " + raw[1:].strip()
        else:
            cards.append(raw.strip())
    return cards


def collapse(text: str) -> tuple[str, dict]:
    """(device-only netlist body, stats). Raises ValueError on refusal."""
    cards = logical_lines(text)
    subckt_hdr = None
    devices, resistors, caps = [], [], []
    for c in cards:
        tok = c.split()
        head = tok[0].lower()
        if head == ".global":
            if tok[1:] != ["vsubs"]:
                raise ValueError(f"unexpected .GLOBAL: {c}")
        elif head == ".subckt":
            if subckt_hdr is not None:
                raise ValueError("more than one .SUBCKT")
            subckt_hdr = tok
        elif head == ".ends":
            pass
        elif tok[0][0] in "Xx":
            devices.append(tok)
        elif tok[0][0] in "Rr":
            resistors.append(tok)
        elif tok[0][0] in "Cc":
            caps.append(tok)
        else:
            raise ValueError(f"unknown element or directive: {c}")
    if subckt_hdr is None:
        raise ValueError("no .SUBCKT found")
    if subckt_hdr[1].lower() != "comparator":
        raise ValueError(f"unexpected subckt: {subckt_hdr}")
    pins = subckt_hdr[2:]
    if pins != PINS:
        raise ValueError(f"pin order {pins} != {PINS}")

    # Series resistors: R<net>_t<k> <net>__t<k> <net> <value>
    term_to_parent: dict[str, str] = {}
    ties, n_term_r = [], 0
    for r in resistors:
        if len(r) != 4:
            raise ValueError(f"resistor with {len(r)} fields: {' '.join(r)}")
        name, a, b, _val = r
        m = TERM.match(a)
        if m is None:
            if a in GROUND_TIES and b == GROUND_TIES[a]:
                ties.append(r)
                continue
            raise ValueError(f"resistor is not a terminal-node series R: {' '.join(r)}")
        if TERM.match(b):
            raise ValueError(f"terminal node collapses onto another terminal: {' '.join(r)}")
        if m.group("net") != b or name != f"R{b}_t{m.group('k')}":
            raise ValueError(f"terminal resistor name/parent mismatch: {' '.join(r)}")
        if a in term_to_parent:
            raise ValueError(f"terminal node {a} has more than one resistor")
        term_to_parent[a] = b
        n_term_r += 1

    # Capacitors: ground (net -> vsubs) or net-to-net coupling; never a terminal.
    n_gnd = n_cc = 0
    for c in caps:
        if len(c) != 4:
            raise ValueError(f"capacitor with {len(c)} fields: {' '.join(c)}")
        a, b = c[1], c[2]
        if TERM.match(a) or TERM.match(b):
            raise ValueError(f"capacitor touches a terminal node: {' '.join(c)}")
        if "vsubs" in (a, b):
            n_gnd += 1
        elif c[0].startswith("Ccc_"):
            n_cc += 1
        else:
            raise ValueError(f"unclassified capacitor: {' '.join(c)}")

    out_dev, used = [], set()
    kept_geom = {}
    for d in devices:
        nodes, rest = d[1:5], d[5:]
        if not rest or not rest[0].startswith("sg13_lv_"):
            raise ValueError(f"unknown device model: {' '.join(d)}")
        new = []
        for n in nodes:
            if TERM.match(n):
                if n not in term_to_parent:
                    raise ValueError(f"unresolved terminal node {n} on {d[0]}")
                used.add(n)
                n = term_to_parent[n]
            new.append(n)
        out_dev.append(" ".join([d[0], *new, *rest]))
        kept_geom[d[0]] = rest
    if set(term_to_parent) != used:
        raise ValueError("terminal resistors with no device pin: "
                         + ", ".join(sorted(set(term_to_parent) - used)))

    body = "\n".join([
        "* GENERATED by sim/comparator-pex/make_devonly.py (issue #191) -- DIAGNOSTIC leg,",
        "* not compliance evidence. Source: layout/comparator/comparator.pex.spice",
        "* sha256 " + hashlib.sha256(text.encode()).hexdigest(),
        f"* {len(out_dev)} extracted devices, model/W/L/AS/AD/PS/PD verbatim; {n_term_r} terminal series",
        f"* R collapsed to parent nets; {n_gnd} ground C and {n_cc} coupling C removed;",
        f"* {len(ties)} DC substrate tie retained (no routing parasitic).",
        ".GLOBAL vsubs",
        ".subckt comparator " + " ".join(pins),
        *out_dev,
        *(" ".join(t) for t in ties),
        ".ends comparator",
        "",
    ])
    stats = {
        "source": str(PEX.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "pin_mapping": pins,
        "devices_retained": len(out_dev),
        "terminal_series_r_collapsed": n_term_r,
        "ground_c_removed": n_gnd,
        "coupling_c_removed": n_cc,
        "dc_ties_retained": len(ties),
        "device_geometry_retained": "model, W, L, AS, AD, PS, PD verbatim for every finger",
    }
    return body, stats


def build() -> dict:
    body, _ = collapse(PEX.read_text())
    outs = {OUT: body}
    tb = (HERE / "dut" / "tb_regeneration.sp").read_text()
    inc = ".include comparator.schematic.sp"
    if tb.count(inc) != 1:
        sys.exit("tb_regeneration.sp: expected exactly one schematic .include")
    outs[HERE / "dut" / "tb_regeneration.devonly.sp"] = tb.replace(
        inc, ".include comparator.devonly.sp").replace(
        "* regeneration:", "* regeneration (DEVICE-ONLY diagnostic leg, issue #191):", 1)
    for kind in ("nominal", "pvt"):
        req = json.loads((HERE / "requests" / f"regeneration.{kind}.json").read_text())
        req["netlist"] = "../dut/tb_regeneration.devonly.sp"
        outs[HERE / "requests" / f"regeneration.devonly.{kind}.json"] = (
            json.dumps(req, indent=2) + "\n")
    return outs


if __name__ == "__main__":
    if "--stats" in sys.argv:
        print(json.dumps(collapse(PEX.read_text())[1], indent=2))
    else:
        try:
            emit(build(), "--check" in sys.argv)
        except ValueError as e:
            sys.exit(f"refused: {e}")

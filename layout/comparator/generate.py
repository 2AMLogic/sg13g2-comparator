#!/usr/bin/env python3
"""Draw the ``comparator`` cell -- the 24-device StrongARM latch + SR output
stage of ``design/comparator.spice`` -- as one flat SG13G2 cell.

    python3 layout/comparator/generate.py            # write comparator.gds
    python3 layout/comparator/generate.py -o X.gds   # write elsewhere

Needs only ``klayout.db`` (the ``klayout`` PyPI package, which the pinned
``klayout-tools`` install brings along). No PDK install is read: every layer
number and rule value is a constant in ``layout/common_sg13g2.py``.

Before writing anything the generator checks its own device table against the
``.subckt comparator`` block of ``design/comparator.spice`` (the reference --
not a copy of it): the same 24 instances, the same LV flavour, the same
terminal nets (drain/source as an unordered pair, gate, bulk), the same L, and
a drawn total W equal to the schematic W. It also checks the pin list and that
every matched pair is drawn as identical unit cells. Any disagreement is a
hard failure, so a netlist change that the layout does not follow cannot
regenerate silently. This is an implementation self-check, not LVS (#60).

FLOORPLAN (bottom to top, every row centred on x = 0)::

    p-tap (vss)
    R_T    MT          8 x 5.0u  l=0.50   merged diffusion
    R_SW   MSW         8 x 5.0u  l=0.13   merged diffusion
    p-tap (vss)
    R_IN   M1/M2       ABBA, 4 unit cells x 2 x 3.0u   l=0.34
    R_LN   M3/M4       ABBA, 4 unit cells x 2 x 0.75u  l=0.13
    p-tap (vss)
    ---- NWell (vdd) ----
    n-tap (vdd)
    R_LP   M5/M6       ABBA, 4 unit cells x 2 x 0.75u
    R_RST  M9 M7 M8 | M8 M7 M10   6 unit cells x 2 x 1.5u
    R_OP   output PMOS (inverters + NOR pull-ups), mirror-symmetric
    n-tap (vdd)
    ---- end NWell ----
    p-tap (vss)
    R_ON   output NMOS (inverters + NOR pull-downs), mirror-symmetric
    p-tap (vss)

MATCHING STRATEGY

* Every matched device is built from identical *unit cells*: one Activ island
  carrying two fingers that share a central drain (source | gate | drain |
  gate | source). Islands are not merged with their neighbours, so every
  finger of A and of B sees the same length-of-diffusion, the same contact
  pattern and the same neighbouring-poly distance; a field-poly dummy at each
  row end reproduces the neighbouring-poly environment the inner units get
  from each other.
* M1/M2, M3/M4, M5/M6 and M7/M8 are placed A B B A (1-D common centroid: both
  devices' centroids sit at x = 0, removing a linear gradient along x).
  M9/M10 have one unit each and sit mirror-symmetrically at the row ends of
  the reset row. The output stage (no matching requirement) is drawn
  mirror-symmetric so the two latch outputs see the same load.
* Routing: per row, gate nets ride horizontal Metal2 buses below the devices
  and source/drain nets horizontal Metal2 buses above; nets cross between rows
  on vertical Metal3 tracks. The A-side nets (vinp, np, ln, lnb, doutb) have
  their tracks in the left channel and the B-side nets mirrored in the right
  one; in the four matched rows every bus spans the same full row width, so A
  and B buses have equal length. The residual asymmetry is that A and B
  occupy different bus *levels* (0.70 um apart), so their M1 straps/stubs
  differ in length by 0.70 um per finger -- stated, not hidden.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass, field

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

import common_sg13g2 as c  # noqa: E402

TOP_CELL = "comparator"
OUT_GDS = HERE / "comparator.gds"
NETLIST = REPO / "design" / "comparator.spice"

#: The subcircuit's ports, in the schematic's own order.
PORTS = ["vinp", "vinn", "clk", "vbias", "dout", "doutb", "vdd", "vss"]

#: Body net per flavour: NMOS bodies are the substrate, tied to vss by the
#: p-tap bars; PMOS bodies are the one NWell, tied to vdd by the n-tap bars.
BODY = {"nmos": "vss", "pmos": "vdd"}

ISL_GAP = 0.40  # Activ gap between neighbouring islands (>= Act.b 0.21)
ROW_GAP = 0.80  # clear gap between row/tap extents
WELL_GAP = 2.00  # clear gap from a p-tap to the n-tap across a well edge
TAP_H = 0.50  # tap-bar Activ height
TRACK_W = 0.40
TRACK_PITCH = 0.90
RAIL_W = 1.20
CHANNEL_MARGIN = 1.20  # row edge -> first channel track
EDGE_MARGIN = 1.00  # outermost geometry -> block edge (pins end here)


# --------------------------------------------------------------------------- #
# Device description
# --------------------------------------------------------------------------- #
@dataclass
class Island:
    """One Activ island: ``len(gates)`` fingers between ``len(cols)`` source/
    drain columns. ``devs[i]`` is the schematic instance finger ``i`` belongs
    to. Columns whose net is not routed in the row (series-stack internal
    nodes) are drawn as plain shared diffusion with no contact."""

    cols: list[str]
    gates: list[str]
    devs: list[str]
    w: float
    l: float

    def __post_init__(self) -> None:
        assert len(self.cols) == len(self.gates) + 1 == len(self.devs) + 1

    @property
    def width(self) -> float:
        return len(self.cols) * c.SD_W_UM + len(self.gates) * self.l


def unit(dev: str, s: str, d: str, g: str, w: float, l: float) -> Island:
    """The matched unit cell: two fingers sharing a central drain."""
    return Island([s, d, s], [g, g], [dev, dev], w, l)


@dataclass
class Row:
    name: str
    flavour: str  # "nmos" | "pmos"
    islands: list[Island]
    gate_levels: list[list[str]]  # level k -> nets sharing that bus level
    sd_levels: list[list[str]]
    matched: bool = False  # full-span buses + end dummies
    centre_gap: float = ISL_GAP  # gap between the two middle islands
    # filled by place():
    y0: float = 0.0
    x_islands: list[float] = field(default_factory=list)

    def gap_after(self, i: int) -> float:
        n = len(self.islands)
        return self.centre_gap if (n % 2 == 0 and i == n // 2 - 1) else ISL_GAP

    @property
    def total_width(self) -> float:
        return sum(i.width for i in self.islands) + sum(
            self.gap_after(i) for i in range(len(self.islands) - 1))

    @property
    def w_max(self) -> float:
        return max(i.w for i in self.islands)

    def gate_level(self, net: str) -> int:
        return next(k for k, nets in enumerate(self.gate_levels) if net in nets)

    def sd_level(self, net: str) -> int | None:
        for k, nets in enumerate(self.sd_levels):
            if net in nets:
                return k
        return None

    # local y coordinates (Activ bottom = 0)
    def gate_bus_y(self, k: int) -> float:
        return -(c.GATE_CONT_DY + c.GATE_BUS0_DY + k * c.BUS_PITCH_UM)

    def sd_bus_y(self, k: int) -> float:
        return self.w_max + c.SD_BUS0_DY + k * c.BUS_PITCH_UM

    @property
    def bottom(self) -> float:
        return self.gate_bus_y(len(self.gate_levels) - 1) - c.PAD_UM / 2

    @property
    def top(self) -> float:
        return self.sd_bus_y(len(self.sd_levels) - 1) + c.PAD_UM / 2


def rows() -> list[Row]:
    """The device table, row by row. This is the single source of what is
    drawn; ``check_against_netlist`` reconciles it with the schematic."""
    U = unit
    return [
        Row("R_T", "nmos",
            [Island(["vss", "tmid"] * 4 + ["vss"], ["vbias"] * 8, ["MT"] * 8, 5.0, 0.5)],
            gate_levels=[["vbias"]], sd_levels=[["tmid"], ["vss"]]),
        Row("R_SW", "nmos",
            [Island(["tmid", "tail"] * 4 + ["tmid"], ["clk"] * 8, ["MSW"] * 8, 5.0, 0.13)],
            gate_levels=[["clk"]], sd_levels=[["tmid"], ["tail"]]),
        Row("R_IN", "nmos",
            [U("M1", "tail", "np", "vinp", 3.0, 0.34), U("M2", "tail", "nn", "vinn", 3.0, 0.34),
             U("M2", "tail", "nn", "vinn", 3.0, 0.34), U("M1", "tail", "np", "vinp", 3.0, 0.34)],
            gate_levels=[["vinp"], ["vinn"]], sd_levels=[["tail"], ["np"], ["nn"]],
            matched=True),
        Row("R_LN", "nmos",
            [U("M3", "np", "ln", "lp", 0.75, 0.13), U("M4", "nn", "lp", "ln", 0.75, 0.13),
             U("M4", "nn", "lp", "ln", 0.75, 0.13), U("M3", "np", "ln", "lp", 0.75, 0.13)],
            gate_levels=[["lp"], ["ln"]], sd_levels=[["np"], ["nn"], ["ln"], ["lp"]],
            matched=True),
        Row("R_LP", "pmos",
            [U("M5", "vdd", "ln", "lp", 0.75, 0.13), U("M6", "vdd", "lp", "ln", 0.75, 0.13),
             U("M6", "vdd", "lp", "ln", 0.75, 0.13), U("M5", "vdd", "ln", "lp", 0.75, 0.13)],
            gate_levels=[["lp"], ["ln"]], sd_levels=[["vdd"], ["ln"], ["lp"]],
            matched=True),
        Row("R_RST", "pmos",
            [U("M9", "vdd", "np", "clk", 1.5, 0.13), U("M7", "vdd", "ln", "clk", 1.5, 0.13),
             U("M8", "vdd", "lp", "clk", 1.5, 0.13), U("M8", "vdd", "lp", "clk", 1.5, 0.13),
             U("M7", "vdd", "ln", "clk", 1.5, 0.13), U("M10", "vdd", "nn", "clk", 1.5, 0.13)],
            gate_levels=[["clk"]], sd_levels=[["vdd"], ["np"], ["nn"], ["ln"], ["lp"]],
            matched=True),
        Row("R_OP", "pmos",
            [Island(["doutb", "na", "vdd"], ["dout", "lnb"], ["MNAP2", "MNAP1"], 4.0, 0.13),
             Island(["vdd", "lnb"], ["ln"], ["MIAP"], 3.0, 0.13),
             Island(["lpb", "vdd"], ["lp"], ["MIBP"], 3.0, 0.13),
             Island(["vdd", "nb", "dout"], ["lpb", "doutb"], ["MNBP1", "MNBP2"], 4.0, 0.13)],
            gate_levels=[["ln", "lp"], ["lnb", "lpb"], ["dout"], ["doutb"]],
            sd_levels=[["vdd"], ["lnb", "lpb"], ["doutb", "dout"]], centre_gap=1.0),
        Row("R_ON", "nmos",
            [Island(["vss", "doutb", "vss", "lnb"], ["dout", "lnb", "ln"],
                    ["MNAN2", "MNAN1", "MIAN"], 1.5, 0.13),
             Island(["lpb", "vss", "dout", "vss"], ["lp", "lpb", "doutb"],
                    ["MIBN", "MNBN1", "MNBN2"], 1.5, 0.13)],
            gate_levels=[["ln", "lp"], ["lnb", "lpb"], ["dout"], ["doutb"]],
            sd_levels=[["vss"], ["lnb", "lpb"], ["doutb", "dout"]], centre_gap=1.0),
    ]


#: Stack order, bottom to top. "ptap"/"ntap" are tap bars; "|" marks an
#: NWell edge (the band between the two marks is one NWell on vdd).
STACK = ["ptap", "R_T", "R_SW", "ptap", "R_IN", "R_LN", "ptap",
         "|", "ntap", "R_LP", "R_RST", "R_OP", "ntap", "|",
         "ptap", "R_ON", "ptap"]

#: Matched pairs (A, B) and the placement rule each one follows.
MATCHED_PAIRS = [("M1", "M2", "common-centroid ABBA"),
                 ("M3", "M4", "common-centroid ABBA"),
                 ("M5", "M6", "common-centroid ABBA"),
                 ("M7", "M8", "common-centroid ABBA"),
                 ("M9", "M10", "mirror-symmetric")]

#: Track channels. Index 0 is nearest the rows. A-side nets left, their
#: B-side mirror images right; clk is duplicated on both sides.
LEFT = ["vinp", "np", "ln", "lnb", "doutb", "clk"]
RIGHT = ["vinn", "nn", "lp", "lpb", "dout", "clk"]
CENTRE = ["vbias", "tmid", "tail"]  # share x = 0 in disjoint y spans

#: Ports: (net, edge, which track carries the pin: "L"/"R"/"C").
PIN_PLAN = [("vinp", "bottom", "L"), ("vinn", "bottom", "R"), ("vbias", "bottom", "C"),
            ("vss", "bottom", "L"), ("clk", "top", "L"), ("doutb", "top", "L"),
            ("dout", "top", "R"), ("vdd", "top", "L")]


# --------------------------------------------------------------------------- #
# Self-check against the schematic
# --------------------------------------------------------------------------- #
def read_reference(netlist: pathlib.Path = NETLIST) -> tuple[list[str], dict[str, dict]]:
    """Parse ``.subckt comparator`` out of design/comparator.spice."""
    text = netlist.read_text().splitlines()
    ports: list[str] = []
    devices: dict[str, dict] = {}
    inside = False
    for line in text:
        tok = line.split()
        if not tok or tok[0].startswith("*"):
            continue
        if tok[0].lower() == ".subckt" and tok[1] == "comparator":
            inside, ports = True, tok[2:]
            continue
        if inside and tok[0].lower() == ".ends":
            break
        if inside and tok[0][0] in "Xx":
            params = dict(p.split("=") for p in tok[6:])
            devices[tok[0][1:]] = {
                "d": tok[1], "g": tok[2], "s": tok[3], "b": tok[4], "model": tok[5],
                "w": _um(params["w"]), "l": _um(params["l"]),
                "ng": int(params.get("ng", 1)), "m": int(params.get("m", 1)),
            }
    if not devices:
        raise SystemExit(f"no `.subckt comparator` devices found in {netlist.name}")
    return ports, devices


def _um(value: str) -> float:
    m = re.fullmatch(r"([0-9.eE+-]+)u", value)
    if not m:
        raise ValueError(f"unexpected dimension {value!r}")
    return float(m.group(1))


def drawn_inventory(table: list[Row]) -> dict[str, dict]:
    inv: dict[str, dict] = {}
    for row in table:
        for isl in row.islands:
            for i, dev in enumerate(isl.devs):
                rec = inv.setdefault(dev, {
                    "flavour": row.flavour, "body": BODY[row.flavour], "gates": set(),
                    "sd": set(), "w": 0.0, "l": set(), "fingers": 0, "row": row.name,
                    "finger_w": set()})
                rec["gates"].add(isl.gates[i])
                rec["sd"].add(frozenset((isl.cols[i], isl.cols[i + 1])))
                rec["w"] += isl.w
                rec["l"].add(isl.l)
                rec["finger_w"].add(isl.w)
                rec["fingers"] += 1
    return inv


def check_against_netlist(table: list[Row], netlist: pathlib.Path = NETLIST) -> list[str]:
    ports, ref = read_reference(netlist)
    inv = drawn_inventory(table)
    errors: list[str] = []
    if ports != PORTS:
        errors.append(f"pin list {PORTS} != schematic {ports}")
    if sorted({p for p, _, _ in PIN_PLAN}) != sorted(ports):
        errors.append("PIN_PLAN does not cover exactly the schematic ports")
    missing, extra = sorted(set(ref) - set(inv)), sorted(set(inv) - set(ref))
    if missing:
        errors.append(f"devices in the schematic but not drawn: {missing}")
    if extra:
        errors.append(f"devices drawn but not in the schematic: {extra}")
    for name in sorted(set(ref) & set(inv)):
        r, d = ref[name], inv[name]
        want_model = f"sg13_lv_{d['flavour']}"
        if r["model"] != want_model:
            errors.append(f"{name}: drawn {want_model} (no ThickGateOx), schematic {r['model']}")
        if d["gates"] != {r["g"]}:
            errors.append(f"{name}: gate {sorted(d['gates'])} != {r['g']}")
        if d["sd"] != {frozenset((r["d"], r["s"]))}:
            errors.append(f"{name}: source/drain {[sorted(x) for x in d['sd']]} != {{{r['d']},{r['s']}}}")
        if d["body"] != r["b"]:
            errors.append(f"{name}: body {d['body']} != {r['b']}")
        if d["l"] != {r["l"]}:
            errors.append(f"{name}: L {sorted(d['l'])} != {r['l']}")
        if abs(d["w"] - r["w"] * r["m"]) > 1e-9:
            errors.append(f"{name}: drawn W {d['w']} != schematic {r['w']} x m={r['m']}")
    for a, b, _ in MATCHED_PAIRS:
        if a in inv and b in inv:
            da, db = inv[a], inv[b]
            for key in ("fingers", "finger_w", "l"):
                if da[key] != db[key]:
                    errors.append(f"matched pair {a}/{b}: {key} differs ({da[key]} vs {db[key]})")
    return errors


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #
class Drawing:
    def __init__(self, table: list[Row]) -> None:
        self.b = c.Builder(TOP_CELL)
        self.rows = {r.name: r for r in table}
        self.table = table
        self.finger_x: dict[str, list[tuple[float, float]]] = {}  # dev -> (x, w)
        # (net, x) -> list of y where something lands on the track
        self.taps: dict[tuple[str, float], list[float]] = {}
        half = max(r.total_width for r in table) / 2
        self.row_half = half
        x = half + CHANNEL_MARGIN
        self.track_x: dict[str, list[float]] = {n: [0.0] for n in CENTRE}
        for i, (ln, rn) in enumerate(zip(LEFT, RIGHT, strict=True)):
            xi = c.snap(x + i * TRACK_PITCH)
            self.track_x.setdefault(ln, []).append(-xi)
            self.track_x.setdefault(rn, []).append(xi)
        x_last = x + (len(LEFT) - 1) * TRACK_PITCH
        self.vss_x = c.snap(x_last + TRACK_PITCH / 2 + 0.3 + RAIL_W / 2)
        self.vdd_x = c.snap(self.vss_x + RAIL_W + 0.6)
        self.track_x["vss"] = [-self.vss_x, self.vss_x]
        self.track_x["vdd"] = [-self.vdd_x, self.vdd_x]
        self.tap_half = half + 0.5

    # -- rows -------------------------------------------------------------- #
    def draw_row(self, row: Row) -> None:
        b = self.b
        y0 = row.y0
        x = -row.total_width / 2
        gate_pts: dict[str, list[float]] = {}
        sd_pts: dict[str, list[float]] = {}
        row.x_islands = []
        for n_isl, isl in enumerate(row.islands):
            row.x_islands.append(x)
            pitch = c.SD_W_UM + isl.l
            ax0, ax1 = x, x + isl.width
            b.box(c.L_ACTIV, ax0, y0, ax1, y0 + isl.w)
            if row.flavour == "pmos":
                b.box(c.L_PSD, ax0 - c.PSD_C, y0 - c.PSD_C, ax1 + c.PSD_C, y0 + isl.w + c.PSD_C)
            # gates
            gc_y = y0 - c.GATE_CONT_DY
            head = max(isl.l, c.POLY_HEAD_UM)
            for i, g in enumerate(isl.gates):
                gx0 = x + c.SD_W_UM + i * pitch
                gxc = gx0 + isl.l / 2
                b.box(c.L_GATPOLY, gx0, gc_y, gx0 + isl.l, y0 + isl.w + c.GAT_C)
                b.box(c.L_GATPOLY, gxc - head / 2, gc_y - c.POLY_HEAD_UM / 2,
                      gxc + head / 2, gc_y + c.POLY_HEAD_UM / 2)
                b.box(c.L_CONT, gxc - c.CNT_A / 2, gc_y - c.CNT_A / 2,
                      gxc + c.CNT_A / 2, gc_y + c.CNT_A / 2)
                bus_y = y0 + row.gate_bus_y(row.gate_level(g))
                b.box(c.L_METAL1, gxc - c.STUB_W_UM / 2, bus_y - c.BUS_W_UM / 2,
                      gxc + c.STUB_W_UM / 2, gc_y + c.POLY_HEAD_UM / 2)
                c.via1(b, gxc, bus_y)
                gate_pts.setdefault(g, []).append(gxc)
                self.finger_x.setdefault(isl.devs[i], []).append((gxc, isl.w))
            # source/drain columns
            for j, net in enumerate(isl.cols):
                cx0 = x + j * pitch
                cxc = cx0 + c.SD_W_UM / 2
                k = row.sd_level(net)
                if k is None:  # internal series node: shared diffusion only
                    continue
                c.cont_array(b, cx0 + 0.17, y0 + c.CNT_C, cx0 + 0.33, y0 + isl.w - c.CNT_C)
                bus_y = y0 + row.sd_bus_y(k)
                b.box(c.L_METAL1, cxc - c.STRAP_W_UM / 2, y0, cxc + c.STRAP_W_UM / 2,
                      bus_y + c.BUS_W_UM / 2)
                c.via1(b, cxc, bus_y)
                sd_pts.setdefault(net, []).append(cxc)
            names = sorted(set(isl.devs), key=isl.devs.index)
            b.annotate(" ".join(names), (ax0 + ax1) / 2, y0 + isl.w / 2)
            x = ax1 + row.gap_after(n_isl)

        if row.matched:
            # Field-poly dummies at both row ends, where the neighbouring
            # unit's outer gate would be: every unit then sees the same
            # neighbouring-poly distance on both sides.
            l_gate = row.islands[0].l
            w = row.islands[0].w
            left = -row.total_width / 2 - ISL_GAP - c.SD_W_UM - l_gate
            right = row.total_width / 2 + ISL_GAP + c.SD_W_UM
            for dx in (left, right):
                b.box(c.L_GATPOLY, dx, y0 - c.GAT_C, dx + l_gate, y0 + w + c.GAT_C)

        # buses
        row_tracks = [x for nets in row.gate_levels + row.sd_levels
                      for n in nets for x in self.track_x[n]]
        full = (min(row_tracks), max(row_tracks))
        for side, levels, pts, ycalc in (
            ("gate", row.gate_levels, gate_pts, row.gate_bus_y),
            ("sd", row.sd_levels, sd_pts, row.sd_bus_y),
        ):
            for k, nets in enumerate(levels):
                spans = []
                for net in nets:
                    xs = pts.get(net, []) + self.track_x[net]
                    if not pts.get(net):
                        raise AssertionError(f"{row.name}: {side} net {net} has no terminal")
                    lo, hi = (full if row.matched else (min(xs), max(xs)))
                    lo, hi = lo - 0.3, hi + 0.3
                    for olo, ohi, onet in spans:
                        if lo < ohi + 0.4 and olo < hi + 0.4:
                            raise AssertionError(
                                f"{row.name}: {side} level {k} buses {net}/{onet} overlap")
                    spans.append((lo, hi, net))
                    y = y0 + ycalc(k)
                    b.box(c.L_METAL2, lo, y - c.BUS_W_UM / 2, hi, y + c.BUS_W_UM / 2)
                    for tx in self.track_x[net]:
                        c.via2(b, tx, y)
                        self.taps.setdefault((net, tx), []).append(y)

    # -- taps / well ---------------------------------------------------------- #
    def draw_tap(self, kind: str, y: float) -> None:
        b = self.b
        net = "vss" if kind == "ptap" else "vdd"
        implant = c.L_PSD if kind == "ptap" else c.L_NSD
        h = self.tap_half
        b.box(c.L_ACTIV, -h, y, h, y + TAP_H)
        b.box(implant, -h - c.PSD_C, y - c.PSD_C, h + c.PSD_C, y + TAP_H + c.PSD_C)
        c.cont_array(b, -h + c.CNT_C, y + c.CNT_C, h - c.CNT_C, y + TAP_H - c.CNT_C)
        rail = self.vss_x if net == "vss" else self.vdd_x
        yc = y + TAP_H / 2
        b.box(c.L_METAL1, -rail - c.PAD_UM / 2, yc - 0.20, rail + c.PAD_UM / 2, yc + 0.20)
        for tx in (-rail, rail):
            c.via_stack_13(b, tx, yc)
            self.taps.setdefault((net, tx), []).append(yc)

    # -- tracks ---------------------------------------------------------------- #
    def draw_tracks(self, y_bot: float, y_top: float) -> None:
        b = self.b
        pins = {(n, e, s) for n, e, s in PIN_PLAN}
        segments: dict[float, list[tuple[float, float, str]]] = {}
        for net, xs in self.track_x.items():
            for tx in xs:
                ys = self.taps.get((net, tx))
                if not ys:
                    raise AssertionError(f"track {net}@{tx} has no tap")
                lo, hi = min(ys) - 0.20, max(ys) + 0.20
                side = "C" if tx == 0 else ("L" if tx < 0 else "R")
                width = RAIL_W if net in ("vss", "vdd") else TRACK_W
                if net in ("vss", "vdd"):
                    lo, hi = y_bot, y_top
                if net == "clk":  # both clk tracks run to the top edge
                    hi = y_top
                pin_edge = None
                for n, e, s in pins:
                    if n == net and s == side:
                        pin_edge = e
                if pin_edge == "bottom":
                    lo = y_bot
                elif pin_edge == "top":
                    hi = y_top
                for olo, ohi, onet in segments.get(tx, []):
                    if lo < ohi + c.MN_B and olo < hi + c.MN_B:
                        raise AssertionError(f"track clash at x={tx}: {net} vs {onet}")
                segments.setdefault(tx, []).append((lo, hi, net))
                b.box(c.L_METAL3, tx - width / 2, lo, tx + width / 2, hi)
                b.label(net, tx, (lo + hi) / 2, level=3)
                if pin_edge:
                    pw = width - 0.10
                    if pin_edge == "bottom":
                        b.pin(net, tx - pw / 2, lo, tx + pw / 2, lo + 0.60, level=3)
                    else:
                        b.pin(net, tx - pw / 2, hi - 0.60, tx + pw / 2, hi, level=3)

    # -- top level ----------------------------------------------------------- #
    def build(self) -> c.Builder:
        y = 0.0
        prev = None
        taps: list[tuple[str, float]] = []
        for item in STACK:
            if item == "|":
                prev = "|"
                continue
            gap = WELL_GAP if prev == "|" else (ROW_GAP if prev else 0.0)
            if item in ("ptap", "ntap"):
                ty = y + gap
                taps.append((item, ty))
                y = ty + TAP_H
            else:
                row = self.rows[item]
                row.y0 = y + gap - row.bottom
                self.draw_row(row)
                y = row.y0 + row.top
            prev = item
        for kind, ty in taps:
            self.draw_tap(kind, ty)
        # The NWell: from below the first n-tap to above the last one.
        ntaps = [ty for kind, ty in taps if kind == "ntap"]
        h = self.tap_half + c.NW_ENC
        self.b.box(c.L_NWELL, -h, min(ntaps) - c.NW_ENC, h, max(ntaps) + TAP_H + c.NW_ENC)
        y_bot = -EDGE_MARGIN
        y_top = y + EDGE_MARGIN
        self.draw_tracks(y_bot, y_top)
        self.y_extent = (y_bot, y_top)
        return self.b

    def centroids(self) -> list[tuple[str, str, str, float, float]]:
        out = []
        for a, bb, rule in MATCHED_PAIRS:
            ca = sum(x * w for x, w in self.finger_x[a]) / sum(w for _, w in self.finger_x[a])
            cb = sum(x * w for x, w in self.finger_x[bb]) / sum(w for _, w in self.finger_x[bb])
            out.append((a, bb, rule, ca, cb))
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-o", "--output", type=pathlib.Path, default=OUT_GDS)
    ap.add_argument("--netlist", type=pathlib.Path, default=NETLIST,
                    help="reference netlist to reconcile against (default: "
                         "design/comparator.spice; other values are for negative controls)")
    args = ap.parse_args()

    table = rows()
    errors = check_against_netlist(table, args.netlist)
    if errors:
        print(f"generator device table disagrees with {args.netlist.name}:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    d = Drawing(table)
    b = d.build()
    shapes = c.assert_manhattan(b)
    for a, bb, rule, ca, cb in d.centroids():
        if rule.startswith("common-centroid") and abs(ca - cb) > 1e-6:
            print(f"{a}/{bb}: centroids differ ({ca:.4f} vs {cb:.4f})", file=sys.stderr)
            return 1
        if rule == "mirror-symmetric" and abs(ca + cb) > 1e-6:
            print(f"{a}/{bb}: not mirror-symmetric ({ca:.4f} vs {cb:.4f})", file=sys.stderr)
            return 1
    b.write(str(args.output))

    x0, y0, x1, y1 = b.bbox_um()
    inv = drawn_inventory(table)
    try:
        shown = args.output.resolve().relative_to(REPO)
    except ValueError:
        shown = args.output.name
    print(f"wrote {shown}")
    print(f"  top cell : {TOP_CELL}")
    print(f"  bbox     : ({x0:.3f}, {y0:.3f}) - ({x1:.3f}, {y1:.3f}) um"
          f"  [{x1 - x0:.2f} x {y1 - y0:.2f} um]")
    print(f"  shapes   : {shapes} (all axis-aligned boxes)")
    print(f"  devices  : {len(inv)} (matches design/comparator.spice .subckt comparator)")
    print(f"  pins     : {' '.join(PORTS)}")
    print("  matching :")
    for a, bb, rule, ca, cb in d.centroids():
        fa = inv[a]
        print(f"    {a:>3}/{bb:<3} {rule:<22} {fa['fingers']} x {sorted(fa['finger_w'])[0]}u"
              f" l={sorted(fa['l'])[0]}u  centroid x: {ca:+.3f} / {cb:+.3f} um")
    return 0


if __name__ == "__main__":
    sys.exit(main())

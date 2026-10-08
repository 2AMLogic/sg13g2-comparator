"""Shared ``klayout.db`` drawing primitives for this repo's SG13G2 layouts.

Written for issue #58 (T1 item 2: committed, reproducibly generated layout).
The structure follows the hand-written generator pattern used by
``2AMLogic/sg13g2-ldo`` (``layout/common_sg13cmos5l.py``), re-derived for the
SG13G2 layer table and for what a small, matched, low-voltage dynamic
comparator needs: unit-cell MOS islands, multi-level M2 buses, M3 tracks and
contacted tap bars. No PDK PCell is instantiated (see ``layout/README.md``,
"What this layout is, and is not").

Conventions
-----------

* **Micron in, database-unit out.** ``dbu = 0.001`` (1 nm), snapped to the
  SG13G2 5 nm manufacturing grid on the way in.
* **Axis-aligned boxes only.** Every shape is a ``kdb.Box``;
  ``assert_manhattan`` checks that from the database.
* **Net names are texts on the ``.text`` (datatype 25) metal layers**, which
  is what klt's curated ``sg13g2`` extraction deck reads
  (``EXTRACTION_DECK.metal_labels == ((8,25),(10,25),(30,25),...)``). Ports
  additionally get a box on the ``.pin`` (datatype 2) layer, drawn strictly
  inside the metal it marks.
* **Deterministic output.** Shapes are inserted in a fixed order and the GDS is
  written with ``gds2_write_timestamps = False``, so the stream is a function
  of the source and the pinned KLayout writer only.
"""

from __future__ import annotations

import klayout.db as kdb

# --------------------------------------------------------------------------- #
# Layer table (IHP SG13G2 ``sg13g2.lyp`` numbering; the drawing/label pairs
# below are the ones klt's curated ``sg13g2`` deck declares in its
# ``EXTRACTION_DECK`` and DRC table -- Activ 1/0, GatPoly 5/0, Cont 6/0,
# nSD 7/0, pSD 14/0, NWell 31/0, Metal1..3 8/0, 10/0, 30/0, Via1 19/0,
# Via2 29/0, Metal<n>.text <n>/25).
# --------------------------------------------------------------------------- #
L_ACTIV = (1, 0)
L_GATPOLY = (5, 0)
L_CONT = (6, 0)
L_NSD = (7, 0)
L_METAL1 = (8, 0)
L_METAL1_PIN = (8, 2)
L_METAL1_TEXT = (8, 25)
L_METAL2 = (10, 0)
L_METAL2_PIN = (10, 2)
L_METAL2_TEXT = (10, 25)
L_PSD = (14, 0)
L_VIA1 = (19, 0)
L_VIA2 = (29, 0)
L_METAL3 = (30, 0)
L_METAL3_PIN = (30, 2)
L_METAL3_TEXT = (30, 25)
L_NWELL = (31, 0)
L_TEXT = (63, 0)

LAYER_NAMES: dict[tuple[int, int], str] = {
    L_ACTIV: "Activ.drawing",
    L_GATPOLY: "GatPoly.drawing",
    L_CONT: "Cont.drawing",
    L_NSD: "nSD.drawing",
    L_METAL1: "Metal1.drawing",
    L_METAL1_PIN: "Metal1.pin",
    L_METAL1_TEXT: "Metal1.text",
    L_METAL2: "Metal2.drawing",
    L_METAL2_PIN: "Metal2.pin",
    L_METAL2_TEXT: "Metal2.text",
    L_PSD: "pSD.drawing",
    L_VIA1: "Via1.drawing",
    L_VIA2: "Via2.drawing",
    L_METAL3: "Metal3.drawing",
    L_METAL3_PIN: "Metal3.pin",
    L_METAL3_TEXT: "Metal3.text",
    L_NWELL: "NWell.drawing",
    L_TEXT: "TEXT.drawing",
}

#: Metal level -> (drawing, pin, text) layers.
METAL_STACK: dict[int, tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = {
    1: (L_METAL1, L_METAL1_PIN, L_METAL1_TEXT),
    2: (L_METAL2, L_METAL2_PIN, L_METAL2_TEXT),
    3: (L_METAL3, L_METAL3_PIN, L_METAL3_TEXT),
}

# --------------------------------------------------------------------------- #
# Rule values.
#
# "deck" = the value klt's curated sg13g2 DRC deck enforces (read from the
# pinned klt build's ``decks/sg13g2.py`` DECK table). "rules" = an IHP SG13G2
# layout-rule value the curated deck does not check; those are drawn with
# margin and are re-checked by the PDK's own deck under issue #59, not here.
# --------------------------------------------------------------------------- #
GRID_UM = 0.005

ACT_A = 0.15  # deck: Activ min width
ACT_B = 0.21  # deck: Activ min space
GAT_A = 0.13  # deck: GatPoly min width
GAT_B = 0.18  # deck: GatPoly min space
GAT_C = 0.18  # rules Gat.c: GatPoly endcap past Activ
GAT_D = 0.07  # deck: GatPoly space to Activ
CNT_A = 0.16  # deck: Cont size (min and max)
CNT_B = 0.18  # deck: Cont space
CNT_C = 0.07  # deck: Activ enclosure of Cont
CNT_D = 0.07  # deck: GatPoly enclosure of Cont
CNT_E = 0.14  # rules Cnt.e: Cont-on-GatPoly space to Activ
CNT_F = 0.11  # rules Cnt.f: Cont-on-Activ space to GatPoly
M1_A = 0.16  # deck: Metal1 min width
M1_B = 0.18  # deck: Metal1 min space
V1_A = 0.19  # deck: Via1 size (min and max)
V1_B = 0.22  # deck: Via1 space
VN_A = 0.19  # deck: Via2 size (min and max)
MN_A = 0.20  # deck: Metal2/Metal3 min width
MN_B = 0.21  # deck: Metal2/Metal3 min space
PSD_C = 0.18  # rules pSD.c: pSD (and here also nSD) enclosure of Activ
NW_ENC = 0.62  # NWell enclosure of P+ Activ / N+ tap: drawn at the
#               thick-oxide value (NW.c1) as margin over the LV value
CONT_PITCH = CNT_A + CNT_B

#: Source/drain column width. Holds one contact column with
#: (0.50 - 0.16) / 2 = 0.17 um to each neighbouring gate (>= Cnt.f 0.11).
SD_W_UM = 0.50
#: Metal1 strap width on a source/drain column (encloses the 0.16 um contact
#: and a 0.19 um Via1 by 0.085 um; leaves >= 0.27 um to the next strap at the
#: tightest 0.63 um column pitch).
STRAP_W_UM = 0.36
#: Gate-contact poly head (Cont + 2 x Cnt.d).
POLY_HEAD_UM = CNT_A + 2 * CNT_D
#: Gate contact centre, below the Activ bottom edge. Contact top is then
#: 0.47 um from the Activ (>= Cnt.e 0.14) and the head 0.40 um (>= Gat.c).
GATE_CONT_DY = 0.55
#: Bus (M2) width and level pitch, gate side and source/drain side.
BUS_W_UM = 0.30
BUS_PITCH_UM = 0.70
#: First gate bus below the gate contact, first S/D bus above the Activ top.
GATE_BUS0_DY = 0.65
SD_BUS0_DY = 0.55
#: M1 stub width from a gate contact down to its bus.
STUB_W_UM = 0.30
#: Via landing pad (M1 / M2) used in via stacks.
PAD_UM = 0.40


def snap(value_um: float) -> float:
    """Snap a micron coordinate to the 5 nm grid."""
    return round(round(value_um / GRID_UM) * GRID_UM, 6)


class Builder:
    """A ``kdb.Layout`` + one flat top cell + layer map, with primitives."""

    def __init__(self, top_cell: str, dbu: float = 0.001) -> None:
        self.layout = kdb.Layout()
        self.layout.dbu = dbu
        self.cell = self.layout.create_cell(top_cell)
        self._layers: dict[tuple[int, int], int] = {}
        for (layer, datatype), name in LAYER_NAMES.items():
            info = kdb.LayerInfo(layer, datatype, name)
            self._layers[(layer, datatype)] = self.layout.layer(info)

    def _u(self, value_um: float) -> int:
        return int(round(snap(value_um) / self.layout.dbu))

    def box(
        self, layer: tuple[int, int], x0: float, y0: float, x1: float, y1: float
    ) -> tuple[float, float, float, float]:
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        self.cell.shapes(self._layers[layer]).insert(
            kdb.Box(self._u(x0), self._u(y0), self._u(x1), self._u(y1))
        )
        return (snap(x0), snap(y0), snap(x1), snap(y1))

    def text(self, layer: tuple[int, int], s: str, x: float, y: float) -> None:
        self.cell.shapes(self._layers[layer]).insert(
            kdb.Text(s, self._u(x), self._u(y))
        )

    def label(self, net: str, x: float, y: float, level: int) -> None:
        """Name a net: a text on that metal level's ``.text`` layer. Must sit
        on a drawn shape of the same level."""
        self.text(METAL_STACK[level][2], net, x, y)

    def pin(self, net: str, x0: float, y0: float, x1: float, y1: float, level: int) -> None:
        """A port: ``.pin`` box (inside drawn metal) plus the net-name text."""
        self.box(METAL_STACK[level][1], x0, y0, x1, y1)
        self.label(net, (x0 + x1) / 2, (y0 + y1) / 2, level)

    def annotate(self, s: str, x: float, y: float) -> None:
        """Human-readable annotation on TEXT.drawing (read by no check)."""
        self.text(L_TEXT, s, x, y)

    def write(self, path: str) -> None:
        """Write the GDS reproducibly (no BGNLIB/BGNSTR wall-clock stamps)."""
        options = kdb.SaveLayoutOptions()
        options.format = "GDS2"
        options.gds2_write_timestamps = False
        self.layout.write(path, options)

    def bbox_um(self) -> tuple[float, float, float, float]:
        b = self.cell.bbox()
        d = self.layout.dbu
        return (b.left * d, b.bottom * d, b.right * d, b.top * d)


def cont_array(b: Builder, x0: float, y0: float, x1: float, y1: float) -> int:
    """Fill a box with Cnt.a contacts on a Cnt.a + Cnt.b pitch, centred."""
    span_x, span_y = x1 - x0, y1 - y0
    nx = int((span_x + CNT_B + 1e-9) // CONT_PITCH)
    ny = int((span_y + CNT_B + 1e-9) // CONT_PITCH)
    if nx < 1 or ny < 1:
        raise AssertionError(f"no room for a contact in {x0, y0, x1, y1}")
    ox = x0 + (span_x - (nx * CONT_PITCH - CNT_B)) / 2
    oy = y0 + (span_y - (ny * CONT_PITCH - CNT_B)) / 2
    for i in range(nx):
        for j in range(ny):
            cx, cy = ox + i * CONT_PITCH, oy + j * CONT_PITCH
            b.box(L_CONT, cx, cy, cx + CNT_A, cy + CNT_A)
    return nx * ny


def via1(b: Builder, x: float, y: float) -> None:
    b.box(L_VIA1, x - V1_A / 2, y - V1_A / 2, x + V1_A / 2, y + V1_A / 2)


def via2(b: Builder, x: float, y: float) -> None:
    b.box(L_VIA2, x - VN_A / 2, y - VN_A / 2, x + VN_A / 2, y + VN_A / 2)


def via_stack_13(b: Builder, x: float, y: float) -> None:
    """Metal1 -> Metal3 at one point: M1 pad, Via1, M2 pad, Via2 (the M3
    landing is the caller's track)."""
    h = PAD_UM / 2
    b.box(L_METAL1, x - h, y - h, x + h, y + h)
    via1(b, x, y)
    b.box(L_METAL2, x - h, y - h, x + h, y + h)
    via2(b, x, y)


def assert_manhattan(b: Builder) -> int:
    """Every non-text shape is an axis-aligned box; returns the shape count."""
    count = 0
    for layer_index in b.layout.layer_indexes():
        for shape in b.cell.shapes(layer_index).each():
            if shape.is_text():
                continue
            if not shape.is_box():
                raise AssertionError(f"non-box shape on layer {layer_index}: {shape}")
            count += 1
    return count

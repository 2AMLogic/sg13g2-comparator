"""Process / voltage / temperature corner definitions for IHP SG13G2.

Ported from ``2AMLogic/gf180-comparator``'s ``sim/harness/corners.py``
(itself ported from ``2AMLogic/gf180-sar-adc``): the ``<process>_<temp>c_
<supply>v`` corner-id convention, the ``sabotage()`` negative control, the
per-family ``.lib``-bundle structure, and the -40/27/125 degC x supply-
tolerance axes. See ``sim/harness/README.md``'s divergence table for the
full list of what changed and why.

ADAPTED FOR SG13G2, structurally:

- gf180mcu has no single global process switch -- every device family
  (MOS/BJT/diode/resistor/...) carries its own ``.lib`` section, and a named
  corner there is a bundle of one section per family. **SG13G2's
  ``cornerMOSlv.lib`` already IS that global switch for the one family this
  block's placeholder DUT instantiates** (LV MOS): ``mos_tt`` / ``mos_ff`` /
  ``mos_ss`` / ``mos_fs`` / ``mos_sf``, each a single self-contained ``.LIB``
  block. So ``FAMILIES`` here has exactly one entry, ``mos`` -- not because
  other families were dropped as dead weight (gf180-comparator's rationale
  for dropping capacitor corners), but because this PDK does not need a
  multi-family bundle to define a process corner at all.
- **The placeholder DUT's load is an IDEAL resistor (a plain SPICE ``R``
  element), not a PDK resistor subckt** (``sim/dut/placeholder_comparator.spice``
  header states why). SG13G2's ``cornerRES.lib`` (``res_typ``/``res_bcs``/
  ``res_wcs``, each with its own real per-instance mismatch model -- see
  below) is therefore NOT bundled into any corner here. The day a real
  design binds a PDK resistor (``rsil``/``rhigh``/``rppd``), this is the
  file to add a ``res`` family and a resistor-dominated corner pair to,
  mirroring gf180-comparator's ``res_ff``/``res_ss`` promotion -- tracked as
  a named extension point, not silently deferred.
- **SG13G2 has no gf180mcu-style global ``sw_stat_mismatch`` switch at all.**
  Local mismatch is a property of which ``.LIB`` section is loaded:
  ``mos_tt_mismatch`` (etc.) ``.include``s the PDK's ``sg13g2_moslv_mod_
  mismatch.lib``, whose ``sg13_lv_nmos``/``sg13_lv_pmos`` subckts carry
  ``agauss()``-bound ``delvto``/``factuo``/``w``/``l`` terms gated by a
  per-instance ``mm_ok`` parameter (default 1) -- confirmed against the
  installed checkout during issue #6 (``sim/device-mismatch-confirm/
  README.md``). So this module defines a SECOND corner set,
  ``mos_mismatch`` (``tt_mismatch``/``ff_mismatch``/``ss_mismatch``/
  ``fs_mismatch``/``sf_mismatch``), which is both a process-corner sweep AND
  the offset-MC bench's Monte-Carlo switch at once -- there is no equivalent
  of gf180-comparator's ``.param sw_stat_mismatch=1`` fragment line here,
  because there is nothing for a fragment to set.
- ``sabotage()`` forces every corner to the plain ``mos_tt`` section
  (mismatch OFF). For the ordinary corner set this is the usual "prove the
  process axis moves" negative control; for the offset-MC bench, which runs
  the ``mismatch`` corner set, sabotage ALSO switches mismatch off --
  collapsing the reported offset sigma toward zero, which is exactly the
  same "sigma = 0 while everything looks like it ran" trap this PDK's own
  mismatch mechanism can fall into (see ``sim/harness/README.md``), caught
  by the same ``av_sigma_pct``/``sig_vos_mv`` guard gf180-comparator ported.
- **Voltage axis**: 1.2 V +/-10% (1.08 / 1.20 / 1.32 V) -- SG13G2's LV rail
  (``README.md`` Supply row) -- not gf180mcu's 3.3 V-class rail.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

# Default PVT axes. CLAUDE.md mandates PVT corners on every recorded result.
DEFAULT_TEMPERATURES_C: tuple[float, ...] = (-40.0, 27.0, 125.0)
DEFAULT_SUPPLY_TOLERANCE: float = 0.10  # +/-10 %, per README.md's supply row
DEFAULT_NOMINAL_SUPPLY_V: float = 1.2   # SG13G2 LV rail (CLAUDE.md)


@dataclass(frozen=True)
class Corner:
    """A named process corner: the single ``cornerMOSlv.lib`` ``.LIB`` section it loads."""

    name: str
    section: str
    description: str = ""

    @property
    def sections(self) -> tuple[str, ...]:
        """Kept plural (and a tuple) for symmetry with the gf180-comparator API
        shape -- ``runner.py`` iterates ``point.corner.sections`` regardless of
        how many families a given PDK's harness bundles."""
        return (self.section,)


CORNERS: dict[str, Corner] = {
    "tt": Corner("tt", "mos_tt", "typical, mismatch OFF"),
    "ff": Corner("ff", "mos_ff", "fast NMOS/PMOS, mismatch OFF"),
    "ss": Corner("ss", "mos_ss", "slow NMOS/PMOS, mismatch OFF"),
    "fs": Corner("fs", "mos_fs", "fast NMOS / slow PMOS, mismatch OFF"),
    "sf": Corner("sf", "mos_sf", "slow NMOS / fast PMOS, mismatch OFF"),
    # Mismatch corners: SAME five process points, but each section also
    # ``.include``s the PDK's per-instance local-mismatch model (mm_ok=1
    # default) -- see this module's docstring. Used by comparator-offset-mc
    # ONLY; every other bench runs mismatch-free by convention (offset and
    # regeneration/noise/kickback are separable effects, budgeted
    # separately -- see each bench's tb.json ``evidence`` block).
    "tt_mismatch": Corner("tt_mismatch", "mos_tt_mismatch", "typical, mismatch ON"),
    "ff_mismatch": Corner("ff_mismatch", "mos_ff_mismatch", "fast NMOS/PMOS, mismatch ON"),
    "ss_mismatch": Corner("ss_mismatch", "mos_ss_mismatch", "slow NMOS/PMOS, mismatch ON"),
    "fs_mismatch": Corner("fs_mismatch", "mos_fs_mismatch", "fast NMOS / slow PMOS, mismatch ON"),
    "sf_mismatch": Corner("sf_mismatch", "mos_sf_mismatch", "slow NMOS / fast PMOS, mismatch ON"),
}

CORNER_SETS: dict[str, tuple[str, ...]] = {
    # Minimum bar for a quick smoke run. NOT a valid evidence matrix on its own.
    "tt": ("tt",),
    # The five classic MOS corners, mismatch off -- the default for every
    # bench except comparator-offset-mc.
    "mos": ("tt", "ff", "ss", "fs", "sf"),
    # Same five points, mismatch on -- comparator-offset-mc's corner set.
    "mos_mismatch": (
        "tt_mismatch", "ff_mismatch", "ss_mismatch", "fs_mismatch", "sf_mismatch",
    ),
}
DEFAULT_CORNER_SET = "mos"


def resolve_corners(names: list[str] | tuple[str, ...] | None) -> list[Corner]:
    """Turn a list of corner *or* corner-set names into Corner objects."""
    if not names:
        names = [DEFAULT_CORNER_SET]
    resolved: list[Corner] = []
    seen: set[str] = set()
    for name in names:
        expanded = CORNER_SETS.get(name, (name,))
        for corner_name in expanded:
            if corner_name in seen:
                continue
            if corner_name not in CORNERS:
                raise KeyError(
                    f"unknown corner {corner_name!r}; "
                    f"known corners: {', '.join(sorted(CORNERS))}; "
                    f"known sets: {', '.join(sorted(CORNER_SETS))}"
                )
            seen.add(corner_name)
            resolved.append(CORNERS[corner_name])
    return resolved


def sabotage(corner_list: list[Corner]) -> list[Corner]:
    """Return the same corner *names* with every section forced to plain ``mos_tt``.

    This is the harness's **negative control**, not a feature: it reproduces
    the exact silent failure mode this repo is most exposed to -- a runner
    that appears to sweep process corners (and, for comparator-offset-mc,
    mismatch draws) but actually simulates typical-and-mismatch-free
    everywhere (wrong ``.lib`` section, ignored parameter, wrong corner
    name). ``sim/selftest.sh`` runs a testbench once normally and once
    sabotaged; the sabotaged run **must fail** its per-axis sensitivity (and,
    for offset-MC, its mismatch-on guard) checks. If it passes, corner
    switching is not taking effect and every downstream evidence record is
    worthless. The CLI forces ``--no-write`` whenever this is used, so a
    sabotaged run can never enter ``sim/`` as evidence.
    """
    return [
        Corner(name=corner.name, section="mos_tt", description=f"SABOTAGED ({corner.description})")
        for corner in corner_list
    ]


def _finite_number(value, where: str) -> float:
    """Return ``value`` as a float, rejecting bool / str / None / NaN / Inf /
    ints too large for a float, with a field-specific message."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be a finite number, got {value!r}")
    try:
        result = float(value)
    except OverflowError:
        raise ValueError(f"{where} must be finite, got {value!r}") from None
    if not math.isfinite(result):
        raise ValueError(f"{where} must be finite, got {value!r}")
    return result


def validate_supply_params(nominal_v, tolerance) -> tuple[float, float]:
    """Validate nominal supply (finite, > 0) and tolerance (finite, >= 0).

    A tolerance of exactly 0 is a deliberate nominal-only sweep; a tolerance
    >= 1 would generate a zero or negative low rail and is rejected.
    """
    nominal = _finite_number(nominal_v, "nominal_supply_v")
    if nominal <= 0:
        raise ValueError(f"nominal_supply_v must be > 0, got {nominal_v!r}")
    tol = _finite_number(tolerance, "supply_tolerance")
    if tol < 0:
        raise ValueError(f"supply_tolerance must be >= 0, got {tolerance!r}")
    if tol >= 1:
        raise ValueError(
            f"supply_tolerance must be < 1 (a tolerance of {tolerance!r} gives a "
            "zero or negative supply rail)"
        )
    return nominal, tol


def validate_temperatures(temperatures, where: str = "temperatures_c") -> list[float]:
    """Validate a nonempty sequence of finite temperatures (any finite value)."""
    if isinstance(temperatures, (str, bytes)) or not hasattr(temperatures, "__iter__"):
        raise ValueError(f"{where} must be a list of numbers, got {temperatures!r}")
    values = [_finite_number(t, f"{where}[{i}]") for i, t in enumerate(temperatures)]
    if not values:
        raise ValueError(f"{where} must not be empty")
    return values


def supply_points(
    nominal_v: float = DEFAULT_NOMINAL_SUPPLY_V,
    tolerance: float = DEFAULT_SUPPLY_TOLERANCE,
) -> list[float]:
    """Nominal supply and its +/- tolerance rails, low to high."""
    nominal_v, tolerance = validate_supply_params(nominal_v, tolerance)
    if tolerance == 0:
        points = [round(nominal_v, 6)]
    else:
        points = [
            round(nominal_v * (1.0 - tolerance), 6),
            round(nominal_v, 6),
            round(nominal_v * (1.0 + tolerance), 6),
        ]
    for v in points:
        if not math.isfinite(v) or v <= 0:
            raise ValueError(
                f"supply rails {points!r} must be finite and > 0 "
                f"(nominal_supply_v={nominal_v!r}, supply_tolerance={tolerance!r})"
            )
    return points


@dataclass(frozen=True)
class PvtPoint:
    """One point in the PVT grid -- exactly one ngspice invocation."""

    corner: Corner
    temp_c: float
    vdd: float
    index: int = field(default=0, compare=False)

    @property
    def corner_id(self) -> str:
        """The ``<process>_<temp>c_<supply>v`` id from ``sim/README.md``.

        This is the ratified corner naming for evidence records: the raw log
        for this point is ``corners/<record-id>/<corner-id>.log`` (e.g.
        ``ss_-40c_1.08v.log``, ``tt_27c_1.20v.log``).
        """
        return f"{self.corner.name}_{self.temp_c:g}c_{self.vdd:.2f}v"

    def as_dict(self) -> dict:
        return {
            "corner": self.corner.name,
            "corner_sections": list(self.corner.sections),
            "temp_c": self.temp_c,
            "vdd": self.vdd,
            "corner_id": self.corner_id,
        }


class CornerIdCollisionError(ValueError):
    """Raised when two or more distinct PVT points format to the same ``corner_id``.

    ``corner_id`` renders ``temp_c`` with ``:g`` and ``vdd`` with ``:.2f``
    (see ``PvtPoint.corner_id``), so a non-default ``--temps``/
    ``--supply-tolerance`` can produce distinct ``(corner, temp_c, vdd)``
    tuples that nonetheless render identically -- e.g. ``--supply-tolerance
    0.001`` on the 1.2 V nominal yields 1.1988/1.2/1.2012 V, all of which
    round to ``1.20`` under ``:.2f``. A silently-collapsed grid drops points
    without warning and later evidence records overwrite each other's log
    files under the same ``corner_id``, so this must fail loudly instead.
    """


def build_grid(
    corners: list[Corner],
    temperatures: list[float] | tuple[float, ...],
    supplies: list[float],
) -> list[PvtPoint]:
    """Full factorial P x V x T grid, in a stable, reproducible order.

    Raises:
        CornerIdCollisionError: if two or more of the constructed points
            share a ``corner_id`` (see that class's docstring for why this
            can happen and why it must be a loud, immediate error).
    """
    if not corners:
        raise ValueError("corners must not be empty")
    temperatures = validate_temperatures(temperatures)
    if isinstance(supplies, (str, bytes)) or not hasattr(supplies, "__iter__"):
        raise ValueError(f"supplies must be a list of numbers, got {supplies!r}")
    supplies = [_finite_number(v, f"supplies[{i}]") for i, v in enumerate(supplies)]
    if not supplies:
        raise ValueError("supplies must not be empty")
    for i, v in enumerate(supplies):
        if v <= 0:
            raise ValueError(f"supplies[{i}] must be > 0, got {v!r}")
    points = [
        PvtPoint(corner=corner, temp_c=temp, vdd=vdd, index=i)
        for i, (corner, temp, vdd) in enumerate(
            itertools.product(corners, temperatures, supplies)
        )
    ]

    by_id: dict[str, list[PvtPoint]] = {}
    for point in points:
        by_id.setdefault(point.corner_id, []).append(point)
    collisions = {cid: pts for cid, pts in by_id.items() if len(pts) > 1}
    if collisions:
        lines = []
        for cid, pts in sorted(collisions.items()):
            tuples = ", ".join(
                f"(corner={p.corner.name!r}, temp_c={p.temp_c!r}, vdd={p.vdd!r})" for p in pts
            )
            lines.append(f"  {cid!r} <- {tuples}")
        raise CornerIdCollisionError(
            "PVT grid has colliding corner_id values -- distinct "
            "(corner, temp_c, vdd) points rendered to the same id, so the "
            "grid would silently lose points:\n" + "\n".join(lines) +
            "\n\nThis happens when a custom --temps/--supply-tolerance "
            "produces values that round to the same corner_id string "
            "(temp_c uses ':g', vdd uses ':.2f'). Widen the spacing between "
            "the colliding values."
        )

    return points

"""Unit tests for ``harness.corners.build_grid``'s corner_id uniqueness check.

Ported from ``2AMLogic/gf180-comparator``'s ``sim/harness/tests/
test_corners.py`` (regression coverage for that repo's issue #8: a custom
``--temps``/``--supply-tolerance`` can produce distinct ``(corner, temp_c,
vdd)`` tuples that render to the same ``corner_id`` string, silently
collapsing the grid instead of raising). ADAPTED FOR SG13G2: the collision
repro uses this repo's own 1.2 V LV nominal (``DEFAULT_NOMINAL_SUPPLY_V``)
in place of gf180mcu's 3.3 V rail -- the ``:.2f`` collision this exercises
is a property of the formatting, not of which nominal supply triggers it,
but the concrete numbers only mean something read against this repo's own
axis (``CornerIdCollisionError``'s own docstring already anticipates this
exact 1.1988/1.2/1.2012 V example). ``resolve_corners(["mos"])`` still
expands to the same five classic process points (``tt``/``ff``/``ss``/
``fs``/``sf``) as gf180-comparator's -- SG13G2 has no ``full`` corner set
(no PDK-resistor corner promotion; see ``harness/corners.py``'s module
docstring), so that test has no counterpart here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.corners import (  # noqa: E402
    CORNERS,
    DEFAULT_NOMINAL_SUPPLY_V,
    DEFAULT_SUPPLY_TOLERANCE,
    DEFAULT_TEMPERATURES_C,
    CornerIdCollisionError,
    build_grid,
    resolve_corners,
    supply_points,
)


class BuildGridCollisionTest(unittest.TestCase):
    def test_tight_supply_tolerance_collapses_corner_id_and_raises(self):
        """--supply-tolerance 0.001 on the 1.2 V nominal collapses all three
        supply points (1.1988 / 1.2 / 1.2012 V) to the same '1.20v' suffix
        under corner_id's ':.2f' formatting -- reproducing the scenario
        CornerIdCollisionError's own docstring describes, executed here for
        real against this repo's own supply axis.
        """
        supplies = supply_points(nominal_v=DEFAULT_NOMINAL_SUPPLY_V, tolerance=0.001)
        # Confirm the reproduction is real before asserting on its effect:
        # three *distinct* floats that all format identically under ':.2f'.
        self.assertEqual(len(set(supplies)), 3)
        self.assertEqual({f"{v:.2f}" for v in supplies}, {"1.20"})

        with self.assertRaises(CornerIdCollisionError) as ctx:
            build_grid([CORNERS["tt"]], [27.0], supplies)

        message = str(ctx.exception)
        self.assertIn("tt_27c_1.20v", message)
        # All three colliding vdd values should be named in the error so a
        # user can see which flag combination caused the collision.
        for vdd in supplies:
            self.assertIn(repr(vdd), message)

    def test_colliding_temperatures_also_raise(self):
        """The ':g' temperature format can collide independently of vdd."""
        supplies = supply_points(nominal_v=DEFAULT_NOMINAL_SUPPLY_V, tolerance=0)
        with self.assertRaises(CornerIdCollisionError):
            build_grid([CORNERS["tt"]], [27.0, 27.0000001], supplies)

    def test_default_grid_has_no_false_positive_collision(self):
        """The default 45-point grid (characterize.sh/selftest.sh) must not
        trip the new check."""
        corner_list = resolve_corners(["mos"])  # tt, ff, ss, fs, sf
        supplies = supply_points(DEFAULT_NOMINAL_SUPPLY_V, DEFAULT_SUPPLY_TOLERANCE)
        points = build_grid(corner_list, list(DEFAULT_TEMPERATURES_C), supplies)
        self.assertEqual(len(points), 5 * len(DEFAULT_TEMPERATURES_C) * len(supplies))
        ids = [p.corner_id for p in points]
        self.assertEqual(len(ids), len(set(ids)))

    def test_mismatch_corner_set_has_no_false_positive_collision(self):
        """comparator-offset-mc's ``mos_mismatch`` corner set (this repo's
        equivalent of gf180-comparator's ``full`` set for collision-check
        purposes -- see this module's docstring) must also stay
        collision-free at the default grid."""
        corner_list = resolve_corners(["mos_mismatch"])
        supplies = supply_points(DEFAULT_NOMINAL_SUPPLY_V, DEFAULT_SUPPLY_TOLERANCE)
        points = build_grid(corner_list, list(DEFAULT_TEMPERATURES_C), supplies)
        ids = [p.corner_id for p in points]
        self.assertEqual(len(ids), len(set(ids)))

    def test_zero_tolerance_single_supply_point_is_fine(self):
        """--supply-tolerance 0 collapses to a single supply point by design
        (see supply_points) -- not a collision, just one point per corner/temp."""
        supplies = supply_points(DEFAULT_NOMINAL_SUPPLY_V, tolerance=0)
        self.assertEqual(supplies, [DEFAULT_NOMINAL_SUPPLY_V])
        points = build_grid([CORNERS["tt"]], [27.0], supplies)
        self.assertEqual(len(points), 1)


if __name__ == "__main__":
    unittest.main()

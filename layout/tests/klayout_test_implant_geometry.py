"""pSD geometry regression for issue #184 (needs the klayout Python module).

On demand only: the name deliberately does not match the `test_*.py` pattern
of the stdlib-only CI discovery over layout/tests (which forbids skipped
tests). Run it from the repo root with
`uvx --from klayout==0.30.12 python -I -m unittest discover -s layout/tests -p 'klayout_test_*.py'`.
Checks the committed GDS against pSD.i (0.30 enclosure of a PFET gate) and
pSD.b (0.31 space/notch), and proves both checks detect the pre-fix geometry
(0.18 enclosure per island) while treating a joined implant as legal.
"""

import sys
import unittest
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[1]
GDS = LAYOUT / "comparator" / "comparator.gds"
sys.path.insert(0, str(LAYOUT))

import klayout.db as db  # required: this module is never run without klayout

PSD_I = 0.30
PSD_B = 0.31
DBU = 1000


def _um(v):
    return round(v * DBU)


def _regions(layout):
    top = layout.top_cell()

    def reg(ln, dt):
        return db.Region(top.begin_shapes_rec(layout.layer(ln, dt))).merged()

    return reg(1, 0), reg(5, 0), reg(14, 0)


def _violations(activ, poly, psd):
    """(pSD.i uncovered gate area, pSD.b space/notch pair count)."""
    gates = (poly & activ) & psd.sized(_um(0.005))  # PFET gates only
    # a gate point is enclosed by 0.30 iff it survives the shrunken implant
    bad_i = gates - psd.sized(-_um(PSD_I))
    bad_b = psd.space_check(_um(PSD_B))
    return bad_i.count(), bad_b.count()


class TestImplantGeometry(unittest.TestCase):
    def test_committed_gds_clean(self):
        ly = db.Layout()
        ly.read(str(GDS))
        self.assertEqual(_violations(*_regions(ly)), (0, 0))

    def _synthetic(self, enc, gap):
        activ = db.Region()
        poly = db.Region()
        psd = db.Region()
        x = 0
        for w in (_um(1.0), _um(3.0)):  # unequal-width islands
            activ.insert(db.Box(x, 0, x + _um(2.0), w))
            poly.insert(db.Box(x + _um(0.9), -_um(0.18), x + _um(1.1), w + _um(0.18)))
            psd.insert(db.Box(x - _um(enc), -_um(enc), x + _um(2.0 + enc), w + _um(enc)))
            x += _um(2.0 + gap)
        return activ, poly, psd.merged()

    def test_prefix_geometry_detected(self):
        bad_i, bad_b = _violations(*self._synthetic(0.18, 0.40))
        self.assertGreater(bad_i, 0)  # enclosure 0.18 < 0.30
        self.assertGreater(bad_b, 0)  # 0.04 um gap between islands

    def test_joined_implant_is_legal(self):
        self.assertEqual(_violations(*self._synthetic(0.30, 0.40)), (0, 0))


if __name__ == "__main__":
    unittest.main()

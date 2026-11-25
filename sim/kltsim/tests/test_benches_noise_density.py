"""Tie the injected-density constant to the committed bench circuit (issue #506).

TRANSIENT_NOISE_INJECTED_DENSITY_NV_RTHZ is the one place the Row 2 bench
injection lives; every projection and report figure loadwidth publishes is
scaled by it. The value is not free: it is vn_na * sqrt(2 * vn_ts) over the
committed circuit's plain `.param` lines, so these tests re-derive it from
the file klt actually netlists. A bench recalibration that leaves the
constant behind (or an edit to the constant that leaves the circuit behind)
fails loudly here instead of silently invalidating every published
projection. Stdlib only, no PDK, no ngspice, writes nothing.
"""

from __future__ import annotations

import math
import re
import unittest

from kltsim import build
from kltsim.benches import TRANSIENT_NOISE, TRANSIENT_NOISE_INJECTED_DENSITY_NV_RTHZ

#: Plain numeric `.param name=value` cards only -- braced expressions
#: (`.param od_xn={-1*od_x}`) are not values this test can evaluate.
_PARAM = re.compile(r"^\.param\s+(\w+)\s*=\s*([+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)\s*$",
                    re.MULTILINE)

#: Relative tolerance: the constant is the circuit value rounded to 4
#: significant digits (re-derivation drift ~1e-5), so 1e-3 catches any real
#: recalibration while never flaking on rounding.
REL_TOL = 1e-3


def _density_nv_rthz(text: str) -> float:
    """Input-referred density the circuit injects, in nV/sqrt(Hz)."""
    params = dict(_PARAM.findall(text))
    for name in ("vn_na", "vn_ts"):
        if name not in params:
            raise ValueError(f"circuit no longer carries a plain `.param {name}=` card")
    return float(params["vn_na"]) * math.sqrt(2.0 * float(params["vn_ts"])) * 1e9


class InjectedDensityConstantTest(unittest.TestCase):
    def test_committed_circuit_derives_the_constant(self):
        circuit = (build.BENCH_DIR / TRANSIENT_NOISE.circuit).read_text(encoding="utf-8")
        derived = _density_nv_rthz(circuit)
        self.assertAlmostEqual(
            derived, TRANSIENT_NOISE_INJECTED_DENSITY_NV_RTHZ,
            delta=TRANSIENT_NOISE_INJECTED_DENSITY_NV_RTHZ * REL_TOL)

    def test_recalibrated_circuit_fails_loudly(self):
        # The mechanism the test above relies on: retune vn_na (the knob a
        # recalibration would turn) and the derived density must leave the
        # constant's tolerance band -- a drift that passes would mean a
        # recalibrated bench silently kept its stale projections.
        circuit = (build.BENCH_DIR / TRANSIENT_NOISE.circuit).read_text(encoding="utf-8")
        retuned, n = re.subn(r"^(\.param\s+vn_na\s*=\s*)\S+", r"\g<1>6.0e-3",
                             circuit, flags=re.MULTILINE)
        self.assertEqual(n, 1, "scratch retune of vn_na did not apply")
        self.assertNotAlmostEqual(
            _density_nv_rthz(retuned), TRANSIENT_NOISE_INJECTED_DENSITY_NV_RTHZ,
            delta=TRANSIENT_NOISE_INJECTED_DENSITY_NV_RTHZ * REL_TOL)

    def test_braced_param_expressions_are_not_values(self):
        self.assertEqual(
            _PARAM.findall(".param vn_na=5.735e-3\n.param od_xn={-1*od_x}\n"),
            [("vn_na", "5.735e-3")])

    def test_report_prose_precision_is_unchanged(self):
        # loadwidth renders the constant into report prose via str(); it must
        # keep rendering 36.27 (the DR-0002 record's stated precision), not
        # 36.274... or a rounded 36.3.
        self.assertEqual(str(TRANSIENT_NOISE_INJECTED_DENSITY_NV_RTHZ), "36.27")


if __name__ == "__main__":
    unittest.main()

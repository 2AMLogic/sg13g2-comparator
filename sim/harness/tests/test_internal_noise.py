"""Unit tests for the optional internal-noise hook (issue #81).

Stdlib-only: no PDK, no ngspice, writes nothing outside a temp dir. They
cover the pure emission function (``harness.internal_noise``), its
rejection of unknown devices / unresolvable pins, and the hook-off
guarantee that ``compose_deck`` output is unchanged when the manifest has no
``internal_noise`` block.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness import internal_noise as inz  # noqa: E402
from harness.corners import Corner, PvtPoint  # noqa: E402
from harness.runner import compose_deck  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DUT = REPO_ROOT / "design" / "comparator.spice"

_MINI = """\
.subckt comparator vinp vinn clk vbias dout doutb vdd vss
XM3 ln lp np vss sg13_lv_nmos w=3u l=0.13u ng=1 m=1
XM5 ln lp vdd vdd sg13_lv_pmos w=3u l=0.13u ng=1 m=1
XM1 np vinp tail vss sg13_lv_nmos w=12u l=0.34u ng=1 m=1
.ends
"""


def _block(**over):
    block = {
        "subckt": "comparator",
        "inner": "x1",
        "instances": ["x0"],
        "ts": 2e-11,
        "rails": {"vdd": "vdd", "vss": "0"},
        "devices": {"XM3": {"g": 1e-3, "phase": "evaluate"}, "XM5": {"g": 2e-4}},
    }
    block.update(over)
    return block


class EmissionTest(unittest.TestCase):
    def test_empty_block_is_a_noop(self):
        self.assertEqual(inz.emit_internal_noise({}, _MINI), [])
        self.assertEqual(inz.emit_internal_noise(None, _MINI), [])

    def test_sample_emission_lines(self):
        lines = inz.emit_internal_noise(_block(), _MINI)
        text = "\n".join(lines)
        # hierarchical nodes of the inner instance; rails map to top-level nets
        self.assertIn("Binz_x0_xm3 x0.x1.ln x0.x1.np I = ", text)
        self.assertIn("Binz_x0_xm5 x0.x1.ln vdd I = ", text)
        # one white trnoise source per device, no 1/f terms
        self.assertEqual(sum(1 for l in lines if l.startswith("Vinz_")), 2)
        self.assertTrue(all(l.endswith(" 2e-11 0 0)") for l in lines if l.startswith("Vinz_")))
        # phase gating only where requested
        gated = [l for l in lines if l.startswith("Binz_x0_xm3")][0]
        ungated = [l for l in lines if l.startswith("Binz_x0_xm5")][0]
        self.assertIn("*v(clk)/v(vdd)'", gated)
        self.assertNotIn("v(clk)", ungated)

    def test_amplitude_matches_density_relation(self):
        # S = NA*sqrt(2*TS) must equal sqrt(4 k T gamma g) at the reference T.
        na = inz.na_at_tref(1e-3, 1.0, 2e-11, 1.0)
        s = na * (2 * 2e-11) ** 0.5
        self.assertAlmostEqual(s / inz.density_a_rthz(1e-3, 1.0, inz.T_REF_K - 273.15), 1.0, places=9)

    def test_scale_zero_emits_zero_amplitude(self):
        lines = inz.emit_internal_noise(_block(scale=0.0), _MINI)
        self.assertTrue(all("trnoise(0.000000000e+00 " in l for l in lines if l.startswith("Vinz_")))

    def test_one_source_set_per_instance(self):
        lines = inz.emit_internal_noise(_block(instances=["x0", "x1", "x2"]), _MINI)
        self.assertEqual(sum(1 for l in lines if l.startswith("Binz_")), 6)
        self.assertEqual(len({l.split()[0] for l in lines if l.startswith("Vinz_")}), 6)

    def test_unknown_device_rejected(self):
        with self.assertRaises(inz.InternalNoiseError) as ctx:
            inz.emit_internal_noise(_block(devices={"XM99": {"g": 1e-3}}), _MINI)
        self.assertIn("XM99", str(ctx.exception))

    def test_unresolvable_pin_terminal_rejected(self):
        # XM1's drain/source are np/tail (internal) -> fine; make a device
        # whose terminal is a pin that has no rails entry.
        with self.assertRaises(inz.InternalNoiseError):
            inz.emit_internal_noise(_block(rails={"vss": "0"}), _MINI)  # XM5 -> vdd

    def test_malformed_block_rejected(self):
        for bad in (
            _block(instances=[]),
            _block(ts=0),
            _block(scale=-1),
            _block(devices={"XM3": {"g": 0}}),
            _block(devices={"XM3": {"g": 1e-3, "phase": "sometimes"}}),
            _block(devices={"XM3": {"g": 1e-3, "bogus": 1}}),
            {**_block(), "bogus": 1},
        ):
            with self.assertRaises(inz.InternalNoiseError):
                inz.validate_block(bad)

    def test_real_dut_netlist_resolves(self):
        text = DUT.read_text()
        block = _block(devices={n: {"g": 1e-3} for n in ("XM3", "XM4", "XM5", "XM6", "XM7", "XM8", "XM9", "XM10")})
        lines = inz.emit_internal_noise(block, text)
        self.assertEqual(sum(1 for l in lines if l.startswith("Binz_")), 8)
        self.assertIn("Binz_x0_xm4 x0.x1.lp x0.x1.nn I = ", "\n".join(lines))


class HookOffTest(unittest.TestCase):
    """compose_deck is unchanged when the manifest has no internal_noise."""

    def _deck(self, internal_noise):
        pdk = SimpleNamespace(
            variant="ihp-sg13g2", version="0.3.0",
            mos_corner_lib=Path("/pdk/cornerMOSlv.lib"), osdi_dir=Path("/pdk/osdi"),
        )
        dut = SimpleNamespace(
            dut_id="d", provenance="schematic", netlist_sha256="0" * 64, netlist=DUT,
            param_lines=lambda: [".param dut_ib=2e-05"],
        )
        tb = SimpleNamespace(
            name="t", nominal_supply_v=1.2, params={"od_x": 0.001}, options=("reltol=1e-2",),
            netlist=Path("/tb/t.spice"), analyses=("tran 20p 5n",), measure={"m": "1"},
            internal_noise=internal_noise,
        )
        point = PvtPoint(Corner("mos_tt", "mos_tt", "typical"), 27.0, 1.2)
        return compose_deck(tb, pdk, dut, point)

    def test_absent_key_adds_nothing(self):
        self.assertNotIn("internal-noise", self._deck({}))
        self.assertNotIn("Binz_", self._deck({}))

    def test_present_key_only_inserts_between_testbench_and_control(self):
        base = self._deck({}).split("\n")
        hooked = self._deck(_block(instances=["x0"])).split("\n")
        inserted = [l for l in hooked if l not in base]
        self.assertTrue(inserted)
        self.assertTrue(any(l.startswith("Binz_") for l in inserted))
        # removing the inserted block yields the hook-off deck line for line
        i = hooked.index('.include "/tb/t.spice"')
        stripped = hooked[: i + 1] + hooked[hooked.index("* ---- measurement ----------------------------------------------------") - 1 :]
        self.assertEqual(stripped, base)


if __name__ == "__main__":
    unittest.main()

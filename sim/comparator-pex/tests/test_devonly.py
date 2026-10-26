"""Issue #191: the extracted-device-only adapter maps unambiguously or refuses
(stdlib only; no PDK, ngspice or klt).

    python3 -m unittest discover -s sim/comparator-pex/tests -p 'test_*.py'
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
import make_devonly as md  # noqa: E402
from make_reference import PINS  # noqa: E402

HDR = ".GLOBAL vsubs\n.SUBCKT comparator " + " ".join(PINS) + "\n"
DEV = ("X$1 tmid__t0 vbias__t0 vss__t0 vss__t1 sg13_lv_nmos L=0.5U W=5U AS=2.5P\n"
       "+ AD=1.25P PS=11U PD=5.5U\n")
RES = ("Rtmid_t0 tmid__t0 tmid 1.5\nRvbias_t0 vbias__t0 vbias 2\n"
       "Rvss_t0 vss__t0 vss 3\nRvss_t1 vss__t1 vss 4\n")
CAP = "Ctmid tmid vsubs 1e-15\nCcc_tmid_vss tmid vss 1e-17\n"
TIE = "Rvsubs_dctie vsubs 0 1e+12\n"
END = ".ENDS comparator\n"


def net(dev=DEV, res=RES, cap=CAP, tie=TIE):
    return HDR + dev + res + cap + tie + END


class Collapse(unittest.TestCase):
    def test_resistor_node_collapse(self):
        body, st = md.collapse(net())
        card = next(l for l in body.splitlines() if l.startswith("X$1"))
        self.assertEqual(card.split()[1:5], ["tmid", "vbias", "vss", "vss"])
        self.assertNotIn("__t", re.sub(r"^\*.*$", "", body, flags=re.M))
        self.assertEqual(st["terminal_series_r_collapsed"], 4)

    def test_rc_removed_tie_kept(self):
        body, st = md.collapse(net())
        cards = [l for l in body.splitlines() if not l.startswith("*")]
        self.assertFalse([l for l in cards if l[0] in "Cc" and not l.startswith("Rvsubs")])
        self.assertFalse([l for l in cards if re.match(r"R(tmid|vbias|vss)_", l)])
        self.assertEqual((st["ground_c_removed"], st["coupling_c_removed"],
                          st["dc_ties_retained"]), (1, 1, 1))

    def test_geometry_preserved_and_continuation_joined(self):
        body, _ = md.collapse(net())
        card = next(l for l in body.splitlines() if l.startswith("X$1"))
        self.assertTrue(card.endswith(
            "sg13_lv_nmos L=0.5U W=5U AS=2.5P AD=1.25P PS=11U PD=5.5U"))

    def test_real_netlist_counts(self):
        text = md.PEX.read_text()
        body, st = md.collapse(text)
        self.assertEqual((st["devices_retained"], st["terminal_series_r_collapsed"],
                          st["ground_c_removed"], st["coupling_c_removed"]),
                         (64, 252, 16, 52))
        src = re.findall(r"^X\S+ (?:\S+ ){4}(.*)$", re.sub(r"\n\+", "", text), re.M)
        out = re.findall(r"^X\S+ (?:\S+ ){4}(.*)$", body, re.M)
        self.assertEqual(sorted(src), sorted(out))

    def test_refuses(self):
        cases = {
            "unknown element": net() + "Lx a b 1n\n",
            "unknown directive": net() + ".param a=1\n",
            "non-terminal series R": net(res=RES + "Rfoo a b 1\n"),
            "duplicate terminal R": net(res=RES + "Rtmid_t0 tmid__t0 tmid 9\n"),
            "unresolved terminal": net(res=RES.replace("Rvss_t1 vss__t1 vss 4\n", "")),
            "R to wrong parent name": net(res=RES.replace("Rvss_t0", "Rvdd_t0")),
            "C on terminal": net(cap=CAP + "Cx tmid__t0 vsubs 1f\n"),
            "unclassified C": net(cap=CAP + "Cx a b 1f\n"),
            "unknown model": net(dev=DEV.replace("sg13_lv_nmos", "foo")),
            "orphan terminal R": net(res=RES + "Rtmid_t9 tmid__t9 tmid 1\n"),
            "bad pin order": net().replace(PINS[0] + " " + PINS[1], PINS[1] + " " + PINS[0]),
        }
        for name, text in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                md.collapse(text)


if __name__ == "__main__":
    unittest.main()

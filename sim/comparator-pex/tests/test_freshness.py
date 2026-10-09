"""Issue #123: the post-layout (klt pex) adapter inputs stay derived from their
sources, and `--check` never writes (stdlib only, no PDK / ngspice / klt).

Each case copies the three generators plus exactly the sources they read into a
temporary tree, mutates one thing, and runs the generators as subprocesses, the
way CI and a contributor do:

    python3 sim/comparator-pex/make_reference.py --check
    python3 sim/comparator-pex/make_testbenches.py --check
    python3 sim/comparator-pex/make_requests.py --check

Run locally:

    python3 -m unittest discover -s sim/comparator-pex/tests -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PEX = "sim/comparator-pex"
GENERATORS = ("make_reference.py", "make_testbenches.py", "make_requests.py")
BENCHES = ("regeneration", "kickback")

# Everything the generators read or check, relative to the repository root.
SOURCES = [
    "design/comparator.spice",
    "sim/dut.json",
    *(f"sim/comparator-{b}/testbench/tb.json" for b in BENCHES),
    *(f"sim/comparator-{b}/testbench/tb_{b}.spice" for b in BENCHES),
]
OUTPUTS = [
    f"{PEX}/dut/comparator.schematic.sp",
    *(f"{PEX}/dut/tb_{b}.sp" for b in BENCHES),
    *(f"{PEX}/requests/{b}.{v}.json" for b in BENCHES for v in ("nominal", "pvt")),
]


def snapshot(root: Path) -> dict:
    """Every file under root: bytes and mtime (a rewrite of equal bytes still shows)."""
    return {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for rel in [*SOURCES, *OUTPUTS, *(f"{PEX}/{g}" for g in GENERATORS)]:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)

    # -- helpers -------------------------------------------------------------

    def run_gen(self, gen: str, *args: str) -> subprocess.CompletedProcess:
        # Bytecode writing stays enabled: the snapshot would catch a generator
        # whose import leaves a __pycache__ behind in check mode.
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        return subprocess.run(
            [sys.executable, str(self.root / PEX / gen), *args],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=60,
        )

    def check_all(self) -> dict:
        return {g: self.run_gen(g, "--check") for g in GENERATORS}

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.root / rel
        text = path.read_text()
        self.assertIn(old, text, f"fixture drift: {old!r} not in {rel}")
        path.write_text(text.replace(old, new, 1))

    def assert_stale(self, gen: str, *rels: str) -> None:
        """`gen --check` fails, names each rel, and writes nothing anywhere."""
        before = snapshot(self.root)
        res = self.run_gen(gen, "--check")
        self.assertNotEqual(res.returncode, 0, f"{gen} --check passed on a stale tree")
        self.assertNotIn("Traceback", res.stderr)
        for rel in rels:
            self.assertIn(rel, res.stderr, f"{gen} did not name {rel}")
        self.assertEqual(snapshot(self.root), before, f"{gen} --check wrote on failure")

    def assert_fresh(self, *gens: str) -> None:
        before = snapshot(self.root)
        for gen in gens or GENERATORS:
            res = self.run_gen(gen, "--check")
            self.assertEqual(res.returncode, 0, f"{gen}: {res.stderr}")
        self.assertEqual(snapshot(self.root), before, "--check wrote on success")

    # -- clean tree ----------------------------------------------------------

    def test_committed_inputs_are_fresh_and_check_writes_nothing(self):
        self.assert_fresh()

    # -- make_requests.py ----------------------------------------------------

    def test_changed_measurement_makes_both_request_variants_stale(self):
        self.edit("sim/comparator-kickback/testbench/tb.json",
                  "meas tran ad_pos max v(ad) from=30n to=45n",
                  "meas tran ad_pos max v(ad) from=31n to=45n")
        self.assert_stale("make_requests.py",
                          f"{PEX}/requests/kickback.nominal.json",
                          f"{PEX}/requests/kickback.pvt.json")
        res = self.run_gen("make_requests.py", "--check")
        self.assertNotIn("regeneration", res.stderr)

    def test_changed_analysis_makes_requests_stale(self):
        tb = self.root / "sim/comparator-regeneration/testbench/tb.json"
        data = json.loads(tb.read_text())
        i = next(i for i, a in enumerate(data["analyses"]) if a.startswith("tran "))
        data["analyses"][i] += "0"
        tb.write_text(json.dumps(data, indent=2) + "\n")
        self.assert_stale("make_requests.py",
                          f"{PEX}/requests/regeneration.nominal.json",
                          f"{PEX}/requests/regeneration.pvt.json")

    def test_hand_edited_pvt_request_is_stale(self):
        self.edit(f"{PEX}/requests/regeneration.pvt.json", "125", "85")
        self.assert_stale("make_requests.py", f"{PEX}/requests/regeneration.pvt.json")

    def test_missing_request_is_named_and_not_recreated(self):
        (self.root / PEX / "requests/kickback.pvt.json").unlink()
        self.assert_stale("make_requests.py", f"{PEX}/requests/kickback.pvt.json")
        self.assertFalse((self.root / PEX / "requests/kickback.pvt.json").exists())

    # -- make_testbenches.py -------------------------------------------------

    def test_wrapper_bias_mirror_drift_is_stale(self):
        # The XMB card lives in the schematic's comparator_dut wrapper, which
        # the layout does not cover, so make_reference.py cannot see it.
        self.edit("design/comparator.spice",
                  "XMB ibias ibias vss vss sg13_lv_nmos w=10u l=0.5u",
                  "XMB ibias ibias vss vss sg13_lv_nmos w=12u l=0.5u")
        self.assert_fresh("make_reference.py")
        self.assert_stale("make_testbenches.py",
                          f"{PEX}/dut/tb_regeneration.sp", f"{PEX}/dut/tb_kickback.sp")

    def test_wrapper_core_connection_drift_is_stale(self):
        self.edit("design/comparator.spice",
                  "x1 vinp vinn clk ibias dout doutb vdd vss comparator",
                  "x1 vinn vinp clk ibias dout doutb vdd vss comparator")
        self.assert_stale("make_testbenches.py", f"{PEX}/dut/tb_regeneration.sp")

    def test_extra_wrapper_card_is_stale(self):
        self.edit("design/comparator.spice",
                  "x1 vinp vinn clk ibias dout doutb vdd vss comparator",
                  "x1 vinp vinn clk ibias dout doutb vdd vss comparator\n"
                  "Cib ibias vss 1p")
        self.assert_stale("make_testbenches.py", f"{PEX}/dut/tb_kickback.sp")

    def test_wrapper_core_instance_is_emitted_in_extractor_pin_order(self):
        text = (self.root / PEX / "dut/tb_regeneration.sp").read_text()
        self.assertIn("x1 clk dout doutb ibias vdd vinn vinp vss comparator\n", text)

    def test_consumed_dut_parameter_change_is_stale(self):
        self.edit("sim/dut.json", '"dut_ib": 2e-05', '"dut_ib": 3e-05')
        self.assert_stale("make_testbenches.py", f"{PEX}/dut/tb_regeneration.sp")

    def test_source_stimulus_change_is_stale(self):
        self.edit("sim/comparator-kickback/testbench/tb_kickback.spice",
                  ".param rsrc=1k", ".param rsrc=2k")
        self.assert_stale("make_testbenches.py", f"{PEX}/dut/tb_kickback.sp")

    def test_missing_testbench_is_named(self):
        (self.root / PEX / "dut/tb_kickback.sp").unlink()
        self.assert_stale("make_testbenches.py", f"{PEX}/dut/tb_kickback.sp")

    # -- make_reference.py ---------------------------------------------------

    def test_schematic_core_change_is_stale(self):
        self.edit("design/comparator.spice",
                  "XM1 np vinp tail vss sg13_lv_nmos w=12u",
                  "XM1 np vinp tail vss sg13_lv_nmos w=13u")
        self.assert_stale("make_reference.py", f"{PEX}/dut/comparator.schematic.sp")

    def test_missing_reference_is_named(self):
        (self.root / PEX / "dut/comparator.schematic.sp").unlink()
        self.assert_stale("make_reference.py", f"{PEX}/dut/comparator.schematic.sp")

    # -- intentional regeneration -------------------------------------------

    def test_regeneration_restores_freshness(self):
        self.edit("design/comparator.spice",
                  "XMB ibias ibias vss vss sg13_lv_nmos w=10u",
                  "XMB ibias ibias vss vss sg13_lv_nmos w=12u")
        self.edit("sim/comparator-kickback/testbench/tb.json", "from=30n", "from=31n")
        for gen in GENERATORS:
            self.assertEqual(self.run_gen(gen).returncode, 0)
        self.assert_fresh()
        self.assertIn("w=12u l=0.5u",
                      (self.root / PEX / "dut/tb_kickback.sp").read_text())


if __name__ == "__main__":
    unittest.main()

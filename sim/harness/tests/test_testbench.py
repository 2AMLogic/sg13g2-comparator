"""Unit tests for ``harness.testbench.load``'s Monte-Carlo seed guard.

Added for issue #28: on the pinned ngspice-46 toolchain, ``set rndseed=<N>``
does not actually seed the stream ``agauss()`` mismatch draws are taken
from (two runs of the same deck produce different draws) -- ``setseed <N>``
(no ``set`` prefix) is the mechanism that does. A ``record_kind:
monte-carlo`` manifest that still uses ``set rndseed=`` is silently wrong on
this toolchain, so ``load()`` refuses it at load time (mirroring the
``ValueError``-at-load-time style ``validate_netlist`` and the measurement
name checks already use in this module).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness.testbench import load  # noqa: E402

_NETLIST = "* empty fragment, no forbidden directives\n"


def _write_manifest(root: Path, record_kind: str, seed_line: str) -> Path:
    """Write a minimal-but-valid tb.json + netlist fragment under ``root``
    and return the experiment directory (what ``load()`` accepts)."""
    testbench_dir = root / "testbench"
    testbench_dir.mkdir(parents=True)
    (testbench_dir / "probe.spice").write_text(_NETLIST)
    manifest = {
        "name": "probe",
        "netlist": "probe.spice",
        "analyses": [seed_line, "op"],
        "measure": {"m_probe": "1"},
        "evidence": {"record_kind": record_kind},
    }
    import json

    (testbench_dir / "tb.json").write_text(json.dumps(manifest))
    return root


class MonteCarloSeedGuardTest(unittest.TestCase):
    def test_monte_carlo_with_set_rndseed_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_manifest(Path(tmp) / "probe-mc", "monte-carlo", "set rndseed=12345")
            with self.assertRaises(ValueError) as ctx:
                load(root)
            self.assertIn("set rndseed=", str(ctx.exception))
            self.assertIn("setseed", str(ctx.exception))

    def test_monte_carlo_with_set_rndseed_is_rejected_case_insensitive_and_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_manifest(Path(tmp) / "probe-mc", "monte-carlo", "  SET RNDSEED=12345  ")
            with self.assertRaises(ValueError):
                load(root)

    def test_monte_carlo_with_setseed_loads_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_manifest(Path(tmp) / "probe-mc", "monte-carlo", "setseed 12345")
            tb = load(root)
            self.assertEqual(tb.evidence["record_kind"], "monte-carlo")

    def test_corner_matrix_with_set_rndseed_is_not_rejected(self):
        """The guard is scoped to Monte-Carlo benches only -- a corner-matrix
        manifest using `set rndseed=` for something unrelated to a
        common-random-numbers claim must still load."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_manifest(Path(tmp) / "probe-cm", "corner-matrix", "set rndseed=12345")
            tb = load(root)
            self.assertEqual(tb.evidence["record_kind"], "corner-matrix")


if __name__ == "__main__":
    unittest.main()

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

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

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



# Issue #178: malformed check bounds are rejected at load time.

def _write_checks(root: Path, check: dict, raw: str = "") -> Path:
    tbdir = root / "testbench"
    tbdir.mkdir(parents=True)
    (tbdir / "probe.spice").write_text(_NETLIST)
    manifest = {"name": "probe", "netlist": "probe.spice",
                "measure": {"m_probe": "1"}, "checks": {"m_probe": check}}
    (tbdir / "tb.json").write_text(json.dumps(manifest).replace('"RAW"', raw))
    return root


# Spliced in as raw JSON text so NaN/Infinity/1e999 reach the parser as-is.
_BAD = ['"1"', "null", "true", "[1]", "{}", "NaN", "Infinity", "-Infinity", "1e999", "1" + "0" * 400]


class CheckBoundValidationTest(unittest.TestCase):
    def _load(self, check: dict, raw: str = ""):
        with tempfile.TemporaryDirectory() as tmp:
            return load(_write_checks(Path(tmp) / "p", check, raw))

    def _assert_all_rejected(self, checks, raw: str = ""):
        for check in checks:
            with self.subTest(check=check, raw=raw), self.assertRaises(ValueError):
                self._load(check, raw)

    def test_malformed_bounds_rejected(self):
        for raw in _BAD:
            self._assert_all_rejected(
                [{k: "RAW"} for k in ("min", "max", "min_spread_pct", "max_spread_pct")]
                + [{k: {"process": "RAW"}} for k in ("min_spread_pct_by_axis", "max_spread_pct_by_axis")],
                raw,
            )

    def test_min_greater_than_max_rejected(self):
        self._assert_all_rejected([
            {"min": 2, "max": 1},
            {"min_spread_pct": 5, "max_spread_pct": 1},
            {"min_spread_pct_by_axis": {"supply": 5}, "max_spread_pct_by_axis": {"supply": 1}},
        ])

    def test_negative_spread_rejected(self):
        self._assert_all_rejected([
            {"max_spread_pct": -1},
            {"min_spread_pct": -0.5},
            {"max_spread_pct_by_axis": {"process": -1}},
            {"min_spread_pct_by_axis": {"temperature": -1}},
        ])

    def test_valid_bounds_accepted(self):
        for check in (
            {"min": -0.05, "max": -0.01},
            {"min": 1, "max": 1},
            {"min_spread_pct": 0, "max_spread_pct": 0},
            {"min_spread_pct_by_axis": {"process": 0, "supply": 2.5},
             "max_spread_pct_by_axis": {"process": 3, "supply": 2.5}},
        ):
            with self.subTest(check=check):
                self._load(check)

    def test_shipped_manifests_still_load(self):
        sim_dir = Path(__file__).resolve().parents[2]
        manifests = sorted(sim_dir.glob("*/testbench/tb.json"))
        self.assertTrue(manifests)
        for m in manifests:
            with self.subTest(manifest=m.parent.parent.name):
                load(m)

    def test_cli_bad_bound_fails_before_ngspice_and_reservation(self):
        from harness import cli, report, runner

        with tempfile.TemporaryDirectory() as tmp:
            sim_dir = Path(tmp)
            _write_checks(sim_dir / "bad-exp", {"max": "RAW"}, "NaN")
            with mock.patch.object(cli, "SIM_DIR", sim_dir), \
                 mock.patch.object(runner, "ngspice_version") as nv, \
                 mock.patch.object(report, "reserve_run") as rr, \
                 mock.patch.object(cli.pdk_mod, "find_pdk") as fp, \
                 redirect_stderr(io.StringIO()) as err:
                rc = cli.main(["bad-exp"])
            self.assertEqual(rc, 1)
            self.assertIn("invalid testbench manifest", err.getvalue())
            for m in (nv, rr, fp):
                m.assert_not_called()
            # Nothing reserved or written: no run dir beside the testbench.
            self.assertEqual([p.name for p in sim_dir.iterdir()], ["bad-exp"])
            self.assertEqual([p.name for p in (sim_dir / "bad-exp").iterdir()], ["testbench"])


if __name__ == "__main__":
    unittest.main()

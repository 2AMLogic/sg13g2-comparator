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




# ---------------------------------------------------------------------------
# Issue #178: check-bound validation at load time
# ---------------------------------------------------------------------------

import json  # noqa: E402
import io  # noqa: E402
from contextlib import redirect_stderr  # noqa: E402
from unittest import mock  # noqa: E402


def _write_checks(root: Path, check: dict, raw: str | None = None) -> Path:
    tbdir = root / "testbench"
    tbdir.mkdir(parents=True)
    (tbdir / "probe.spice").write_text(_NETLIST)
    manifest = {
        "name": "probe",
        "netlist": "probe.spice",
        "measure": {"m_probe": "1"},
        "checks": {"m_probe": check},
    }
    text = json.dumps(manifest)
    if raw is not None:
        text = text.replace('"__RAW__"', raw)
    (tbdir / "tb.json").write_text(text)
    return root


_BAD_VALUES = [
    ("string", '"1"'),
    ("null", "null"),
    ("true", "true"),
    ("list", "[1]"),
    ("dict", "{}"),
    ("NaN", "NaN"),
    ("Infinity", "Infinity"),
    ("-Infinity", "-Infinity"),
    ("overflow", "1e999"),
    ("bigint", "1" + "0" * 400),
]


class CheckBoundValidationTest(unittest.TestCase):
    def _load_raw(self, check: dict):
        with tempfile.TemporaryDirectory() as tmp:
            return load(_write_checks(Path(tmp) / "p", check, raw=None))

    def _expect_bad(self, check_template: dict, raw: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = _write_checks(Path(tmp) / "p", check_template, raw=raw)
            with self.assertRaises(ValueError):
                load(root)

    def test_scalar_bounds_reject_malformed(self):
        for key in ("min", "max", "min_spread_pct", "max_spread_pct"):
            for label, raw in _BAD_VALUES:
                with self.subTest(key=key, value=label):
                    self._expect_bad({key: "__RAW__"}, raw)

    def test_per_axis_bounds_reject_malformed(self):
        for key in ("min_spread_pct_by_axis", "max_spread_pct_by_axis"):
            for label, raw in _BAD_VALUES:
                with self.subTest(key=key, value=label):
                    self._expect_bad({key: {"process": "__RAW__"}}, raw)

    def test_min_greater_than_max_rejected(self):
        for check in (
            {"min": 2, "max": 1},
            {"min_spread_pct": 5, "max_spread_pct": 1},
            {"min_spread_pct_by_axis": {"supply": 5}, "max_spread_pct_by_axis": {"supply": 1}},
        ):
            with self.subTest(check=check):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(ValueError) as ctx:
                        load(_write_checks(Path(tmp) / "p", check))
                    self.assertIn("exceeds", str(ctx.exception))

    def test_negative_spread_rejected(self):
        for check in (
            {"max_spread_pct": -1},
            {"min_spread_pct": -0.5},
            {"max_spread_pct_by_axis": {"process": -1}},
            {"min_spread_pct_by_axis": {"temperature": -1}},
        ):
            with self.subTest(check=check):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(ValueError):
                        load(_write_checks(Path(tmp) / "p", check))

    def test_valid_bounds_accepted(self):
        for check in (
            {"min": -0.05, "max": -0.01},
            {"min": -1, "max": 1},
            {"min": 1, "max": 1},
            {"min_spread_pct": 0, "max_spread_pct": 0},
            {"min_spread_pct_by_axis": {"process": 0, "supply": 2.5},
             "max_spread_pct_by_axis": {"process": 3, "supply": 2.5}},
        ):
            with self.subTest(check=check):
                with tempfile.TemporaryDirectory() as tmp:
                    load(_write_checks(Path(tmp) / "p", check))

    def test_shipped_manifests_still_load(self):
        sim_dir = Path(__file__).resolve().parents[2]
        manifests = sorted(sim_dir.glob("*/testbench/tb.json"))
        self.assertTrue(manifests)
        for m in manifests:
            with self.subTest(manifest=str(m.relative_to(sim_dir))):
                load(m)


class CliPreflightTest(unittest.TestCase):
    def test_bad_bound_fails_before_ngspice_and_reservation(self):
        from harness import cli, report as report_mod, runner as runner_mod

        with tempfile.TemporaryDirectory() as tmp:
            sim_dir = Path(tmp)
            _write_checks(sim_dir / "bad-exp", {"max": "__RAW__"}, raw="NaN")
            with mock.patch.object(cli, "SIM_DIR", sim_dir), \
                 mock.patch.object(runner_mod, "ngspice_version", side_effect=AssertionError("ngspice")) as nv, \
                 mock.patch.object(report_mod, "reserve_run", side_effect=AssertionError("reserve")) as rr, \
                 mock.patch.object(cli.pdk_mod, "find_pdk", side_effect=AssertionError("pdk")), \
                 redirect_stderr(io.StringIO()) as err:
                rc = cli.main(["bad-exp"])
            self.assertEqual(rc, 1)
            self.assertIn("invalid testbench manifest", err.getvalue())
            nv.assert_not_called()
            rr.assert_not_called()
            self.assertEqual([p.name for p in sim_dir.iterdir()], ["bad-exp"])
            self.assertEqual({p.name for p in (sim_dir / "bad-exp").iterdir()}, {"testbench"})


if __name__ == "__main__":
    unittest.main()

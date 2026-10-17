"""Issue #264: invalid PVT grid coordinates are rejected before simulation."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness import cli  # noqa: E402
from harness.corners import build_grid, resolve_corners, supply_points  # noqa: E402
from harness.testbench import load  # noqa: E402

NAN, INF = float("nan"), float("inf")


class CornersValidationTest(unittest.TestCase):
    def test_bad_tolerance(self):
        for tol in (-0.1, NAN, INF, -INF, 1.0, 1.5, True, "0.1", None):
            with self.subTest(tol=tol), self.assertRaises(ValueError) as ctx:
                supply_points(1.2, tol)
            self.assertIn("supply_tolerance", str(ctx.exception))

    def test_bad_nominal(self):
        for nom in (0, -1.2, NAN, INF, False, "1.2", None, 10**400):
            with self.subTest(nom=nom), self.assertRaises(ValueError) as ctx:
                supply_points(nom, 0.1)
            self.assertIn("nominal_supply_v", str(ctx.exception))

    def test_zero_tolerance_is_nominal_only(self):
        self.assertEqual(supply_points(1.2, 0), [1.2])
        self.assertEqual(supply_points(1.2, 0.0), [1.2])

    def test_overflowing_rail_rejected(self):
        with self.assertRaises(ValueError):
            supply_points(1e308, 0.9)

    def test_bad_temperatures(self):
        corners = resolve_corners(["tt"])
        for temps in ([NAN], [INF], [True], ["27"], [None], [], [10**400], "27"):
            with self.subTest(temps=temps), self.assertRaises(ValueError):
                build_grid(corners, temps, [1.2])

    def test_bad_supplies_and_empty_axes(self):
        corners = resolve_corners(["tt"])
        for sup in ([], [0.0], [-1.2], [NAN], [INF]):
            with self.subTest(sup=sup), self.assertRaises(ValueError):
                build_grid(corners, [27.0], sup)
        with self.assertRaises(ValueError):
            build_grid([], [27.0], [1.2])

    def test_valid_grids_preserved(self):
        self.assertEqual(len(build_grid(resolve_corners(["mos"]), [-40, 27, 125], supply_points())), 45)
        pts = build_grid(resolve_corners(["tt"]), [-273.0, 300.5], [1.2])
        self.assertEqual([p.temp_c for p in pts], [-273.0, 300.5])


def _write_tb(root: Path, **extra) -> Path:
    tbdir = root / "exp" / "testbench"
    tbdir.mkdir(parents=True)
    (tbdir / "p.spice").write_text("* frag\n")
    manifest = {"netlist": "p.spice", "measure": {"m": "1"}, **extra}
    (tbdir / "tb.json").write_text(json.dumps(manifest))
    return root / "exp"


class ManifestValidationTest(unittest.TestCase):
    def load_with(self, **extra):
        with tempfile.TemporaryDirectory() as tmp:
            return load(_write_tb(Path(tmp), **extra))

    def test_invalid_fields_name_the_field(self):
        cases = [
            ("supply_tolerance", -0.1), ("supply_tolerance", True), ("supply_tolerance", "0.1"),
            ("supply_tolerance", None), ("supply_tolerance", 1),
            ("nominal_supply_v", 0), ("nominal_supply_v", "1.2"), ("nominal_supply_v", None),
            ("nominal_supply_v", False), ("nominal_supply_v", 10**400),
            ("temperatures_c", []), ("temperatures_c", [True]), ("temperatures_c", ["27"]),
            ("temperatures_c", [None]), ("temperatures_c", [10**400]), ("temperatures_c", None),
            ("temperatures_c", 27),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError) as ctx:
                self.load_with(**{key: value})
            self.assertIn(key, str(ctx.exception))

    def test_valid_manifest(self):
        tb = self.load_with(supply_tolerance=0, temperatures_c=[-55, 27.5])
        self.assertEqual(tb.supply_tolerance, 0.0)
        self.assertEqual(tb.temperatures_c, (-55.0, 27.5))


class CliValidationTest(unittest.TestCase):
    def run_cli(self, *args, **manifest):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tb(root, corners=["tt"], **manifest)
            err = io.StringIO()
            with mock.patch.object(cli, "SIM_DIR", root), \
                 mock.patch.object(cli.pdk_mod, "find_pdk") as find_pdk, \
                 mock.patch.object(cli.report_mod, "reserve_run") as reserve, \
                 mock.patch("harness.runner.subprocess.run") as run, \
                 redirect_stdout(io.StringIO()), redirect_stderr(err):
                try:
                    rc = cli.main(["exp", *args])
                except SystemExit as exc:
                    rc = exc.code
            return rc, err.getvalue(), find_pdk, reserve, run

    def assert_rejected(self, *args, text=None, **manifest):
        rc, err, find_pdk, reserve, run = self.run_cli(*args, **manifest)
        self.assertNotEqual(rc, 0)
        if text:
            self.assertIn(text, err)
        find_pdk.assert_not_called()
        reserve.assert_not_called()
        run.assert_not_called()

    def test_cli_overrides_rejected_without_side_effects(self):
        self.assert_rejected("--supply-tolerance", "-0.1", text="supply_tolerance")
        self.assert_rejected("--supply-tolerance", "1.5", text="supply_tolerance")
        self.assert_rejected("--supply-tolerance", "nan")
        self.assert_rejected("--supply-tolerance", "inf")
        self.assert_rejected("--temps", "nan")
        self.assert_rejected("--temps", "27", "inf")
        self.assert_rejected("--temps", text="--temps")

    def test_bad_manifest_rejected(self):
        self.assert_rejected(supply_tolerance=-0.1, text="supply_tolerance")


if __name__ == "__main__":
    unittest.main()

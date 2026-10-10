"""Unit tests for ``harness.toolchain``'s pin-drift check.

``check`` produces the ``drift`` list that decides whether a PVT run is
refused or stamped, so a regression here silently mislabels append-only
evidence. Stdlib only; no PDK or ngspice needed -- pin files are temp fixtures.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness import toolchain  # noqa: E402

GOOD_BANNER = "ngspice-46 : Circuit level simulation program"


class ToolchainCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pin_path = Path(self._tmp.name) / "toolchain.json"

    def _write(self, **pins) -> None:
        self.pin_path.write_text(json.dumps(pins))

    def _check(self, pdk="0.3.0", banner=GOOD_BANNER) -> toolchain.Toolchain:
        return toolchain.check(pdk, banner, path=self.pin_path)

    def test_no_drift_when_all_match(self) -> None:
        self._write(pdk_release="0.3.0", ngspice_min_major=46, python_min="3.9")
        result = self._check()
        self.assertEqual(result.drift, [])
        self.assertEqual(result.observed["pdk_release"], "0.3.0")
        self.assertEqual(result.observed["ngspice"], GOOD_BANNER)

    def test_newer_ngspice_is_allowed(self) -> None:
        self._write(ngspice_min_major=46)
        self.assertEqual(self._check(banner="ngspice-47 : x").drift, [])

    def test_pdk_release_mismatch(self) -> None:
        self._write(pdk_release="0.3.0")
        drift = self._check(pdk="0.2.9").drift
        self.assertEqual(len(drift), 1)
        self.assertIn("pdk_release", drift[0])
        self.assertIn("0.3.0", drift[0])
        self.assertIn("0.2.9", drift[0])

    def test_pdk_release_null_disables_check(self) -> None:
        self._write(pdk_release=None)
        self.assertEqual(self._check(pdk="anything").drift, [])

    def test_unknown_pdk_version_is_drift(self) -> None:
        self._write(pdk_release="0.3.0")
        self.assertEqual(len(self._check(pdk="unknown").drift), 1)

    def test_ngspice_below_floor(self) -> None:
        self._write(ngspice_min_major=46)
        drift = self._check(banner="ngspice-45 : x").drift
        self.assertEqual(len(drift), 1)
        self.assertIn("ngspice", drift[0])
        self.assertIn("45", drift[0])

    def test_unparseable_ngspice_banner(self) -> None:
        self._write(ngspice_min_major=46)
        drift = self._check(banner="not a banner").drift
        self.assertEqual(len(drift), 1)
        self.assertIn("could not parse", drift[0])

    def test_unparseable_banner_ignored_without_floor(self) -> None:
        self._write(pdk_release="0.3.0")
        self.assertEqual(self._check(banner="garbage").drift, [])

    def test_python_floor(self) -> None:
        self._write(python_min="3.9")
        with mock.patch.object(toolchain.sys, "version_info", (3, 8, 0, "final", 0)):
            drift = self._check().drift
        self.assertEqual(len(drift), 1)
        self.assertIn("python", drift[0])

    def test_python_floor_met(self) -> None:
        self._write(python_min="3.9")
        with mock.patch.object(toolchain.sys, "version_info", (3, 9, 0, "final", 0)):
            self.assertEqual(self._check().drift, [])

    def test_multiple_drifts_all_reported(self) -> None:
        self._write(pdk_release="0.3.0", ngspice_min_major=46)
        self.assertEqual(len(self._check(pdk="0.1", banner="ngspice-40").drift), 2)

    def test_missing_pin_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            toolchain.check("0.3.0", GOOD_BANNER, path=self.pin_path)

    def test_as_dict_hides_underscore_pins_and_copies_drift(self) -> None:
        self._write(_comment=["x"], pdk_release="0.3.0")
        result = self._check(pdk="9")
        data = result.as_dict()
        self.assertNotIn("_comment", data["pins"])
        self.assertEqual(data["pins"]["pdk_release"], "0.3.0")
        self.assertEqual(data["drift"], result.drift)
        self.assertIsNot(data["drift"], result.drift)


class NgspiceMajorTest(unittest.TestCase):
    def test_parses_major(self) -> None:
        self.assertEqual(toolchain._ngspice_major("ngspice-46 : foo"), 46)
        self.assertEqual(toolchain._ngspice_major("** ngspice-43.1 **"), 43)

    def test_unparseable_returns_none(self) -> None:
        self.assertIsNone(toolchain._ngspice_major(""))
        self.assertIsNone(toolchain._ngspice_major("ngspice version unknown"))


if __name__ == "__main__":
    unittest.main()

"""Unit tests for ``harness.pdk`` resolution order and config merging.

``find_pdk`` decides which device models a record is attributed to
(``SG13G2_PDK_PATH`` > ``PDK_ROOT`` > ``pdk.local.json``/``pdk.json`` search
roots > built-in roots). Stdlib only; fake PDK trees are temp fixtures and the
module's ``SIM_DIR`` / ``BUILTIN_SEARCH_ROOTS`` are patched so the host's real
install and config never leak in.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness import pdk  # noqa: E402


def _make_variant(root: Path, name: str = "ihp-sg13g2") -> Path:
    variant = root / name
    models = variant / "libs.tech" / "ngspice" / "models"
    models.mkdir(parents=True)
    (models / "cornerMOSlv.lib").write_text("* stub\n")
    return variant


class PdkTestBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.sim_dir = self.tmp / "sim"
        self.sim_dir.mkdir()
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        for key in ("SG13G2_PDK_PATH", "PDK_ROOT", "PDK"):
            os.environ.pop(key, None)
        for target, value in (
            (pdk, {"SIM_DIR": self.sim_dir, "BUILTIN_SEARCH_ROOTS": ()}),
        ):
            patcher = mock.patch.multiple(target, **value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _config(self, name: str, data: dict) -> None:
        (self.sim_dir / name).write_text(json.dumps(data))


class FindPdkTest(PdkTestBase):
    def test_sg13g2_pdk_path_wins_over_pdk_root(self) -> None:
        direct = _make_variant(self.tmp / "direct")
        _make_variant(self.tmp / "root")
        os.environ["SG13G2_PDK_PATH"] = str(direct)
        os.environ["PDK_ROOT"] = str(self.tmp / "root")
        found = pdk.find_pdk()
        self.assertEqual(found.path, direct)
        self.assertEqual(found.source, "SG13G2_PDK_PATH")

    def test_invalid_sg13g2_pdk_path_raises_without_fallthrough(self) -> None:
        _make_variant(self.tmp / "root")
        os.environ["SG13G2_PDK_PATH"] = str(self.tmp / "nope")
        os.environ["PDK_ROOT"] = str(self.tmp / "root")
        with self.assertRaises(pdk.PdkNotFound) as ctx:
            pdk.find_pdk()
        self.assertIn("SG13G2_PDK_PATH", str(ctx.exception))

    def test_pdk_root_with_default_variant(self) -> None:
        variant = _make_variant(self.tmp / "root")
        os.environ["PDK_ROOT"] = str(self.tmp / "root")
        found = pdk.find_pdk()
        self.assertEqual(found.path, variant)
        self.assertEqual(found.source, "PDK_ROOT")
        self.assertEqual(found.variant, "ihp-sg13g2")

    def test_pdk_env_selects_variant(self) -> None:
        variant = _make_variant(self.tmp / "root", "other-variant")
        os.environ["PDK_ROOT"] = str(self.tmp / "root")
        os.environ["PDK"] = "other-variant"
        self.assertEqual(pdk.find_pdk().path, variant)

    def test_variant_argument_beats_pdk_env(self) -> None:
        variant = _make_variant(self.tmp / "root", "arg-variant")
        os.environ["PDK_ROOT"] = str(self.tmp / "root")
        os.environ["PDK"] = "other-variant"
        self.assertEqual(pdk.find_pdk("arg-variant").path, variant)

    def test_pdk_root_beats_config_search_roots(self) -> None:
        env_variant = _make_variant(self.tmp / "envroot")
        cfg_root = self.tmp / "cfgroot"
        _make_variant(cfg_root)
        self._config("pdk.json", {"search_roots": [str(cfg_root)]})
        os.environ["PDK_ROOT"] = str(self.tmp / "envroot")
        self.assertEqual(pdk.find_pdk().path, env_variant)

    def test_invalid_pdk_root_falls_through_to_search_roots(self) -> None:
        cfg_root = self.tmp / "cfgroot"
        variant = _make_variant(cfg_root)
        self._config("pdk.json", {"search_roots": [str(cfg_root)]})
        os.environ["PDK_ROOT"] = str(self.tmp / "empty")
        found = pdk.find_pdk()
        self.assertEqual(found.path, variant)
        self.assertTrue(found.source.startswith("search_root:"))

    def test_config_search_root_beats_builtin(self) -> None:
        cfg_root = self.tmp / "cfgroot"
        builtin_root = self.tmp / "builtin"
        variant = _make_variant(cfg_root)
        _make_variant(builtin_root)
        self._config("pdk.json", {"search_roots": [str(cfg_root)]})
        with mock.patch.object(pdk, "BUILTIN_SEARCH_ROOTS", (str(builtin_root),)):
            self.assertEqual(pdk.find_pdk().path, variant)

    def test_builtin_root_used_last(self) -> None:
        builtin_root = self.tmp / "builtin"
        variant = _make_variant(builtin_root)
        with mock.patch.object(pdk, "BUILTIN_SEARCH_ROOTS", (str(builtin_root),)):
            found = pdk.find_pdk()
        self.assertEqual(found.path, variant)
        self.assertEqual(found.source, f"search_root:{builtin_root}")

    def test_local_config_overrides_committed_variant(self) -> None:
        root = self.tmp / "root"
        variant = _make_variant(root, "local-variant")
        _make_variant(root, "committed-variant")
        self._config("pdk.json", {"variant": "committed-variant", "search_roots": [str(root)]})
        self._config("pdk.local.json", {"variant": "local-variant"})
        self.assertEqual(pdk.find_pdk().path, variant)

    def test_not_found_lists_tried_paths(self) -> None:
        root_a = self.tmp / "a"
        root_b = self.tmp / "b"
        self._config("pdk.json", {"search_roots": [str(root_a)]})
        os.environ["PDK_ROOT"] = str(root_b)
        with self.assertRaises(pdk.PdkNotFound) as ctx:
            pdk.find_pdk()
        msg = str(ctx.exception)
        self.assertIn(str(root_b / "ihp-sg13g2"), msg)
        self.assertIn(str(root_a / "ihp-sg13g2"), msg)
        self.assertIn("IHP SG13G2 PDK not found", msg)

    def test_expands_user_and_env_vars_in_roots(self) -> None:
        root = self.tmp / "home" / "pdks"
        variant = _make_variant(root)
        os.environ["FAKE_HOME_FOR_TEST"] = str(self.tmp / "home")
        self._config("pdk.json", {"search_roots": ["$FAKE_HOME_FOR_TEST/pdks"]})
        self.assertEqual(pdk.find_pdk().path, variant)


class LoadConfigTest(PdkTestBase):
    def test_empty_when_no_files(self) -> None:
        self.assertEqual(pdk._load_config(), {})

    def test_local_overrides_committed_key_by_key(self) -> None:
        self._config("pdk.json", {"variant": "a", "search_roots": ["/x"]})
        self._config("pdk.local.json", {"variant": "b"})
        self.assertEqual(pdk._load_config(), {"variant": "b", "search_roots": ["/x"]})

    def test_invalid_json_raises_naming_file(self) -> None:
        (self.sim_dir / "pdk.local.json").write_text("{not json")
        with self.assertRaises(RuntimeError) as ctx:
            pdk._load_config()
        self.assertIn("pdk.local.json", str(ctx.exception))


class PdkDataclassTest(PdkTestBase):
    def test_version_reads_marker_and_defaults_unknown(self) -> None:
        variant = _make_variant(self.tmp / "root")
        p = pdk.Pdk(path=variant, variant="ihp-sg13g2", source="t")
        self.assertEqual(p.version, "unknown")
        (variant / ".fetched-version").write_text("  0.3.0\n")
        self.assertEqual(p.version, "0.3.0")
        (variant / ".fetched-version").write_text("\n")
        self.assertEqual(p.version, "unknown")

    def test_missing_osdi(self) -> None:
        variant = _make_variant(self.tmp / "root")
        p = pdk.Pdk(path=variant, variant="ihp-sg13g2", source="t")
        self.assertEqual(p.missing_osdi(), list(pdk.REQUIRED_OSDI))
        p.osdi_dir.mkdir(parents=True)
        (p.osdi_dir / "psp103.osdi").write_text("")
        self.assertNotIn("psp103.osdi", p.missing_osdi())


if __name__ == "__main__":
    unittest.main()

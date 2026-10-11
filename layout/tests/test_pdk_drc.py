"""Tests for layout/comparator/pdk_drc.py and its committed report (issue #180).

stdlib only; the deck itself is not run here (it needs the PDK and a real
KLayout executable). Covered: missing prerequisites are `unavailable` and never
clean, the lyrdb parser, and the committed report's invariants against the
committed GDS. Same stand-in loading trick as test_erc_tool.py.
"""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[1]
TOOL = LAYOUT / "comparator" / "pdk_drc.py"
REPORT = LAYOUT / "comparator" / "pdk_drc_report.json"
GDS = LAYOUT / "comparator" / "comparator.gds"


def _load():
    try:
        import klayout.db  # noqa: F401
        standin = False
    except ImportError:
        standin = True
    path_before = list(sys.path)
    mods_before = set(sys.modules)
    if standin:
        pkg = types.ModuleType("klayout")
        pkg.__path__ = []
        db = types.ModuleType("klayout.db")
        pkg.db = db
        sys.modules["klayout"] = pkg
        sys.modules["klayout.db"] = db
    try:
        spec = importlib.util.spec_from_file_location("pdk_drc_under_test", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if standin:
            for name in ("klayout", "klayout.db"):
                sys.modules.pop(name, None)
            for name in set(sys.modules) - mods_before:
                if name == "common_sg13g2":
                    sys.modules.pop(name, None)
            sys.path[:] = path_before
    return mod


pd = _load()

LYRDB = """<?xml version="1.0" encoding="utf-8"?>
<report-database><categories>
<category><name>Gat.c</name><description>end cap</description></category>
<category><name>pSD.b</name><description>pSD  space</description></category>
</categories><items>
<item><category>'pSD.b'</category><values><value>edge-pair: (1,2;3,4)|(5,6;7,8)</value></values></item>
<item><category>'pSD.b'</category><values><value>edge-pair: (0,0;1,1)|(2,2;3,3)</value></values></item>
</items></report-database>
"""


class Unavailable(unittest.TestCase):
    def test_missing_pdk(self):
        with tempfile.TemporaryDirectory() as td:
            env = {k: v for k, v in os.environ.items() if k not in ("IHP_PDK_DIR", "PDK_ROOT")}
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(Path, "home", return_value=Path(td)):
                with self.assertRaises(pd.Unavailable) as cm:
                    pd.find_pdk(td)
        self.assertEqual(cm.exception.reason, "pdk_deck_missing")

    def test_wrong_deck_identity(self):
        with tempfile.TemporaryDirectory() as td:
            pdk = Path(td)
            (pdk / pd.DECK_REL).mkdir(parents=True)
            (pdk / pd.DECK_REL / "run_drc.py").write_text("")
            (pdk / ".fetched-version").write_text("9.9.9\n")
            with self.assertRaises(pd.Unavailable) as cm:
                pd.resolve_prereqs(str(pdk), None)
            self.assertEqual(cm.exception.reason, "deck_identity_mismatch")

    def test_tampered_deck_tree(self):
        with tempfile.TemporaryDirectory() as td:
            pdk = Path(td)
            (pdk / pd.DECK_REL).mkdir(parents=True)
            (pdk / pd.DECK_REL / "run_drc.py").write_text("tampered")
            (pdk / ".fetched-version").write_text(pd.PDK_FETCHED_VERSION + "\n")
            with self.assertRaises(pd.Unavailable) as cm:
                pd.resolve_prereqs(str(pdk), None)
            self.assertEqual(cm.exception.reason, "deck_identity_mismatch")

    def test_missing_klayout_binary(self):
        with self.assertRaises(pd.Unavailable) as cm:
            pd.klayout_version("/nonexistent/klayout")
        self.assertEqual(cm.exception.reason, "klayout_binary_missing")


class Parse(unittest.TestCase):
    def test_lyrdb(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.lyrdb"
            p.write_text(LYRDB)
            executed, violations = pd.parse_lyrdb(p)
        self.assertEqual(set(executed), {"Gat.c", "pSD.b"})
        self.assertEqual(executed["pSD.b"], "pSD space")
        self.assertEqual(list(violations), ["pSD.b"])
        self.assertEqual(len(violations["pSD.b"]), 2)


class CommittedReport(unittest.TestCase):
    def setUp(self):
        self.r = json.loads(REPORT.read_text())

    def test_identity_matches_committed_gds(self):
        self.assertEqual(self.r["gds"]["sha256"], hashlib.sha256(GDS.read_bytes()).hexdigest())
        self.assertEqual(self.r["deck"]["tree_sha256"], pd.DECK_TREE_SHA256)
        self.assertEqual(self.r["deck"]["release_tag"], pd.PDK_RELEASE_TAG)

    def test_status_is_consistent_with_findings(self):
        n = self.r["rules"]["violation_count"]
        self.assertEqual(n, sum(v["count"] for v in self.r["rules"]["violated"]))
        self.assertEqual(self.r["status"], "violations" if n else "clean")
        self.assertIn(self.r["status"], ("clean", "violations"))  # never unavailable

    def test_targeted_rules_executed_and_listed(self):
        got = {t["rule"]: t for t in self.r["rules"]["targeted"]}
        self.assertEqual(set(got), set(pd.TARGETED))
        for rule, t in got.items():
            self.assertTrue(t["executed"], rule)

    def test_negative_controls_detected(self):
        self.assertTrue(self.r["negative_controls"])
        for x in self.r["negative_controls"]:
            self.assertEqual(x["result"], "fails_as_expected", x)
            self.assertEqual(x["committed_violations_of_rule"], 0, x)

    def test_portable_and_declares_skips(self):
        text = REPORT.read_text()
        self.assertNotIn("/home/", text)
        self.assertNotIn("/tmp/", text)
        self.assertTrue(self.r["skipped"])
        self.assertTrue(self.r["not_covered"])


if __name__ == "__main__":
    unittest.main()

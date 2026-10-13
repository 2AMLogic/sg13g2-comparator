"""Tests for layout/comparator/pdk_drc.py and its committed report (issue #180).

stdlib only; the deck itself is not run here (it needs the PDK and a real
KLayout executable). Covered: missing prerequisites are `unavailable` and never
clean, the lyrdb parser, and the committed report's invariants against the
committed GDS. Same stand-in loading trick as test_erc_tool.py.
"""

import hashlib
import importlib.util
import io
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


def full_inventory(drop=()):
    """{rule: description} for every category the pinned deck must emit."""
    return {r: f"d {r}" for rules in pd.REQUIRED_CATEGORIES.values()
            for r in rules if r not in drop}


# A stand-in for the PDK's run_drc.py (issue #253). It reads fake_deck.json
# beside itself, picks the behaviour for the layout's stem (else "default"),
# writes the merged lyrdb and per-rule-set logs under run_drc.py's own naming,
# prints the verdict line and exits with the configured status.
FAKE_DECK = r'''
import json, pathlib, sys
from xml.sax.saxutils import escape
args = dict(a[2:].split("=", 1) for a in sys.argv[1:] if "=" in a)
conf = json.loads((pathlib.Path(__file__).parent / "fake_deck.json").read_text())
stem = pathlib.Path(args["path"]).resolve().stem
c = conf.get(stem, conf["default"])
run = pathlib.Path(args["run_dir"]); run.mkdir(parents=True, exist_ok=True)
pre = f"{stem}_{args['topcell']}"
if c.get("write_db", True):
    cats = "".join(f"<category><name>{escape(n)}</name><description>d</description></category>"
                   for n in c["categories"])
    items = "".join(f"<item><category>'{escape(n)}'</category><values><value>{escape(v)}</value>"
                    "</values></item>" for n, v in c.get("items", []))
    (run / f"{pre}_full.lyrdb").write_text(
        f"<report-database><categories>{cats}</categories><cells/><items>{items}</items></report-database>")
for s in c.get("logs", ["main", "sg13g2_maximal"]):
    (run / f"{pre}_{s}.log").write_text(f"KLayout DRC run for tables '{s}' completed in 1.0 seconds\n")
if c.get("verdict"):
    print(c["verdict"], file=sys.stderr)
sys.exit(c["rc"])
'''


def deck_conf(categories=None, items=(), rc=None, verdict=True, **kw):
    """Behaviour of one fake deck run; defaults are a complete, honest run."""
    categories = sorted(full_inventory()) if categories is None else list(categories)
    items = [list(i) for i in items]
    rc = (1 if items else 0) if rc is None else rc
    v = pd.DECK_VERDICT.get(1 if items else 0) if verdict is True else verdict
    return dict(categories=categories, items=items, rc=rc, verdict=v, **kw)


class FakeDeck(unittest.TestCase):
    """run_deck/main end to end against a fake run_drc.py; no PDK, no KLayout."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        self.pdk = self.td / "pdk"
        (self.pdk / pd.DECK_REL).mkdir(parents=True)
        (self.pdk / pd.DECK_REL / "run_drc.py").write_text(FAKE_DECK)
        self.gds = self.td / "comparator.gds"
        self.gds.write_bytes(b"not really a stream")
        self.out = self.td / "report.json"
        self.out.write_text("KEEP")
        self.n = 0
        # Controls: each mutated copy trips its own rule.
        self.conf = {f"broken_{k.replace('.', '_')}": deck_conf(items=[(k, "edge-pair: x")])
                     for k in pd.CONTROLS}

    def tearDown(self):
        self._td.cleanup()

    def configure(self, **default):
        self.conf["default"] = default
        (self.pdk / pd.DECK_REL / "fake_deck.json").write_text(json.dumps(self.conf))

    def run_deck(self):
        self.n += 1
        return pd.run_deck(self.pdk, sys.executable, self.gds, self.td / f"w{self.n}")

    def main(self, *flags):
        args = ["pdk_drc.py", str(self.gds), "-o", str(self.out), *flags]
        with mock.patch.object(sys, "argv", args), \
             mock.patch.object(pd, "resolve_prereqs",
                               return_value=(self.pdk, sys.executable, "0.30.12", "0.3.0", "t")), \
             mock.patch.object(pd, "drawn_layers", return_value=[]), \
             mock.patch.object(pd, "broken_copy", side_effect=lambda g, o, k: o.write_bytes(g.read_bytes())), \
             mock.patch("sys.stdout", new=io.StringIO()), \
             mock.patch("sys.stderr", new=io.StringIO()) as err:
            rc = pd.main()
        return rc, err.getvalue()

    # -- accepted runs ------------------------------------------------------ #
    def test_complete_zero_marker_run_is_clean(self):
        self.configure(**deck_conf())
        executed, violations = self.run_deck()
        self.assertEqual(set(executed), set(full_inventory()))
        self.assertEqual(violations, {})
        for flags in ((), ("--no-controls",), ("--strict",)):
            self.out.write_text("KEEP")
            rc, err = self.main(*flags)
            self.assertEqual(rc, 0, (flags, err))
            r = json.loads(self.out.read_text())
            self.assertEqual(r["status"], "clean")
            self.assertEqual(r["rules"]["executed_count"], len(full_inventory()))
            if "--no-controls" not in flags:
                self.assertTrue(all(x["result"] == "fails_as_expected" for x in r["negative_controls"]))

    def test_extra_categories_are_accepted(self):
        cats = sorted(full_inventory()) + ["M2.a", "OffGrid.Metal1"]
        self.configure(**deck_conf(categories=cats))
        executed, _ = self.run_deck()
        self.assertIn("M2.a", executed)

    def test_violations_keep_strict_semantics(self):
        self.configure(**deck_conf(items=[("pSD.b", "edge-pair: a"), ("pSD.b", "edge-pair: b")]))
        _, violations = self.run_deck()
        self.assertEqual(len(violations["pSD.b"]), 2)
        rc, err = self.main("--no-controls")
        self.assertEqual(rc, 0, err)
        self.assertEqual(json.loads(self.out.read_text())["status"], "violations")
        rc, err = self.main("--no-controls", "--strict")
        self.assertEqual(rc, 1, err)
        self.assertEqual(json.loads(self.out.read_text())["status"], "violations")

    # -- refused runs ------------------------------------------------------- #
    def assertRefused(self, exc, **conf):
        self.configure(**conf)
        with self.assertRaises(exc):
            self.run_deck()
        for flags in (("--no-controls",), (), ("--check",)):
            self.out.write_text("KEEP")
            rc, err = self.main(*flags)
            self.assertEqual(rc, 1, flags)
            self.assertIn("nothing written", err, flags)
            self.assertEqual(self.out.read_text(), "KEEP", flags)

    def test_nonzero_exit_with_plausible_files_refused(self):
        self.assertRefused(pd.IncompleteRun, **deck_conf(rc=1, verdict=None))
        self.assertRefused(pd.IncompleteRun, **deck_conf(rc=1, verdict=pd.DECK_VERDICT[0]))

    def test_unexpected_exit_status_refused(self):
        for rc in (2, -9, 127):
            self.assertRefused(pd.IncompleteRun, **deck_conf(rc=rc))
            self.assertRefused(pd.IncompleteRun, **deck_conf(rc=rc, items=[("pSD.b", "x")]))

    def test_exit_zero_with_markers_refused(self):
        self.assertRefused(pd.IncompleteRun, **deck_conf(rc=0, items=[("pSD.b", "x")]))

    def test_violations_without_deck_verdict_refused(self):
        self.assertRefused(pd.IncompleteRun, **deck_conf(items=[("pSD.b", "x")], verdict=None))

    def test_clean_without_deck_verdict_refused(self):
        self.assertRefused(pd.IncompleteRun, **deck_conf(verdict=None))

    def test_empty_inventory_refused(self):
        self.assertRefused(pd.MalformedReport, **deck_conf(categories=[]))

    def test_missing_required_category_refused(self):
        for rule_set, rules in pd.REQUIRED_CATEGORIES.items():
            drop = (rules[len(rules) // 2],)
            self.assertRefused(pd.IncompleteRun, **deck_conf(categories=sorted(full_inventory(drop))))

    def test_missing_rule_set_refused(self):
        main_only = pd.REQUIRED_CATEGORIES["main"]
        self.assertRefused(pd.IncompleteRun, **deck_conf(categories=main_only))
        self.assertRefused(pd.IncompleteRun, **deck_conf(logs=["main"]))
        self.assertRefused(pd.IncompleteRun, **deck_conf(write_db=False))

    def test_incomplete_control_run_refused(self):
        self.conf["broken_Gat_c"] = deck_conf(categories=pd.REQUIRED_CATEGORIES["main"],
                                              items=[("M1.a", "x")])
        self.configure(**deck_conf())
        rc, err = self.main()
        self.assertEqual(rc, 1)
        self.assertIn("incomplete deck run", err)
        self.assertEqual(self.out.read_text(), "KEEP")

    def test_build_report_refuses_partial_inventory(self):
        with mock.patch.object(pd, "drawn_layers", return_value=[]):
            for executed in ({}, {"pSD.b": "d"}, full_inventory(drop=("Gat.c",))):
                with self.assertRaises(pd.IncompleteRun):
                    pd.build_report(GDS, executed, {}, "0", "v", "t", [])


class Contract(unittest.TestCase):
    def test_required_categories_shape(self):
        main, maximal = pd.REQUIRED_CATEGORIES["main"], pd.REQUIRED_CATEGORIES["sg13g2_maximal"]
        self.assertEqual(len(set(main)), len(main))
        self.assertEqual(len(set(maximal)), len(maximal))
        self.assertFalse(set(main) & set(maximal))  # the merged lyrdb rejects duplicates
        # Rules the report and controls rely on are all mandatory emissions.
        self.assertLessEqual(set(pd.TARGETED) | set(pd.CONTROLS), set(main) | set(maximal))


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

    def _parse(self, xml):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.lyrdb"
            p.write_text(xml)
            return pd.parse_lyrdb(p)

    @staticmethod
    def _doc(cats="<category><name>pSD.b</name></category>", items="", wrap=True):
        c = f"<categories>{cats}</categories>" if cats is not None else ""
        i = f"<items>{items}</items>" if items is not None else ""
        return f"<report-database>{c}{i}</report-database>"

    def test_multi_value_item_is_one_marker(self):
        item = ("<item><category>'pSD.b'</category><values>"
                "<value>polygon: (0,0;1,1)</value><value>text: ('x',0,0)</value>"
                "</values></item>")
        _, v = self._parse(self._doc(items=item))
        self.assertEqual(len(v["pSD.b"]), 1)
        self.assertEqual(v["pSD.b"][0], ["polygon: (0,0;1,1)", "text: ('x',0,0)"])

    def test_empty_values_fails(self):
        for body in ("<values/>", "<values><value> </value></values>", ""):
            item = f"<item><category>'pSD.b'</category>{body}</item>"
            with self.assertRaises(pd.MalformedReport, msg=body):
                self._parse(self._doc(items=item))

    def test_structure_errors_fail(self):
        ok = "<item><category>'pSD.b'</category><values><value>a</value></values></item>"
        cases = {
            "no categories": self._doc(cats=None, items=ok),
            "no items": self._doc(items=None),
            "blank category name": self._doc(cats="<category><name> </name></category>"),
            "duplicate category": self._doc(cats="<category><name>pSD.b</name></category>" * 2),
            "undeclared item category": self._doc(items=ok.replace("pSD.b", "M1.a")),
            "blank item category": self._doc(items=ok.replace("'pSD.b'", "")),
            "not xml": "<report-database>",
        }
        for label, xml in cases.items():
            with self.assertRaises(pd.MalformedReport, msg=label):
                self._parse(xml)

    def test_no_items_is_clean(self):
        ex, v = self._parse(self._doc(items=""))
        self.assertEqual(v, {})
        self.assertEqual(set(ex), {"pSD.b"})

    def test_empty_categories_fails(self):
        with self.assertRaises(pd.MalformedReport):
            self._parse(self._doc(cats="", items=""))

    def test_report_counts_items_not_values(self):
        markers = {"pSD.b": [["a", "b"], ["c"]]}
        with mock.patch.object(pd, "drawn_layers", return_value=[]):
            r = pd.build_report(GDS, full_inventory(), markers, "0", "v", "t", [])
        self.assertEqual(r["rules"]["violation_count"], 2)
        self.assertEqual(r["rules"]["violated"][0]["count"], 2)
        self.assertEqual(r["rules"]["violated"][0]["markers"], [["a", "b"], ["c"]])
        self.assertEqual(r["status"], "violations")

    def test_malformed_run_leaves_report_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "r.json"
            out.write_text("KEEP")
            args = ["pdk_drc.py", str(GDS), "-o", str(out), "--no-controls"]
            with mock.patch.object(sys, "argv", args), \
                 mock.patch.object(pd, "resolve_prereqs", return_value=(Path(td), "kl", "1", "fv", "t")), \
                 mock.patch.object(pd, "run_deck", side_effect=pd.MalformedReport("bad")):
                rc = pd.main()
            self.assertEqual(rc, 1)
            self.assertEqual(out.read_text(), "KEEP")


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

    def test_inventory_covers_required_categories(self):
        required = sum(len(r) for r in pd.REQUIRED_CATEGORIES.values())
        self.assertGreaterEqual(self.r["rules"]["executed_count"], required)

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

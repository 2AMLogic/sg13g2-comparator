"""Tests for layout/comparator/erc_tool.py judge/build_spec/main (issue #117).

stdlib only. erc_tool imports ``klayout.db`` at module load but touches it
only inside ``mutate()``; when real klayout is absent, empty stand-in modules
are installed for the import and removed again in a ``finally`` so nothing
else in the process sees a fake klayout. ``mutate`` is out of scope.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[1]
TOOL = LAYOUT / "comparator" / "erc_tool.py"
COMMITTED = LAYOUT / "comparator" / "erc_report.json"

_STANDINS = ("klayout", "klayout.db")


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
        spec = importlib.util.spec_from_file_location("erc_tool_under_test", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if standin:
            for name in _STANDINS:
                sys.modules.pop(name, None)
            # common_sg13g2 got bound to the stand-in; do not leave it behind.
            for name in set(sys.modules) - mods_before:
                if name == "common_sg13g2":
                    sys.modules.pop(name, None)
            sys.path[:] = path_before
    return mod, standin


erc, USED_STANDIN = _load()
c = erc.c

WANT = [
    'erc.net_connectivity:["vdd"]',
    'erc.net_connectivity:["vss"]',
    'erc.net_connectivity:["vbias"]',
    'erc.missing_tie:["nwell_vdd"]',
]


def clean_envelope():
    return {
        "file": "layout/comparator/comparator.gds",
        "erc_findings": [],
        "erc_finding_count": 0,
        "erc_status": "clean",
        "erc_coverage": {"checked": list(WANT) + ['erc.floating_gate:["gate0"]'],
                         "skipped": []},
        "provenance": {"devices": []},
    }


class JudgeBase(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.dir = Path(td.name)

    def judge(self, env, expect=None):
        p = self.dir / "env.json"
        p.write_text(json.dumps(env))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = erc.judge(str(p), expect)
        return rc, out.getvalue(), err.getvalue()


class TestJudge(JudgeBase):
    def test_clean_envelope_passes(self):
        rc, out, _ = self.judge(clean_envelope())
        self.assertEqual(rc, 0)
        self.assertIn("erc_status: clean", out)

    def test_committed_report_passes(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = erc.judge(str(COMMITTED), None)
        self.assertEqual(rc, 0, err.getvalue())

    def test_status_not_clean_fails(self):
        e = clean_envelope()
        e["erc_status"] = "findings"
        rc, _, err = self.judge(e)
        self.assertEqual(rc, 1)
        self.assertIn("erc_status", err)

    def test_nonzero_finding_count_fails(self):
        e = clean_envelope()
        e["erc_finding_count"] = 1
        self.assertEqual(self.judge(e)[0], 1)

    def test_skipped_fails(self):
        e = clean_envelope()
        e["erc_coverage"]["skipped"] = [{"reason": "erc.something"}]
        rc, _, err = self.judge(e)
        self.assertEqual(rc, 1)
        self.assertIn("skipped", err)

    def test_each_missing_checked_item_fails(self):
        for item in WANT:
            with self.subTest(item=item):
                e = clean_envelope()
                e["erc_coverage"]["checked"].remove(item)
                rc, _, err = self.judge(e)
                self.assertEqual(rc, 1)
                self.assertIn("checked work missing", err)

    def test_error_key_fails(self):
        e = clean_envelope()
        e["error"] = "boom"
        rc, _, err = self.judge(e)
        self.assertEqual(rc, 1)
        self.assertIn("error/odd envelope", err)

    def test_missing_findings_key_fails(self):
        e = clean_envelope()
        del e["erc_findings"]
        rc, _, err = self.judge(e)
        self.assertEqual(rc, 1)
        self.assertIn("error/odd envelope", err)

    def test_absolute_file_fails(self):
        e = clean_envelope()
        e["file"] = "/tmp/x.gds"
        rc, _, err = self.judge(e)
        self.assertEqual(rc, 1)
        self.assertIn("host-absolute", err)

    def test_home_path_anywhere_fails(self):
        e = clean_envelope()
        e["spec"] = "/home/someone/spec.json"
        rc, _, err = self.judge(e)
        self.assertEqual(rc, 1)
        self.assertIn("host-absolute", err)

    def test_devices_carveout_fails(self):
        e = clean_envelope()
        e["provenance"]["devices"] = [{"name": "m1"}]
        rc, _, err = self.judge(e)
        self.assertEqual(rc, 1)
        self.assertIn("devices", err)


class TestJudgeExpect(JudgeBase):
    def test_expect_in_findings(self):
        e = clean_envelope()
        e["erc_findings"] = [{"rule": "erc.supply_short", "nets": ["vdd", "vss"]}]
        self.assertEqual(self.judge(e, "erc.supply_short")[0], 0)

    def test_expect_in_skipped_reason(self):
        e = clean_envelope()
        e["erc_coverage"]["skipped"] = [{"reason": "erc.degenerate_tap"}]
        self.assertEqual(self.judge(e, "erc.degenerate_tap")[0], 0)

    def test_expect_absent_fails(self):
        self.assertEqual(self.judge(clean_envelope(), "erc.supply_short")[0], 1)

    def test_expect_ignores_cleanliness(self):
        # a dirty envelope is the *point* of a negative control
        e = clean_envelope()
        e["erc_status"] = "findings"
        e["erc_findings"] = [{"id": "erc.open_supply"}]
        self.assertEqual(self.judge(e, "erc.open_supply")[0], 0)


class TestBuildSpec(unittest.TestCase):
    def test_nets(self):
        nets = {n["name"]: n["kind"] for n in erc.build_spec()["nets"]}
        self.assertEqual(nets, {"vdd": "supply", "vss": "supply", "vbias": "signal"})

    def test_default_single_tie(self):
        ties = erc.build_spec()["ties"]
        self.assertEqual([t["name"] for t in ties], ["nwell_vdd"])
        self.assertEqual(ties[0]["net"], "vdd")

    def test_substrate_adds_scratch_tie(self):
        ties = erc.build_spec(substrate=True)["ties"]
        self.assertEqual([t["name"] for t in ties], ["nwell_vdd", "psub_vss"])
        self.assertEqual(ties[1]["well_layer"], "200/0")
        self.assertEqual(ties[1]["net"], "vss")

    def test_layers_come_from_common_table(self):
        s = erc.build_spec()
        t = s["ties"][0]
        self.assertEqual(t["well_layer"], erc.lay(c.L_NWELL))
        self.assertEqual(t["tap_layer"], erc.lay(c.L_ACTIV))
        self.assertEqual(t["tap_requires"], [erc.lay(c.L_NSD), erc.lay(c.L_CONT)])
        stack = {e["name"]: e["layer"] for e in s["stackup"]}
        self.assertEqual(stack["Metal1"], erc.lay(c.L_METAL1))
        self.assertEqual(stack["GatPoly"], erc.lay(c.L_GATPOLY))
        vias = {v["name"]: v["layer"] for v in s["vias"]}
        self.assertEqual(vias["Via2"], erc.lay(c.L_VIA2))

    def test_lay_format(self):
        self.assertEqual(erc.lay((8, 0)), "8/0")

    def test_dump_stable_and_newline_terminated(self):
        a, b = erc.dump(erc.build_spec()), erc.dump(erc.build_spec())
        self.assertEqual(a, b)
        self.assertTrue(a.endswith("}\n"))
        self.assertEqual(json.loads(a), erc.build_spec())


class TestMain(unittest.TestCase):
    def test_bogus_command_returns_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(erc.main(["bogus"]), 2)

    def test_spec_command_prints_dump(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(erc.main(["spec"]), 0)
        self.assertEqual(out.getvalue(), erc.dump(erc.build_spec()))


class TestStandinHygiene(unittest.TestCase):
    def test_standins_not_leaked(self):
        if USED_STANDIN:
            self.assertNotIn("klayout", sys.modules)
            self.assertNotIn("klayout.db", sys.modules)
            self.assertNotIn("common_sg13g2", sys.modules)


if __name__ == "__main__":
    unittest.main()

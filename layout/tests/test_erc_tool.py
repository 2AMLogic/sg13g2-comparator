"""Tests for layout/comparator/erc_tool.py judge/build_spec/main (issue #117).

stdlib only. erc_tool imports ``klayout.db`` at module load but touches it
only inside ``mutate()``; when real klayout is absent, empty stand-in modules
are installed for the import and removed again in a ``finally`` so nothing
else in the process sees a fake klayout -- see ``klayout_standin.load_tool``,
which both this module and test_pdk_drc.py share (issue #432). ``mutate`` is
out of scope.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Importing the sibling helper needs layout/tests on sys.path. unittest
# discovery inserts the start directory itself, but `python3 -I` implies -P
# (3.11+), so a direct `python3 -I layout/tests/<file>` run -- and
# pinned_deck_contract.py loading this module by path -- does not get it.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import klayout_standin  # noqa: E402

LAYOUT = Path(__file__).resolve().parents[1]
TOOL = LAYOUT / "comparator" / "erc_tool.py"
COMMITTED = LAYOUT / "comparator" / "erc_report.json"

erc, USED_STANDIN = klayout_standin.load_tool(TOOL, "erc_tool_under_test")
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

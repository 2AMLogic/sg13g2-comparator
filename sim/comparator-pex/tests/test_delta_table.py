"""Issue #181: make_delta_table.py keeps raw availability, grades only mapped keys."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PEX = REPO / "sim/comparator-pex"
sys.dont_write_bytecode = True
sys.path.insert(0, str(PEX))
import make_delta_table as mdt  # noqa: E402

ENVELOPE = REPO / "layout/comparator/pex_report.json"
TT, SS = "tt/1.200V/27C", "ss/1.080V/125C"


def row(spec, corner, s, x, status="pass"):
    return {"spec_row": spec, "corner_id": corner, "schematic_value": s,
            "extracted_value": x, "delta_pct": None, "status": status}


def by(out):
    return {(r["spec_row"], r["corner_id"]): r for r in out["rows"]}


class CommittedEnvelope(unittest.TestCase):
    def test_nominal(self):
        env = mdt.load(ENVELOPE)
        out, md = mdt.render(env, ENVELOPE)
        rows = by(out)
        dc = rows["regeneration.nominal.dc_first", TT]
        self.assertEqual(dc["delta_pct"], 30126069.28)  # raw kept
        self.assertEqual(dc["status"], "pass")
        i = dc["interpretation"]
        self.assertEqual((i["schematic_state"], i["extracted_state"], i["state_change"]), ("low", "high", True))
        self.assertIn("WRONG STATE", i["verdict"])
        self.assertNotIn("30126069", md)
        self.assertEqual(rows["regeneration.nominal.td_a", TT]["interpretation"]["verdict"], "EXCEEDS")
        self.assertIn("NOT MET", out["delay_compliance_extracted"]["regeneration.td_a"])
        td_c = rows["regeneration.nominal.td_c", TT]
        self.assertEqual((td_c["status"], td_c["extracted_value"]), ("error", None))
        self.assertEqual(td_c["interpretation"]["verdict"], "missing: no verdict")
        self.assertIsNone(rows["regeneration.nominal.td_b", TT]["interpretation"]["kind"])
        self.assertEqual(out["corners"], [TT])
        self.assertIn("1 corner(s); no Monte Carlo, no seeds; no sigma", out["statistical_basis"])
        self.assertEqual(len(out["rows"]), len(env["delta"]))


class Mapping(unittest.TestCase):
    def test_mapped_keys_match_staged_requests(self):
        cards = {("regeneration", "td_a"): "targ v(dan)", ("regeneration", "td_c"): "targ v(dcn)"}
        cards |= {k: ("at=18n" if v == "low" else "at=55n") for k, v in mdt.LOGIC.items()}
        for bench, key in [*mdt.DELAY, *mdt.LOGIC]:
            for var in ("nominal", "pvt"):
                req = json.loads((PEX / f"requests/{bench}.{var}.json").read_text())
                spice = {m["name"]: m["spice"] for m in req["measurements"]}[key]
                self.assertIn(cards[bench, key], spice)
                self.assertIn(f"v(d{key[1]}n)" if key[0] == "d" else "v(clkn)", spice)
        tb = (PEX / "dut/tb_regeneration.sp").read_text()
        for p in ("dv_big=50m", "dv_tiny=0.1m", "Bdan  dan  0 v = 'v(douta)/v(vdda)'"):
            self.assertIn(p, tb)


class Synthetic(unittest.TestCase):
    def render(self, rows):
        return mdt.render({"status": "error", "delta": rows}, "fixture")

    def test_multi_corner_logic_timing_missing_unknown(self):
        out, md = self.render([
            row("regeneration.pvt.td_a", TT, 7e-10, 1.4e-9),
            row("regeneration.pvt.td_a", SS, 8e-10, 1.6e-9),
            row("regeneration.pvt.td_a", "tt/1.500V/27C", 7e-10, 9e-9),
            row("regeneration.pvt.td_c", TT, 1e-9, None, "error"),
            row("regeneration.pvt.td_c", SS, None, None, "error"),
            row("regeneration.pvt.dc_first", SS, 0.99, 1e-6),
            row("regeneration.pvt.db_first", SS, 0.0, 0.5),
            row("kickback.pvt.da_end", SS, 1.0, 0.0),
            row("regeneration.pvt.offset_sigma", TT, 1e-3, 2e-3),
            row("other.pvt.td_a", TT, 1e-9, 9e-9),
        ])
        r = by(out)
        v = lambda k, c: r[k, c]["interpretation"]["verdict"]  # noqa: E731
        self.assertEqual(v("regeneration.pvt.td_a", TT), "within")
        self.assertEqual(v("regeneration.pvt.td_a", SS), "EXCEEDS")
        self.assertIn("outside", v("regeneration.pvt.td_a", "tt/1.500V/27C"))
        self.assertEqual(v("regeneration.pvt.td_c", SS), "missing: no verdict")
        self.assertEqual(r["regeneration.pvt.td_c", SS]["availability"], "neither leg measured")
        self.assertEqual(r["regeneration.pvt.td_c", TT]["availability"], "extracted missing")
        self.assertEqual(v("regeneration.pvt.dc_first", SS), "correct (expected low)")
        self.assertEqual(v("regeneration.pvt.db_first", SS), "indeterminate (expected low)")
        self.assertEqual(v("kickback.pvt.da_end", SS), "WRONG STATE (expected high)")
        for k in ("regeneration.pvt.offset_sigma", "other.pvt.td_a"):
            self.assertEqual(v(k, TT), "ungraded (no mapped criterion)")
        s = out["delay_compliance_extracted"]
        self.assertTrue(s["regeneration.td_a"].startswith("NOT MET: extracted exceeds at 1"))
        self.assertTrue(s["regeneration.td_c"].startswith("not established: 0/45"))
        self.assertEqual((len(out["corners"]), out["pvt_grid_points"]), (3, 2))
        self.assertIn("3 corner(s)", out["statistical_basis"])
        self.assertNotIn("sigma", md.replace("no sigma", "").replace("offset_sigma", ""))

    def test_full_grid_met_only_when_complete(self):
        grid = [f"{p}/{v:.3f}V/{t}C" for p in mdt.GRID[0] for v in (1.08, 1.2, 1.32) for t in (-40, 27, 125)]
        rows = [row("regeneration.pvt.td_a", c, 7e-10, 1e-9) for c in grid]
        self.assertTrue(self.render(rows)[0]["delay_compliance_extracted"]["regeneration.td_a"]
                        .startswith("met at every"))
        rows[0]["extracted_value"] = None
        self.assertTrue(self.render(rows)[0]["delay_compliance_extracted"]["regeneration.td_a"]
                        .startswith("not established: 44/45"))

    def grid(self):
        return [(p, v, t) for p in sorted(mdt.GRID[0]) for v in ("1.08", "1.2", "1.32") for t in (-40, 27, 125)]

    def test_45_spellings_of_one_point_rejected(self):
        rows = [row("regeneration.pvt.td_a", "tt/1.2" + "0" * n + "V/27C", 7e-10, 1e-9) for n in range(45)]
        with self.assertRaisesRegex(ValueError, "repeats the physical point"):
            self.render(rows)
        # the same spellings on an unmapped key are not graded, and count as one physical point
        out, _ = self.render([row("regeneration.pvt.offset_sigma", c["corner_id"], 1, 1) for c in rows])
        self.assertEqual(out["pvt_grid_points"], 1)
        self.assertIn("at 1 corner(s)", out["statistical_basis"])

    def test_distinct_spellings_cover_full_grid(self):
        # every point written with a different decimal spelling still counts once each
        rows = [row("regeneration.pvt.td_a", f"{p}/{v}{'0' * (i % 4)}V/{t}C", 7e-10, 1e-9)
                for i, (p, v, t) in enumerate(self.grid())]
        out, _ = self.render(rows)
        self.assertTrue(out["delay_compliance_extracted"]["regeneration.td_a"].startswith("met at every"))
        self.assertEqual(out["pvt_grid_points"], 45)

    def test_missing_point_not_full_grid(self):
        rows = [row("regeneration.pvt.td_a", f"{p}/{v}V/{t}C", 7e-10, 1e-9) for p, v, t in self.grid()]
        out, _ = self.render(rows[1:] + [row("regeneration.pvt.td_a", "tt/1.5V/27C", 7e-10, 1e-9)])
        self.assertTrue(out["delay_compliance_extracted"]["regeneration.td_a"].startswith("not established: 44/45"))
        self.assertEqual(out["pvt_grid_points"], 44)

    def test_nominal_pvt_alias_rejected(self):
        for ex in (1e-9, 9e-9):  # contradictory or identical evidence: both ambiguous
            with self.subTest(ex=ex), self.assertRaisesRegex(ValueError, "repeats the physical point"):
                self.render([row("regeneration.nominal.td_a", "tt/1.200V/27C", 7e-10, 1e-9),
                             row("regeneration.pvt.td_a", "tt/1.2V/27C", 7e-10, ex)])
        self.render([row("regeneration.nominal.td_a", TT, 7e-10, 1e-9),  # different measurement: fine
                     row("regeneration.pvt.td_c", "tt/1.2V/27C", 7e-10, 1e-9)])

    def test_negative_delay_invalid(self):
        for corner in (TT, "tt/1.500V/27C"):  # in or out of grid
            with self.subTest(corner=corner), self.assertRaises(ValueError) as cm:
                self.render([row("regeneration.pvt.td_a", "ss/1.080V/125C", 7e-10, 1e-9),
                             row("regeneration.pvt.td_a", corner, 7e-10, -1e-9)])
            self.assertIn(f"delta[1]: regeneration.pvt.td_a @ {corner}", str(cm.exception))
            self.assertIn("negative", str(cm.exception))
        grid = [row("regeneration.pvt.td_a", f"{p}/{v}V/{t}C", 7e-10, 1e-9) for p, v, t in self.grid()]
        grid[7]["extracted_value"] = -1e-9
        with self.assertRaisesRegex(ValueError, "delta\\[7\\].*negative"):
            self.render(grid)

    def test_zero_delay_graded_against_upper_bound_only(self):
        out, _ = self.render([row("regeneration.pvt.td_a", TT, 7e-10, 0.0)])
        self.assertEqual(by(out)["regeneration.pvt.td_a", TT]["interpretation"]["verdict"], "within")

    def test_cli_negative_delay_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "env.json").write_text(json.dumps({"delta": [row("regeneration.pvt.td_a", TT, 1e-9, -1e-9)]}))
            res = subprocess.run([sys.executable, "-B", str(PEX / "make_delta_table.py"), str(d / "env.json"),
                                  str(d / "out")], capture_output=True, text=True, timeout=60)
            self.assertEqual(res.returncode, 2)
            self.assertIn(f"regeneration.pvt.td_a @ {TT}", res.stderr)
            self.assertEqual(sorted(p.name for p in d.iterdir()), ["env.json"])

    def test_malformed_rejected(self):
        good = row("regeneration.pvt.td_a", TT, 1e-9, 1e-9)
        bad = [{}, {"delta": []}, {"delta": "x"}, {"delta": [{"spec_row": "a.b"}]},
               {"delta": [good, dict(good)]}, {"delta": [dict(good, spec_row="td_a")]},
               {"delta": [dict(good, corner_id=None)]}]
        for k in ("schematic_value", "extracted_value", "delta_pct"):
            bad += [{"delta": [dict(good, **{k: x})]} for x in ("1", True, float("nan"), float("inf"))]
        for env in bad:
            with self.subTest(env=env), self.assertRaises(ValueError):
                mdt.render(env, "fixture")


class Cli(unittest.TestCase):
    def run_cli(self, src, stem):
        return subprocess.run([sys.executable, "-B", str(PEX / "make_delta_table.py"), str(src), str(stem)],
                              capture_output=True, text=True, timeout=60)

    def test_non_finite_json_and_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for token in ("NaN", "Infinity", "-Infinity"):
                src = d / "env.json"
                src.write_text('{"delta": [{"spec_row": "regeneration.n.td_a", "corner_id": "%s", '
                               '"schematic_value": %s, "extracted_value": 1e-9, "delta_pct": null, '
                               '"status": "pass"}]}' % (TT, token))
                res = self.run_cli(src, d / "out")
                self.assertEqual(res.returncode, 2, res.stderr)
                self.assertIn("non-finite", res.stderr)
                self.assertNotIn("Traceback", res.stderr)
                self.assertEqual(sorted(p.name for p in d.iterdir()), ["env.json"])
            (d / "old.md").write_text("evidence\n")
            res = self.run_cli(ENVELOPE, d / "old")
            self.assertEqual(res.returncode, 1)
            self.assertIn("refusing to overwrite", res.stderr)
            self.assertFalse((d / "old.json").exists())
            self.assertEqual((d / "old.md").read_text(), "evidence\n")
            self.assertEqual(self.run_cli(ENVELOPE, d / "new").returncode, 0)
            self.assertTrue((d / "new.json").exists() and (d / "new.md").exists())


if __name__ == "__main__":
    unittest.main()

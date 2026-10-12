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


def states(ch, pts, first=0.0, end=1.0, bench="regeneration", var="pvt"):
    """Decision-state rows for channel ch (a/c) at the given (proc, volts, temp) points."""
    return [r for p, v, t in pts for r in (row(f"{bench}.{var}.d{ch}_first", f"{p}/{v}V/{t}C", 0.0, first),
                                           row(f"{bench}.{var}.d{ch}_end", f"{p}/{v}V/{t}C", 1.0, end))]


def grid_pts():
    return [(p, v, t) for p in sorted(mdt.GRID[0]) for v in ("1.08", "1.2", "1.32") for t in (-40, 27, 125)]


def td_rows(key="td_a", ex=1e-9, pts=None):
    return [row(f"regeneration.pvt.{key}", f"{p}/{v}V/{t}C", 7e-10, ex) for p, v, t in (pts or grid_pts())]


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
        rows = [row("regeneration.pvt.td_a", c, 7e-10, 1e-9) for c in grid] + states("a", [
            (p, f"{v:.3f}", t) for p in mdt.GRID[0] for v in (1.08, 1.2, 1.32) for t in (-40, 27, 125)])
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
                for i, (p, v, t) in enumerate(self.grid())] + states("a", self.grid())
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


class DecisionValidity(unittest.TestCase):
    """Issue #240: in-bound delays only establish compliance with matching valid decision states."""

    def summ(self, rows, key="regeneration.td_a"):
        out, md = mdt.render({"status": "error", "delta": rows}, "fixture")
        return out, out["delay_compliance_extracted"][key], md

    def test_wrong_polarity_complete_grid_not_met(self):
        out, s, _ = self.summ(td_rows() + states("a", grid_pts(), first=1.0, end=0.0))
        self.assertTrue(s.startswith("not established: 45/45 grid points within"), s)
        self.assertNotIn("met at every", s)
        self.assertIn("wrong 90", s)
        v = by(out)["regeneration.pvt.td_a", "tt/1.08V/-40C"]["interpretation"]
        self.assertEqual(v["verdict"], "within")  # numeric comparison stays visible
        self.assertTrue(v["decision_validity"].startswith("decision state not valid"))
        self.assertEqual(len(out["delay_decision_validity"]["regeneration.td_a"]["invalid"]), 45)

    def test_correct_states_met_for_a_and_c(self):
        for ch in "ac":
            rows = td_rows(f"td_{ch}") + states(ch, grid_pts())
            _, s, _ = self.summ(rows, f"regeneration.td_{ch}")
            self.assertTrue(s.startswith("met at every PVT grid point"), s)

    def test_td_c_wrong_and_channels_not_mixed(self):
        rows = td_rows("td_c") + states("c", grid_pts(), first=1.0, end=0.0)
        self.assertTrue(self.summ(rows, "regeneration.td_c")[1].startswith("not established"))
        # correct a-channel states do not validate td_c
        rows = td_rows("td_c") + states("a", grid_pts())
        s = self.summ(rows, "regeneration.td_c")[1]
        self.assertTrue(s.startswith("not established") and "missing 90" in s, s)

    def test_missing_and_indeterminate_states(self):
        pts = grid_pts()
        rows = td_rows() + states("a", pts[1:]) + states("a", pts[:1], first=0.5, end=None)
        out, s, _ = self.summ(rows)
        self.assertTrue(s.startswith("not established: 45/45"), s)
        self.assertIn("indeterminate 1", s)
        self.assertIn("missing 1", s)
        inv = out["delay_decision_validity"]["regeneration.td_a"]["invalid"]
        self.assertEqual(inv[0]["corner"], "%s/%s/%d" % (pts[0][0], mdt.canonical("%s/%sV/%dC" % pts[0])[1], pts[0][2]))
        self.assertEqual(len(inv), 1)
        # an absent state row is reported with the measurement name
        rows = td_rows() + states("a", pts)[2:]
        out, s, _ = self.summ(rows)
        self.assertIn("missing 2", s)
        self.assertIn("regeneration.da_first missing (no row)",
                      out["delay_decision_validity"]["regeneration.td_a"]["invalid"][0]["reasons"])

    def test_order_and_spelling_do_not_matter(self):
        pts = grid_pts()
        rows = [row(f"regeneration.pvt.td_a", f"{p}/{v}{'0' * (i % 3)}V/{t}C", 7e-10, 1e-9)
                for i, (p, v, t) in enumerate(pts)]
        st = states("a", [(p, v + "0" * ((i + 1) % 3), t) for i, (p, v, t) in enumerate(pts)])
        st = [r for r in st if r["spec_row"].endswith("end")] + [r for r in st if r["spec_row"].endswith("first")]
        allr = st[::-1] + rows[::-1]
        self.assertTrue(self.summ(allr)[1].startswith("met at every"))

    def test_canonical_duplicate_state_still_rejected(self):
        rows = td_rows() + states("a", grid_pts()) + states("a", [("tt", "1.200", 27)], var="nominal")
        with self.assertRaisesRegex(ValueError, "repeats the physical point"):
            self.summ(rows)

    def test_kickback_states_do_not_validate(self):
        rows = td_rows() + states("a", grid_pts(), bench="kickback")
        s = self.summ(rows)[1]
        self.assertTrue(s.startswith("not established") and "missing 90" in s, s)

    def test_mixed_fixture(self):
        pts = grid_pts()
        rows = td_rows(pts=pts[:20]) + td_rows(ex=3e-9, pts=pts[20:21]) + td_rows(pts=pts[21:])
        rows += states("a", pts[:10]) + states("a", pts[10:20], first=1.0, end=0.0) + states("a", pts[20:])
        out, s, md = self.summ(rows)
        self.assertTrue(s.startswith("NOT MET: extracted exceeds at 1 corner(s)"), s)
        self.assertIn("decision states valid at 35/45", s)
        r = by(out)
        self.assertEqual(r["regeneration.pvt.td_a", "ss/1.32V/125C"]["interpretation"]["verdict"], "within")
        self.assertEqual(r["regeneration.pvt.td_a", "ss/1.32V/125C"]["extracted_value"], 1e-9)
        self.assertEqual(r["regeneration.pvt.td_a", "ff/1.08V/-40C"]["interpretation"]["verdict"], "within")
        self.assertIn("decision state not valid", md)
        # exceeding point with wrong states still reports the over-limit value
        rows = td_rows(ex=3e-9, pts=pts[:1]) + td_rows(pts=pts[1:]) + states("a", pts, first=1.0, end=0.0)
        out, s, _ = self.summ(rows)
        self.assertTrue(s.startswith("NOT MET"))

    def test_mapping_matches_staged_requests(self):
        for (bench, td), sts in mdt.TIMING_STATES.items():
            self.assertIn((bench, td), mdt.DELAY)
            ch = td[-1]
            self.assertEqual({k[1] for k in sts}, {f"d{ch}_first", f"d{ch}_end"})
            for var in ("nominal", "pvt"):
                req = json.loads((PEX / f"requests/{bench}.{var}.json").read_text())
                spice = {m["name"]: m["spice"] for m in req["measurements"]}
                self.assertIn(f"targ v(d{ch}n)", spice[td])
                for b, k in sts:
                    self.assertIn(f"v(d{ch}n)", spice[k])
                    self.assertEqual(b, bench)
        self.assertEqual(set(mdt.TIMING_STATES), set(mdt.DELAY))


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

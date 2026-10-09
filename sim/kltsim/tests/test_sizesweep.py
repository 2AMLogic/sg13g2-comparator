"""Regression tests for the issue #92 sizing-study helpers (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kltsim import build, grade, sizesweep
from kltsim.benches import KICKBACK, REGENERATION


class GeometryTests(unittest.TestCase):
    def body(self, **kw):
        return build.compose_body(KICKBACK, build.BATCH_OSDI_DIR, **kw)

    def test_no_override_body_has_no_geometry_marker(self):
        self.assertEqual(build.extract_geometry(self.body()), {})
        self.assertNotIn("GEOMETRY OVERRIDE", self.body())

    def test_override_changes_only_named_instances(self):
        text = self.body(geometry_overrides={"XM1.w": "8u", "XM2.w": "8u"})
        _p, _s, embedded = build.extract_dut_block(text)
        self.assertIn("XM1 np vinp tail vss sg13_lv_nmos w=8u l=0.34u", embedded)
        self.assertIn("XM2 nn vinn tail vss sg13_lv_nmos w=8u l=0.34u", embedded)
        base = build.extract_dut_block(self.body())[2].split("\n")
        new = embedded.split("\n")
        self.assertEqual([a for a, b in zip(base, new) if a != b].__len__(), 2)
        self.assertEqual(build.extract_geometry(text), {"XM1.w": "8u", "XM2.w": "8u"})

    def test_declared_sha_matches_embedded_and_base_is_recorded(self):
        text = self.body(geometry_overrides={"XM1.l": "0.5u"})
        _p, declared, embedded = build.extract_dut_block(text)
        self.assertEqual(declared, hashlib.sha256(embedded.encode()).hexdigest())
        base = build.load_dut_binding()["_netlist_path"].read_bytes()
        self.assertIn(f"base DUT (unmodified) sha256={hashlib.sha256(base).hexdigest()}", text)

    def test_unknown_instance_or_field_refused(self):
        for bad in ({"XNOPE.w": "1u"}, {"XM1.m": "2"}, {"XMBA.w": "1u"}):
            with self.assertRaises(build.BuildError):
                self.body(geometry_overrides=bad)

    def test_parse_geometry(self):
        self.assertEqual(build.parse_geometry(["XM1.w=8u"]), {"XM1.w": "8u"})
        with self.assertRaises(build.BuildError):
            build.parse_geometry(["XM1=8u"])

    def test_grade_accepts_declared_geometry_and_refuses_undeclared_edit(self):
        dut = grade.load_dut_reference() if hasattr(grade, "load_dut_reference") else None
        if dut is None:
            self.skipTest("no DutReference loader")
        text = self.body(geometry_overrides={"XM1.w": "8u"})
        ev = grade.BenchEvidence(name="kickback", body_text=text, envelopes=[])
        self.assertEqual(grade.check_dut(ev, dut), [])
        tampered = text.replace("XM1 np vinp tail vss sg13_lv_nmos w=8u", "XM1 np vinp tail vss sg13_lv_nmos w=9u")
        ev2 = grade.BenchEvidence(name="kickback", body_text=tampered, envelopes=[])
        self.assertTrue(grade.check_dut(ev2, dut))


class ScreenRequestTests(unittest.TestCase):
    def test_screen_grid_contains_binding_corner(self):
        req = build.compose_request(KICKBACK, "k.body.spice", "batch")
        out = json.loads(sizesweep.screen_request((json.dumps(req)).encode()))
        c = out["corners"]
        self.assertIn("mos_ff", c["process"])
        self.assertIn(1.32, c["supply_v"]["vsup"])
        self.assertIn(125, c["temperature_c"])
        self.assertEqual(len(c["process"]) * len(c["supply_v"]["vsup"]) * len(c["temperature_c"]), 18)

    def test_regeneration_screen_keeps_all_supply_keys(self):
        req = build.compose_request(REGENERATION, "r.body.spice", "batch")
        out = json.loads(sizesweep.screen_request(json.dumps(req).encode()))
        self.assertEqual(set(out["corners"]["supply_v"]), set(req["corners"]["supply_v"]))


# --------------------------------------------------------------------------- #
# issue #122: validated screening reduction (synthetic evidence, no simulator)
# --------------------------------------------------------------------------- #

BENCH_SPECS = {"kickback": KICKBACK, "regeneration": REGENERATION}
BINDING_LABEL = "ff_125c_1.32v"


def _meas_value(bench, m, supply, temp, overrides):
    if m.name in overrides:
        return overrides[m.name]
    if m.name == "temp_meas":
        return float(temp)
    if m.name in ("vdd_meas", "vdda_meas"):
        return supply
    if m.role == "gate":
        lim = m.limits or {}
        return 1.0 if "min" in lim else 0.0
    return 1.0


def _corner(bench, proc, supply, temp, status="pass", overrides=None):
    return {
        "corner_id": f"{proc}_{temp}_{supply}", "process": proc,
        "supply_v": {k: supply for k in bench.supply_keys}, "temperature_c": temp,
        "status": status, "monte_carlo": None, "diagnostics": [],
        "measurements": [{"name": m.name, "unit": m.unit, "status": "pass",
                          "value": _meas_value(bench, m, supply, temp, overrides or {})}
                         for m in bench.measurements],
    }


def _is_binding(c):
    return c["process"] == "mos_ff" and c["supply_v"][sorted(c["supply_v"])[0]] == 1.32 \
        and c["temperature_c"] == 125


def write_candidate(root: Path, name="x", geometry=None, mutate=None, geometry_by_bench=None,
                    full_grid_request=False):
    """Write scr_<name>/ with a self-consistent request/body/envelope/invocation
    chain per bench. ``mutate(bench_name, corners)`` edits the corner list."""
    sub = root / f"scr_{name}"
    sub.mkdir(parents=True)
    for bname, bench in BENCH_SPECS.items():
        geo = (geometry_by_bench or {}).get(bname, geometry)
        body = build.compose_body(bench, build.BATCH_OSDI_DIR, geometry_overrides=geo)
        (sub / f"{bname}.body.spice").write_text(body, encoding="utf-8")
        req = build.compose_request(bench, f"{bname}.body.spice", "batch")
        req_bytes = (json.dumps(req, indent=2) + "\n").encode()
        if not full_grid_request:
            req_bytes = sizesweep.screen_request(req_bytes)
        (sub / f"{bname}.request.json").write_bytes(req_bytes)
        corners = [_corner(bench, p, v, t) for p in sizesweep.SCREEN_PROCESSES
                   for v in sizesweep.SCREEN_SUPPLIES_V for t in sizesweep.SCREEN_TEMPERATURES_C]
        if mutate:
            mutate(bname, corners)
        env = {"status": "fail", "corner_count": len(corners), "corners": corners,
               "environment": {"netlist_source": "schematic"},
               "provenance": {"input": {"content_hash":
                                        "sha256:" + hashlib.sha256(body.encode()).hexdigest()}}}
        env_bytes = (json.dumps(env, indent=2) + "\n").encode()
        (sub / f"{bname}.envelope.json").write_bytes(env_bytes)
        (sub / f"{bname}.invocation.json").write_text(json.dumps({
            "tag": bname, "request_sha256": hashlib.sha256(req_bytes).hexdigest(),
            "envelope_sha256": hashlib.sha256(env_bytes).hexdigest()}), encoding="utf-8")
    return sub


class ScreeningReductionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def reduce(self, **kw):
        write_candidate(self.root, **kw)
        rows = sizesweep.screen(self.root)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def assertUnavailable(self, row, *metrics):
        for m in metrics:
            cell = row["metrics"][m]
            self.assertFalse(cell["available"], m)
            self.assertIsNone(cell["value"], m)

    def reasons(self, row, metric):
        return " | ".join(row["metrics"][metric]["rejections"])

    def test_expected_grid_is_the_18_point_screen_including_binding(self):
        self.assertEqual(len(sizesweep.EXPECTED_POINTS), 18)
        self.assertIn(("ff", 1.32, 125.0), sizesweep.EXPECTED_POINTS)

    def test_complete_successful_reduced_grid(self):
        row = self.reduce(geometry={"XM1.w": "8u", "XM2.w": "8u"})
        self.assertEqual(row["geometry"], {"XM1.w": "8u", "XM2.w": "8u"})
        self.assertEqual(row["geometry_problems"], [])
        for b in row["benches"].values():
            self.assertEqual((b["expected"], b["present"]), (18, 18))
            self.assertEqual((b["evidence_rejections"], b["missing_points"], b["notes"]), ([], [], []))
        for name, cell in row["metrics"].items():
            self.assertTrue(cell["available"], name)
            self.assertEqual(cell["rejections"], [], name)
            self.assertEqual(cell["valid"], cell["expected"], name)
        self.assertEqual(row["metrics"]["qkick_binding"]["value"], 1.0)
        self.assertEqual(row["metrics"]["qkick_binding"]["point"], BINDING_LABEL)
        self.assertAlmostEqual(row["metrics"]["p_avg_worst"]["value"], 1e6)  # W -> uW
        self.assertEqual(row["metrics"]["qkick_worst"]["valid"], 18)

    def test_failed_status_corner_cannot_count_or_supply_binding_charge(self):
        def mutate(bench, corners):
            if bench == "kickback":
                for c in corners:
                    if _is_binding(c):
                        c["status"] = "error"
                        for m in c["measurements"]:
                            if m["name"] == "qkick_fc":
                                m["value"] = 31.5  # plausible, passing gate
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_binding", "qkick_worst", "sigdep_worst")
        self.assertEqual(row["metrics"]["qkick_worst"]["valid"], 17)
        self.assertIn("status 'error'", self.reasons(row, "qkick_binding"))
        self.assertIn(BINDING_LABEL, self.reasons(row, "qkick_worst"))
        self.assertTrue(row["metrics"]["td01_worst"]["available"])  # other bench unaffected

    def test_missing_or_unknown_status_is_rejected(self):
        def mutate(bench, corners):
            if bench == "regeneration":
                corners[0]["status"] = None
                corners[1].pop("status")
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "td50_worst", "tau_worst", "p_avg_worst")
        self.assertEqual(row["metrics"]["td50_worst"]["valid"], 16)

    def test_limit_failure_status_is_a_valid_measurement(self):
        def mutate(bench, corners):
            for c in corners:
                c["status"] = "fail"  # Target limit missed, run itself succeeded
        row = self.reduce(mutate=mutate)
        self.assertTrue(all(c["available"] for c in row["metrics"].values()))

    def test_non_finite_values_cannot_supply_statistics(self):
        def mutate(bench, corners):
            if bench == "kickback":
                vals = {"qkick_fc": float("nan"), "kick_sigdep_uv": float("inf")}
                for c in corners[:2]:
                    for m in c["measurements"]:
                        if m["name"] in vals:
                            m["value"] = vals[m["name"]]
                for m in corners[2]["measurements"]:  # NaN gate
                    if m["name"] == "dout_1k_end":
                        m["value"] = float("nan")
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_worst", "sigdep_worst")
        self.assertEqual(row["metrics"]["qkick_worst"]["valid"], 15)
        text = self.reasons(row, "qkick_worst")
        self.assertIn("not finite", text)
        self.assertIn("decision gate", text)
        self.assertIn("not finite", self.reasons(row, "sigdep_worst"))

    def test_non_finite_binding_charge_is_unavailable(self):
        def mutate(bench, corners):
            if bench == "kickback":
                for c in corners:
                    if _is_binding(c):
                        for m in c["measurements"]:
                            if m["name"] == "qkick_fc":
                                m["value"] = float("-inf")
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_binding")

    def test_duplicate_pvt_entries_are_ambiguous_and_retained_as_reason(self):
        def mutate(bench, corners):
            if bench == "kickback":
                dup = json.loads(json.dumps(corners[4]))
                dup["corner_id"] += "_again"
                for m in dup["measurements"]:
                    if m["name"] == "qkick_fc":
                        m["value"] = 0.5
                corners.append(dup)
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_worst", "sigdep_worst")
        self.assertEqual(row["metrics"]["qkick_worst"]["valid"], 17)
        self.assertIn("ambiguous duplicate", self.reasons(row, "qkick_worst"))
        self.assertTrue(any("duplicate PVT result" in n for n in row["benches"]["kickback"]["notes"]))

    def test_duplicate_binding_point_withholds_binding_charge(self):
        def mutate(bench, corners):
            if bench == "kickback":
                corners.extend(json.loads(json.dumps([c for c in corners if _is_binding(c)])))
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_binding")

    def test_duplicate_measurement_names_are_rejected(self):
        def mutate(bench, corners):
            if bench == "kickback":
                m = next(m for m in corners[3]["measurements"] if m["name"] == "qkick_fc")
                corners[3]["measurements"].append(dict(m, value=0.1))
                g = next(m for m in corners[5]["measurements"] if m["name"] == "dout_1k_end")
                corners[5]["measurements"].append(dict(g))
                p = next(m for m in corners[6]["measurements"] if m["name"] == "vdd_meas")
                corners[6]["measurements"].append(dict(p))
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_worst")
        self.assertEqual(row["metrics"]["qkick_worst"]["valid"], 15)
        text = self.reasons(row, "qkick_worst")
        self.assertIn("duplicate measurement name qkick_fc", text)
        self.assertIn("duplicate measurement name dout_1k_end", text)
        self.assertIn("duplicate probe", text)
        self.assertEqual(row["metrics"]["sigdep_worst"]["valid"], 17)  # only the probe point

    def test_failed_decision_gate_withholds_binding_charge(self):
        def mutate(bench, corners):
            if bench == "kickback":
                for c in corners:
                    if _is_binding(c):
                        for m in c["measurements"]:
                            if m["name"] == "dout_1k_end":
                                m["value"] = 0.2
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_binding", "qkick_worst")
        self.assertIn("dout_1k_end", self.reasons(row, "qkick_binding"))
        self.assertTrue(row["metrics"]["sigdep_worst"]["available"])

    def test_probe_not_matching_corner_is_rejected(self):
        def mutate(bench, corners):
            if bench == "regeneration":
                for m in corners[0]["measurements"]:
                    if m["name"] == "temp_meas":
                        m["value"] = 99.0
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "p_avg_worst")
        self.assertIn("temperature probe", self.reasons(row, "p_avg_worst"))

    def test_regeneration_gates_are_per_metric(self):
        def mutate(bench, corners):
            if bench == "regeneration":
                for m in corners[0]["measurements"]:
                    if m["name"] == "dout_od50_end":
                        m["value"] = 0.0
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "td50_worst")
        for ok in ("td01_worst", "tau_worst", "p_avg_worst"):
            self.assertTrue(row["metrics"][ok]["available"], ok)
        self.assertEqual(row["metrics"]["td50_worst"]["required_gates"],
                         ["dout_od50_first", "dout_od50_end"])

    def test_missing_points_are_visible_against_expected_grid(self):
        def mutate(bench, corners):
            if bench == "regeneration":
                del corners[0:3]
        row = self.reduce(mutate=mutate)
        b = row["benches"]["regeneration"]
        self.assertEqual((b["expected"], b["present"]), (18, 15))
        self.assertEqual(len(b["missing_points"]), 3)
        self.assertUnavailable(row, "td01_worst", "tau_worst", "p_avg_worst")
        self.assertEqual(row["metrics"]["td01_worst"]["valid"], 15)
        self.assertTrue(row["metrics"]["qkick_worst"]["available"])

    def test_missing_binding_point_makes_binding_charge_unavailable(self):
        def mutate(bench, corners):
            if bench == "kickback":
                corners[:] = [c for c in corners if not _is_binding(c)]
        row = self.reduce(mutate=mutate)
        self.assertUnavailable(row, "qkick_binding")
        self.assertEqual(row["metrics"]["qkick_binding"]["present"], 0)
        self.assertIn(BINDING_LABEL, self.reasons(row, "qkick_binding"))

    def test_out_of_grid_and_monte_carlo_corners_are_noted_not_counted(self):
        def mutate(bench, corners):
            extra = _corner(BENCH_SPECS[bench], "mos_tt", 1.2, 27)
            mc = _corner(BENCH_SPECS[bench], "mos_tt", 1.08, -40)
            mc["monte_carlo"] = {"n": 1}
            corners.extend([extra, mc])
        row = self.reduce(mutate=mutate)
        for b in row["benches"].values():
            self.assertEqual(b["present"], 18)
            self.assertEqual(len(b["notes"]), 2)
        self.assertTrue(all(c["available"] for c in row["metrics"].values()))

    def test_empty_directory_reports_nothing_present(self):
        (self.root / "scr_empty").mkdir()
        row = sizesweep.screen(self.root)[0]
        self.assertEqual(row["benches"]["kickback"]["present"], 0)
        self.assertEqual(len(row["benches"]["kickback"]["missing_points"]), 18)
        self.assertTrue(all(not c["available"] for c in row["metrics"].values()))
        self.assertIn("no envelope present", row["benches"]["kickback"]["evidence_rejections"])

    # -- provenance -----------------------------------------------------------

    def tamper(self, fname, fn):
        write_candidate(self.root)
        path = self.root / "scr_x" / fname
        path.write_bytes(fn(path.read_bytes()))
        return sizesweep.screen(self.root)[0]

    def test_changed_body_fails_provenance(self):
        row = self.tamper("kickback.body.spice", lambda b: b + b"* edited\n")
        self.assertTrue(row["benches"]["kickback"]["evidence_rejections"])
        self.assertUnavailable(row, "qkick_binding", "qkick_worst", "sigdep_worst")
        self.assertEqual(row["benches"]["regeneration"]["evidence_rejections"], [])
        self.assertTrue(row["metrics"]["td01_worst"]["available"])

    def test_changed_request_fails_provenance(self):
        def edit(b):
            req = json.loads(b)
            req["analysis"] = {"kind": "tran", "args": "5p 10n"}
            return (json.dumps(req, indent=2) + "\n").encode()
        row = self.tamper("regeneration.request.json", edit)
        text = " ".join(row["benches"]["regeneration"]["evidence_rejections"])
        self.assertIn("request_sha256 mismatch", text)
        self.assertIn("analysis", text)
        self.assertUnavailable(row, "td50_worst", "p_avg_worst")

    def test_changed_envelope_or_invocation_fails_provenance(self):
        row = self.tamper("kickback.envelope.json", lambda b: b + b" ")
        self.assertIn("envelope_sha256 mismatch",
                      " ".join(row["benches"]["kickback"]["evidence_rejections"]))
        self.assertUnavailable(row, "qkick_binding")

    def test_missing_invocation_fails_provenance(self):
        write_candidate(self.root)
        (self.root / "scr_x" / "kickback.invocation.json").unlink()
        row = sizesweep.screen(self.root)[0]
        self.assertIn("invocation", " ".join(row["benches"]["kickback"]["evidence_rejections"]))
        self.assertUnavailable(row, "qkick_binding")

    def test_full_grid_request_is_not_accepted_as_screening(self):
        row = self.reduce(full_grid_request=True)
        text = " ".join(row["benches"]["kickback"]["evidence_rejections"])
        self.assertIn("corners", text)
        self.assertUnavailable(row, "qkick_binding", "qkick_worst")

    def test_mismatched_bench_geometries_cannot_be_attributed(self):
        row = self.reduce(geometry_by_bench={"kickback": {"XM1.w": "8u", "XM2.w": "8u"}})
        self.assertEqual(row["geometry"], {})
        self.assertIn("inconsistent candidate geometry", " ".join(row["geometry_problems"]))
        self.assertTrue(all(not c["available"] for c in row["metrics"].values()))
        md = sizesweep.render_markdown({"campaign": "c", "screen": [row], "full": []})
        self.assertIn("INCONSISTENT", md)

    def test_undeclared_dut_edit_is_rejected(self):
        write_candidate(self.root, geometry={"XM1.w": "8u"})
        path = self.root / "scr_x" / "kickback.body.spice"
        path.write_text(path.read_text().replace("XM1 np vinp tail vss sg13_lv_nmos w=8u",
                                                 "XM1 np vinp tail vss sg13_lv_nmos w=9u"), encoding="utf-8")
        row = sizesweep.screen(self.root)[0]
        self.assertTrue(row["benches"]["kickback"]["evidence_rejections"])
        self.assertUnavailable(row, "qkick_binding")

    # -- reporting ------------------------------------------------------------

    def test_markdown_shows_unavailable_not_numbers(self):
        def mutate(bench, corners):
            if bench == "kickback":
                for c in corners:
                    if _is_binding(c):
                        c["status"] = "error"
        write_candidate(self.root, mutate=mutate)
        result = {"campaign": "c", "screen": sizesweep.screen(self.root), "full": []}
        md = sizesweep.render_markdown(result)
        self.assertIn("unavailable (17/18 valid)", md)
        self.assertIn("unavailable (0/1 valid)", md)
        self.assertIn("| kickback | 18 | 18 |", md)
        self.assertNotIn("nan", md.lower().replace("unavailable", ""))
        json.dumps(grade.json_safe(result), allow_nan=False)

    def test_run_never_overwrites_a_different_committed_report(self):
        camp = self.root / "c1"
        camp.mkdir()
        write_candidate(camp)
        sizesweep.run("c1", self.root)
        sizesweep.run("c1", self.root)  # identical bytes: idempotent
        (camp / "sizesweep.md").write_text("historical", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            sizesweep.run("c1", self.root)
        self.assertEqual((camp / "sizesweep.md").read_text(), "historical")
        sizesweep.run("c1", self.root, report_name="sizesweep_validated")
        self.assertTrue((camp / "sizesweep_validated.json").is_file())


class FullGridRegressionTests(unittest.TestCase):
    """The reduced-grid allowance must not weaken the default full-grid checks."""

    def test_default_request_check_still_requires_the_full_grid(self):
        full = build.compose_request(KICKBACK, "kickback.body.spice", "batch")
        screened = json.loads(sizesweep.screen_request(json.dumps(full).encode()))
        self.assertEqual(grade.check_request_semantics(KICKBACK, "kickback", full), [])
        problems = grade.check_request_semantics(KICKBACK, "kickback", screened)
        self.assertTrue(any("corners" in p for p in problems))

    def test_screening_corners_are_compared_exactly(self):
        full = build.compose_request(KICKBACK, "kickback.body.spice", "batch")
        screened = json.loads(sizesweep.screen_request(json.dumps(full).encode()))
        want = sizesweep.screen_corners(KICKBACK)
        self.assertEqual(grade.check_request_semantics(KICKBACK, "kickback", screened, want), [])
        self.assertTrue(grade.check_request_semantics(KICKBACK, "kickback", full, want))
        bad = json.loads(json.dumps(screened))
        bad["corners"]["temperature_c"] = [27]
        self.assertTrue(grade.check_request_semantics(KICKBACK, "kickback", bad, want))
        # other contract fields stay enforced under the reduced grid
        bad2 = json.loads(json.dumps(screened))
        bad2["analysis"] = {"kind": "tran", "args": "1p 1n"}
        self.assertTrue(grade.check_request_semantics(KICKBACK, "kickback", bad2, want))

    def test_load_campaign_default_signature_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            ev = grade.load_campaign(Path(d))
            self.assertEqual(set(ev), set(grade._bench_names()))


if __name__ == "__main__":
    unittest.main()

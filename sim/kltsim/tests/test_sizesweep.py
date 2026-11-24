"""Regression tests for the issue #92 sizing-study helpers (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_param_override_read_back_from_body_header(self):
        self.assertEqual(build.extract_param_overrides(self.body()), {})
        text = self.body(param_overrides={"dut_ib": 1.5e-05})
        self.assertEqual(build.extract_param_overrides(text), {"dut_ib": "1.5e-05"})

    def test_candidate_identity_includes_dut_ib(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp)
            (sub / "kickback.body.spice").write_text(self.body(
                geometry_overrides={"XM1.w": "8u"}, param_overrides={"dut_ib": 1e-05}))
            (sub / "regeneration.body.spice").write_text(self.body(
                geometry_overrides={"XM1.w": "8u"}, param_overrides={"dut_ib": 1.5e-05}))
            _g, problems = sizesweep._geometry_report(sub, ("kickback", "regeneration"))
            self.assertTrue(problems)
            (sub / "regeneration.body.spice").write_text(self.body(
                geometry_overrides={"XM1.w": "8u"}, param_overrides={"dut_ib": 1e-05}))
            g, problems = sizesweep._geometry_report(sub, ("kickback", "regeneration"))
            self.assertEqual((g, problems), ({"XM1.w": "8u", "dut_ib": "1e-05"}, []))

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
                    full_grid_request=False, param_overrides=None):
    """Write scr_<name>/ with a self-consistent request/body/envelope/invocation
    chain per bench. ``mutate(bench_name, corners)`` edits the corner list."""
    sub = root / f"scr_{name}"
    sub.mkdir(parents=True)
    for bname, bench in BENCH_SPECS.items():
        geo = (geometry_by_bench or {}).get(bname, geometry)
        body = build.compose_body(bench, build.BATCH_OSDI_DIR, geometry_overrides=geo,
                                  param_overrides=param_overrides)
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

    def test_markdown_only_conflict_writes_nothing(self):
        camp = self.root / "c1"
        camp.mkdir()
        write_candidate(camp)
        (camp / "sizesweep.md").write_text("historical", encoding="utf-8")
        with self.assertRaises(FileExistsError) as cm:
            sizesweep.run("c1", self.root)
        self.assertIn("--report-name", str(cm.exception))
        self.assertFalse((camp / "sizesweep.json").exists())
        self.assertEqual((camp / "sizesweep.md").read_text(), "historical")

    def test_identical_rerun_preserves_timestamps(self):
        camp = self.root / "c1"
        camp.mkdir()
        write_candidate(camp)
        sizesweep.run("c1", self.root)
        before = {n: (camp / n).stat().st_mtime_ns for n in ("sizesweep.json", "sizesweep.md")}
        sizesweep.run("c1", self.root)
        after = {n: (camp / n).stat().st_mtime_ns for n in before}
        self.assertEqual(before, after)

    def test_matching_partial_pair_is_completed(self):
        camp = self.root / "c1"
        camp.mkdir()
        write_candidate(camp)
        sizesweep.run("c1", self.root)
        (camp / "sizesweep.json").unlink()
        md_before = (camp / "sizesweep.md").stat().st_mtime_ns
        sizesweep.run("c1", self.root)
        self.assertTrue((camp / "sizesweep.json").is_file())
        self.assertEqual((camp / "sizesweep.md").stat().st_mtime_ns, md_before)


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


class FullFinalistGeometryGateTests(unittest.TestCase):
    """Issue #269: a finalist is one candidate only if all benches agree."""

    OVERRIDE = {"XM1.w": "8u", "XM2.w": "8u"}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_full(self, bodies, skip=(), verdict=None, extra_rows=()):
        sub = self.root / "full_x"
        sub.mkdir()
        for bname, bench in BENCH_SPECS.items():
            if bname in skip:
                continue
            if isinstance(bodies.get(bname), str):
                text = bodies[bname]
            else:
                text = build.compose_body(bench, build.BATCH_OSDI_DIR, geometry_overrides=bodies.get(bname))
            (sub / f"{bname}.body.spice").write_text(text, encoding="utf-8")
        verdict = verdict or grade.PASS
        rows = [{"id": rid, "target_verdict": verdict, "stretch_verdict": verdict,
                 "target_bound": 1.0, "stretch_bound": 1.0,
                 "target": {"points_valid": 45, "points_expected": 45, "points_failing": 0,
                            "worst": {"value": 0.5, "point": "tt_27c_1.2v"}},
                 "stretch": {"points_failing": 0}}
                for rid, _l, _u in sizesweep.FULL_ROWS if rid not in skip_rows(skip)]
        # the real campaigns grade a 5a coverage row too; its INCOMPLETE shape
        # (evidence_kind "coverage", no `target` block) is what the roll-up
        # exemption must let through (issue #447)
        rows.append(coverage_row("5a", grade.INCOMPLETE))
        rows.extend(extra_rows)
        orig = grade.grade_campaign
        grade.grade_campaign = lambda _d: {"rows": rows}
        self.addCleanup(setattr, grade, "grade_campaign", orig)
        res = sizesweep.full(self.root)
        self.assertEqual(len(res), 1)
        result = {"campaign": "c", "screen": [], "full": res}
        json.dumps(grade.json_safe(result), allow_nan=False)
        return res[0], sizesweep.render_markdown(result)

    def test_consistent_baseline_control(self):
        r, md = self.run_full({})
        self.assertEqual(r["candidate_status"], "available")
        met, failed, _i, _u = sizesweep._met(r)
        self.assertTrue(met)
        self.assertEqual(failed, [])
        self.assertNotIn("REJECTED", md)

    def test_consistent_override_control(self):
        bodies = {b: self.OVERRIDE for b in BENCH_SPECS}
        r, md = self.run_full(bodies)
        self.assertEqual(r["candidate_status"], "available")
        self.assertEqual(r["geometry"], self.OVERRIDE)
        self.assertTrue(sizesweep._met(r)[0])
        self.assertNotIn("REJECTED", md)

    def test_conflicting_geometry_is_rejected(self):
        r, md = self.run_full({"kickback": self.OVERRIDE})
        self.assertEqual(r["candidate_status"], "rejected")
        self.assertTrue(any("inconsistent" in x for x in r["rejection_reasons"]))
        self.assertEqual(sizesweep._met(r), ([], [], [], []))
        self.assertTrue(all(c["state"] == "rejected" for c in r["rows"].values()))
        # individual results survive as diagnostics only
        self.assertTrue(any(c["state"] == "measured" for c in r["diagnostic_rows"].values()))
        self.assertIn("REJECTED", md)
        self.assertIn("inconsistent candidate geometry", md)
        self.assertNotIn("Target rows met | ", md.split("Ratified Target rows")[0])
        row = [l for l in md.splitlines() if l.startswith("| x | REJECTED")]
        self.assertEqual(len(row), 1)
        self.assertNotIn("1,", row[0])

    def test_conflicting_failed_rows_not_counted_failed(self):
        r, _md = self.run_full({"kickback": self.OVERRIDE}, verdict=grade.FAIL)
        self.assertEqual(sizesweep._met(r), ([], [], [], []))

    def test_unreadable_header_is_rejected(self):
        good = build.compose_body(KICKBACK, build.BATCH_OSDI_DIR)
        bad = good.replace("\n", "\n" + build.GEOMETRY_MARKER + " garbage-no-equals\n", 1)
        with self.assertRaises(build.BuildError):
            build.extract_geometry(bad)
        r, md = self.run_full({"kickback": bad})
        self.assertEqual(r["candidate_status"], "rejected")
        self.assertTrue(any("unreadable" in x for x in r["rejection_reasons"]))
        self.assertEqual(sizesweep._met(r), ([], [], [], []))
        self.assertIn("unreadable geometry override", md)

    def test_missing_bench_still_reported_as_not_run(self):
        r, _md = self.run_full({}, skip=("kickback",))
        self.assertEqual(r["candidate_status"], "available")
        _m, _f, _i, unrun = sizesweep._met(r)
        self.assertTrue(unrun)
        self.assertNotIn("rejected", {c["state"] for c in r["rows"].values()})

    def test_rollup_classifies_every_ratified_row(self):
        # issue #447: the classified set is derived from rows.json, so Row 5a
        # is classified and Row 4c (reporting_requirement) is not
        r, _md = self.run_full({})
        self.assertIn("5a", r["rows"])
        self.assertNotIn("4c", r["rows"])

    def test_coverage_row_incomplete_lands_in_incomplete_not_not_run(self):
        # the test that fails on a naive one-token fix: without the
        # evidence_kind exemption the no-target coverage entry is suppressed
        # to "not swept" and 5a is misfiled under not run
        r, md = self.run_full({})
        met, failed, inc, unrun = sizesweep._met(r)
        self.assertIn("5a", inc)
        self.assertNotIn("5a", unrun)
        self.assertNotIn("5a", met)
        self.assertNotIn("5a", failed)
        rollup = md.split("### Ratified Target rows per finalist")[1]
        self.assertIn("| x | ", rollup)
        row = [l for l in rollup.splitlines() if l.startswith("| x | ")][0]
        self.assertIn("5a", row.split("|")[4])  # the incomplete column

    def test_coverage_row_pass_lands_in_met(self):
        r, _md = self.run_full({}, extra_rows=[coverage_row(
            "5a", grade.PASS, covered=("regeneration", "kickback"), problems=())])
        met, failed, inc, unrun = sizesweep._met(r)
        self.assertIn("5a", met)
        self.assertNotIn("5a", inc)
        self.assertNotIn("5a", unrun)
        self.assertNotIn("5a", failed)

    def test_non_coverage_row_without_target_block_still_not_run(self):
        # the test that fails if the exemption is keyed on the missing
        # `target` block instead of evidence_kind: rows 1/2 of the bias
        # campaign grade INCOMPLETE with no target block under #440 drift and
        # must stay "not run" (issue #447)
        r, _md = self.run_full({}, extra_rows=[sim_row_no_target("1", grade.INCOMPLETE)])
        _m, _f, inc, unrun = sizesweep._met(r)
        self.assertIn("1", unrun)
        self.assertNotIn("1", inc)

    def test_reporting_requirement_row_never_classified(self):
        entry = {"id": "4c", "row": "4c", "unit": "mV", "evidence_kind": "klt_sim",
                 "target_verdict": grade.NOT_SPECIFIED, "stretch_verdict": grade.NOT_SPECIFIED,
                 "target_bound": None, "stretch_bound": None,
                 "target": {"points_valid": 45, "points_expected": 45, "points_failing": 0}}
        r, _md = self.run_full({}, extra_rows=[entry])
        met, failed, inc, unrun = sizesweep._met(r)
        for lst in (met, failed, inc, unrun):
            self.assertNotIn("4c", lst)
        self.assertNotIn("4c", r["rows"])

    def test_metric_table_columns_unchanged(self):
        _r, md = self.run_full({})
        expected = ("| candidate | geometry override | "
                    + " | ".join(f"{l} [{u}]" for _i, l, u in sizesweep.FULL_ROWS) + " |")
        header = md.split("| candidate | geometry override |")[0] + "| candidate | geometry override |" \
            + md.split("| candidate | geometry override |")[1].split("\n")[0]
        self.assertIn(expected, header)
        self.assertNotIn("5a", header)
        self.assertNotIn("4c", header)


def skip_rows(skip):
    return {rid for rid, _l, _u in sizesweep.FULL_ROWS
            if any(rid in (KICK_ROWS if b == "kickback" else ()) for b in skip)}


KICK_ROWS = ("4a", "4b")


def coverage_row(rid, verdict, covered=("regeneration",),
                 problems=("kickback: no envelope",)):
    """A graded entry shaped like ``grade.py``'s coverage branch (issue #447):
    ``evidence_kind == "coverage"`` and **no** ``target``/``stretch`` block."""
    return {"id": rid, "row": rid, "unit": None, "condition": None,
            "statistical_basis": None, "sub_bound": None,
            "target_bound": None, "stretch_bound": None,
            "evidence_kind": "coverage",
            "target_verdict": verdict, "stretch_verdict": grade.NOT_SPECIFIED,
            "benches_fully_covered": list(covered),
            "coverage_problems": list(problems)}


def sim_row_no_target(rid, verdict):
    """A graded klt_sim entry with no ``target`` block (rows 1/2 of
    ``20261115-issue92-bias`` under the #440 grader drift)."""
    return {"id": rid, "row": rid, "unit": "mV", "condition": None,
            "statistical_basis": None, "sub_bound": None,
            "target_bound": None, "stretch_bound": None,
            "evidence_kind": "klt_sim", "bench": "regeneration",
            "target_verdict": verdict, "stretch_verdict": verdict}


# --------------------------------------------------------------------------- #
# issue #497: integration-node capacitance study (noise joins the screen, one
# part per process; structural candidate binding)
# --------------------------------------------------------------------------- #

from kltsim.benches import TRANSIENT_NOISE  # noqa: E402

CAP_GEOMETRY = {"XM1.w": "8u", "XM2.w": "8u", "XM3.w": "6u", "XM4.w": "6u",
                "XM5.w": "6u", "XM6.w": "6u", "XMSW.w": "20u"}


class CapScreenPlanningTests(unittest.TestCase):
    """The noise bench's screening requests: one six-point part per process
    (tt/ff/ss), union exactly the 18 screening points, once each, N = 80 per
    rung preserved -- the fivefold duplication a request-only build produced
    (issue #497 verified correction) can no longer be generated."""

    def test_noise_screen_parts_cover_18_points_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            body_path, requests, files = sizesweep.plan_screen_inputs(
                TRANSIENT_NOISE, out, geometry_overrides=CAP_GEOMETRY)
            tags = sorted(p.name for p in requests)
            self.assertEqual(tags, ["transient_noise.mos_ff.request.json",
                                    "transient_noise.mos_ss.request.json",
                                    "transient_noise.mos_tt.request.json"])
            bodies = {p for p, _ in files if p.name.endswith(".body.spice")}
            self.assertEqual(bodies, {body_path})  # one shared body
            seen = []
            for path, data in files:
                if not path.name.endswith(".request.json"):
                    continue
                req = json.loads(data)
                c = req["corners"]
                self.assertEqual(len(c["process"]), 1, path.name)
                self.assertEqual(c["supply_v"], {"vsup": [1.08, 1.32]})
                self.assertEqual(c["temperature_c"], [-40, 27, 125])
                self.assertEqual(req["monte_carlo"]["n"], 80)
                self.assertEqual(req["netlist"], "transient_noise.body.spice")
                for p in c["process"]:
                    for v in c["supply_v"]["vsup"]:
                        for t in c["temperature_c"]:
                            seen.append((p, v, t))
            self.assertEqual(len(seen), 18)
            self.assertEqual(len(set(map(str, seen))), 18)  # each point ONCE
            self.assertNotIn("remote", req)

    def test_noise_screen_parts_pass_the_chain_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _body, _reqs, files = sizesweep.plan_screen_inputs(
                TRANSIENT_NOISE, out, geometry_overrides=CAP_GEOMETRY)
            for path, data in files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            benches = grade.load_campaign(
                out, corners=sizesweep.screen_corners_for,
                bench_names=("transient_noise",))
            ev = benches["transient_noise"]
            self.assertEqual(ev.chain_problems, [], ev.chain_problems)

    def test_offset_mc_screen_uses_the_benches_mismatch_sections(self):
        from kltsim.benches import OFFSET_MC
        with tempfile.TemporaryDirectory() as tmp:
            _b, requests, files = sizesweep.plan_screen_inputs(OFFSET_MC, Path(tmp))
        self.assertEqual(
            sorted(p.name for p in requests),
            [f"offset_mc.mos_{p}_mismatch.request.json" for p in ("ff", "ss", "tt")])
        self.assertEqual(sorted(sizesweep.screen_part_tags(OFFSET_MC)),
                         sorted(p.name[:-len(".request.json")] for p in requests))

    def test_screen_part_tags_are_a_subset_of_the_benches_full_tags(self):
        for bench in (TRANSIENT_NOISE, KICKBACK, REGENERATION):
            self.assertTrue(set(sizesweep.screen_part_tags(bench))
                            <= set(build.part_tags(bench)), bench.name)

    def test_tiling_preflight_counts_duplicates(self):
        real = sizesweep.screen_part_request

        def whole_grid(bench, section, body_name=None):
            return real(bench, section, body_name) | {
                "corners": sizesweep.screen_corners(bench)}

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(sizesweep, "screen_part_request", whole_grid):
            with self.assertRaises(build.BuildError):
                sizesweep.plan_screen_inputs(TRANSIENT_NOISE, Path(tmp))

    def test_run_reads_the_screen_tags_the_builder_wrote(self):
        import argparse
        from kltsim import cli
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _b, _r, files = sizesweep.plan_screen_inputs(TRANSIENT_NOISE, out)
            for path, data in files:
                path.write_bytes(data)
            seen = []
            args = argparse.Namespace(bench="transient_noise", campaign=str(out),
                                      part=None, skip_existing=False)
            with mock.patch.object(cli, "_campaign_dir", return_value=out), \
                    mock.patch.object(cli, "_submit_with_retry",
                                      side_effect=lambda r, o, tag, a, **k: seen.append(tag) or 0):
                self.assertEqual(cli.cmd_run(args), 0)
            self.assertEqual(sorted(seen), sorted(sizesweep.screen_part_tags(TRANSIENT_NOISE)))

    def test_incomplete_full_grid_and_explicit_parts(self):
        from kltsim import cli
        from kltsim.benches import OFFSET_MC, NOISE_FULL_BENCHES
        for bench in (TRANSIENT_NOISE, OFFSET_MC, NOISE_FULL_BENCHES["tn_full_zero"]):
            with self.subTest(bench=bench.name), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                build.commit_inputs(build.plan_bench_inputs(bench, out, target="batch")[2])
                tags = build.part_tags(bench)
                fs = next(t for t in tags if ".mos_fs" in t)
                sf = next(t for t in tags if ".mos_sf" in t)
                (out / f"{fs}.request.json").unlink()
                argv = ["run", "--campaign", tmp, "--bench", bench.name]
                with mock.patch.object(cli, "_submit_with_retry", return_value=0) as submit:
                    self.assertNotEqual(cli.main(argv), 0)
                    self.assertNotEqual(cli.main(argv + ["--part", sf, "--part", fs]), 0)
                    submit.assert_not_called()
                    self.assertEqual(cli.main(argv + ["--part", sf]), 0)
                    self.assertEqual([c.args[2] for c in submit.call_args_list], [sf])

    def test_unavailable_screen_part_and_mixed_grids(self):
        from kltsim import cli
        bench = TRANSIENT_NOISE
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build.commit_inputs(sizesweep.plan_screen_inputs(bench, out)[2])
            argv = ["run", "--campaign", tmp, "--bench", bench.name]
            with mock.patch.object(cli, "_submit_with_retry", return_value=0) as submit:
                self.assertNotEqual(cli.main(argv + ["--part", "transient_noise.mos_fs"]), 0)
                tag = "transient_noise.mos_tt"
                full = dict(build.plan_bench_inputs(bench, out, target="batch")[2])
                path = out / f"{tag}.request.json"
                path.write_bytes(full[path])
                self.assertNotEqual(cli.main(argv), 0)
                submit.assert_not_called()

    def test_unsplit_screen_bytes_unchanged(self):
        # kickback/regeneration screens keep today's exact request bytes
        # (plan + screen_request), so a rebuild of an archived screen is a
        # byte-identical no-op
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _b, _r, files = sizesweep.plan_screen_inputs(KICKBACK, out)
            for path, data in files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            _b2, _r2, old_files = build.plan_bench_inputs(KICKBACK, out, target="batch")
            old = {p.name: sizesweep.screen_request(d) if p.name.endswith(".request.json") else d
                   for p, d in old_files}
            new = {p.name: d for p, d in files}
            self.assertEqual(old, new)


def _cap_corner(bench, proc, supply, temp, sample=None, values=None):
    section = proc
    cid = f"{section}/{supply:.3f}V/{temp:g}C"
    if sample is not None:
        cid += f"/mc{sample}"
    values = dict(values or {})
    for name in bench.probes.get("supply", ()):
        values.setdefault(name, supply)
    if bench.probes.get("temperature"):
        values.setdefault(bench.probes["temperature"], float(temp))
    measurements = [{"name": m.name, "value": values.get(m.name, 1.0), "unit": m.unit,
                     "status": "pass", "margin": None}
                    for m in bench.measurements if m.name in values]
    return {"corner_id": cid, "process": section,
            "supply_v": {k: supply for k in bench.supply_keys},
            "temperature_c": temp, "status": "pass", "diagnostics": [],
            "monte_carlo": None if sample is None else {"sample_index": sample},
            "measurements": measurements}


def write_cap_screen(root: Path, name="cadd2f", cap="2f", *, geometry=None,
                     candidate_name=None, mutate_noise=None, drop_draw_at=None,
                     drop_point=None, wrong_geometry=None):
    """Write scr_<name>/ holding the issue #497 screen pair: regeneration
    (one request) + transient_noise (three per-process parts), each with a
    self-consistent body/request/envelope/invocation chain."""
    from kltsim import benches as benches_mod
    geometry = geometry if geometry is not None else CAP_GEOMETRY
    sub = root / f"scr_{name}"
    sub.mkdir(parents=True)
    params = {"dut_ib": "1e-05"}
    cand_path = root / f"{candidate_name or name}.spice"
    if not cand_path.is_file():
        cand_path.write_text(build.compose_candidate_netlist(cap), encoding="utf-8")
    candidate = (candidate_name or name, cand_path)
    # -- regeneration: one screen request over the whole grid ----------------
    bench = benches_mod.REGENERATION
    body = build.compose_body(bench, build.BATCH_OSDI_DIR, param_overrides=params,
                              geometry_overrides=geometry, candidate=candidate)
    (sub / "regeneration.body.spice").write_text(body, encoding="utf-8")
    req = build.compose_request(bench, "regeneration.body.spice", "batch")
    req_bytes = sizesweep.screen_request((json.dumps(req, indent=2) + "\n").encode())
    (sub / "regeneration.request.json").write_bytes(req_bytes)
    corners = []
    for p in sizesweep.SCREEN_PROCESSES:
        for v in sizesweep.SCREEN_SUPPLIES_V:
            for t in sizesweep.SCREEN_TEMPERATURES_C:
                vals = {"vdd_meas": v, "vdda_meas": v, "temp_meas": float(t),
                        "dout_od01_first": 1e-7, "dout_od01_end": 1.0,
                        "td_od01_ns": 1.5, "td_od50_ns": 0.7, "tau_ps": 90.0,
                        "p_avg_uw": 25.0, "p_avg": 25e-6}
                corners.append(_cap_corner(bench, p, v, t, values=vals))
    env = {"status": "pass", "corner_count": len(corners), "corners": corners,
           "environment": {"netlist_source": "schematic"},
           "provenance": {"input": {"content_hash":
                                    "sha256:" + hashlib.sha256(body.encode()).hexdigest()}}}
    _write_chain(sub, "regeneration", body, req_bytes, env)
    # -- transient_noise: three per-process parts, N = 80 ---------------------
    bench = benches_mod.TRANSIENT_NOISE
    body = build.compose_body(bench, build.BATCH_OSDI_DIR, param_overrides=params,
                              geometry_overrides=geometry, candidate=candidate)
    (sub / "transient_noise.body.spice").write_text(body, encoding="utf-8")
    _body, requests, _files = sizesweep.plan_screen_inputs(
        bench, sub, param_overrides=params,
        geometry_overrides=geometry, candidate=candidate)
    for path, data in _files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for section in sizesweep.SCREEN_PROCESSES:
        tag = f"transient_noise.{section}"
        req_path = sub / f"{tag}.request.json"
        req_bytes = req_path.read_bytes()
        corners, by_corner = [], {"hit_plus": [], "hit_minus": [], "hit_zero": []}
        draw = 0
        for v in sizesweep.SCREEN_SUPPLIES_V:
            for t in sizesweep.SCREEN_TEMPERATURES_C:
                if drop_point == (section, v, t):
                    continue
                counts = {"hit_plus": 76.0, "hit_minus": 4.0, "hit_zero": 40.0}
                if mutate_noise:
                    counts.update(mutate_noise(section, v, t))
                for k in range(80):
                    draw += 1
                    vals = {"vdd_meas": v, "temp_meas": float(t),
                            "vn0_a": draw * 1e-6, "vn0_b": -draw * 1e-6,
                            "vn1_a": draw * 2e-6,
                            "res_zero": 0.5, "res_plus": 0.5, "res_minus": 0.5}
                    if drop_draw_at == (section, v, t) and k == 3:
                        vals.pop("vn0_a"), vals.pop("vn0_b"), vals.pop("vn1_a")
                    for nm, ones in counts.items():
                        vals[nm] = 1.0 if k < ones else 0.0
                    corners.append(_cap_corner(bench, section, v, t, sample=k, values=vals))
                base = corners[-1]["corner_id"].rsplit("/mc", 1)[0]
                for nm, ones in counts.items():
                    by_corner[nm].append({"corner_id": base, "n": 80, "errored": 0,
                                          "mean": ones / 80, "stddev": None})
        env = {"status": "pass", "corner_count": len(corners), "corners": corners,
               "environment": {"netlist_source": "schematic"},
               "provenance": {"input": {"content_hash":
                                        "sha256:" + hashlib.sha256(body.encode()).hexdigest()}},
               "measurements": [{"name": nm, "unit": "1",
                                 "monte_carlo": {"by_corner": entries}}
                                for nm, entries in by_corner.items()]}
        _write_chain(sub, tag, body, req_bytes, env)
    return sub


def _write_chain(sub: Path, tag: str, body: str, req_bytes: bytes, env: dict):
    env_bytes = (json.dumps(env, indent=2) + "\n").encode()
    (sub / f"{tag}.envelope.json").write_bytes(env_bytes)
    (sub / f"{tag}.invocation.json").write_text(json.dumps({
        "tag": tag, "request_sha256": hashlib.sha256(req_bytes).hexdigest(),
        "envelope_sha256": hashlib.sha256(env_bytes).hexdigest()}), encoding="utf-8")


class CapScreenReductionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def reduce(self, **kw):
        write_cap_screen(self.root, **kw)
        rows = sizesweep.cap_screen(self.root)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_complete_screen_gives_both_statistics(self):
        row = self.reduce()
        self.assertEqual(row["candidate"]["name"], "cadd2f")
        self.assertEqual(row["cap_fF"], 2.0)
        self.assertEqual(row["geometry_problems"] + row["candidate_problems"]
                         + row["identity_problems"], [])
        noise = row["metrics"]["noise_mean"]
        td01 = row["metrics"]["td01_worst"]
        self.assertTrue(noise["available"] and td01["available"])
        self.assertEqual((noise["valid"], noise["expected"]), (18, 18))
        self.assertEqual((td01["valid"], td01["expected"]), (18, 18))
        self.assertAlmostEqual(noise["value"], 2.0 / (grade.probit(0.95) - grade.probit(0.05)),
                               places=6)
        self.assertEqual(td01["value"], 1.5)
        self.assertIn("noise_statistic", row["metrics"]["noise_mean"])  # labelled

    def test_missing_draw_rejects_only_its_point(self):
        row = self.reduce(drop_draw_at=("mos_tt", 1.08, -40))
        noise = row["metrics"]["noise_mean"]
        self.assertFalse(noise["available"])
        self.assertEqual(noise["valid"], 17)
        self.assertEqual(noise["present"], 18)
        self.assertEqual(row["benches"]["transient_noise"]["missing_points"], [])
        self.assertTrue(any("independence probe" in r for r in noise["rejections"]),
                        noise["rejections"])

    def test_missing_point_is_counted_not_averaged_over(self):
        row = self.reduce(drop_point=("mos_ff", 1.32, 125))
        noise = row["metrics"]["noise_mean"]
        self.assertFalse(noise["available"])
        self.assertEqual(noise["valid"], 17)
        self.assertEqual((noise["present"], noise["expected"]), (17, 18))
        bench = row["benches"]["transient_noise"]
        self.assertEqual((bench["present"], bench["missing_points"]), (17, ["ff_125c_1.32v"]))
        self.assertEqual(noise["missing_points"], bench["missing_points"])
        self.assertTrue(any("no Monte-Carlo population" in r for r in noise["rejections"]))

    def test_incomplete_screen_is_not_an_elimination(self):
        row = self.reduce(drop_point=("mos_ff", 1.32, 125))
        noise = row["metrics"]["noise_mean"]
        self.assertIsNone(noise["value"])           # no partial mean as the statistic
        self.assertIsNotNone(noise["partial_mean"])
        self.assertTrue(noise["missing_points"])
        self.assertEqual(row["decision"]["decision"], "incomplete")
        self.assertFalse(row["decision"]["advance"])
        result = {"campaign": "c", "control": sizesweep.cap_control(),
                  "screen": [row], "full": []}
        md = sizesweep.render_capacitance_markdown(result)
        self.assertIn("Screen INCOMPLETE", md)
        self.assertNotIn("No setting advanced", md)

        from kltsim import cli
        from contextlib import redirect_stdout
        import io
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["capacitance", "--campaign", str(self.root)]), 1)
        saved = json.loads((self.root / "capacitance.json").read_bytes())
        self.assertEqual(saved["screen"][0]["decision"]["decision"], "incomplete")

    def test_unregistered_candidate_does_not_advance(self):
        row = self.reduce(name="unlisted-setting", cap="2f")
        self.assertTrue(any("not registered" in r for r in
                            row["benches"]["regeneration"]["evidence_rejections"]),
                        row["benches"]["regeneration"]["evidence_rejections"])
        self.assertNotEqual(row["decision"]["decision"], "advance")

    def test_at_most_one_finalist(self):
        def qualifying(name, noise):
            return {"name": name, "cap_fF": 2.0,
                    "metrics": {"noise_mean": {"value": noise}},
                    "decision": {"advance": True, "decision": "advance", "reasons": []}}
        rows = [qualifying("cadd4f", 0.9), qualifying("cadd2f", 0.8)]
        sizesweep._select_finalist(rows)
        self.assertEqual([r["decision"]["decision"] for r in rows],
                         ["not-selected", "advance"])
        self.assertEqual(sum(1 for r in rows if r["decision"]["advance"]), 1)

    def test_substituted_candidate_setting_rejected(self):
        # scr_cadd2f/ whose regeneration bench is a valid cadd4f body+chain
        sub = write_cap_screen(self.root, name="cadd2f", cap="2f")
        other = write_cap_screen(self.root, name="cadd4f", cap="4f")
        for fname in ("regeneration.body.spice", "regeneration.envelope.json",
                      "regeneration.invocation.json", "regeneration.request.json"):
            (sub / fname).write_bytes((other / fname).read_bytes())
        row = sizesweep.cap_screen(self.root)[0]
        self.assertEqual(row["name"], "cadd2f")
        self.assertTrue(any("expected 'cadd2f'" in p for p in row["candidate_problems"]),
                        row["candidate_problems"])
        # the substituted bench's own statistic is withheld (wrong setting)
        self.assertFalse(row["metrics"]["td01_worst"]["available"])
        self.assertTrue(any("expected 'cadd2f'" in r
                            for r in row["benches"]["regeneration"]["evidence_rejections"]))

    def test_wrong_candidate_identity_rejected(self):
        # a scr_ dir whose name does not match the declared candidate
        row = self.reduce(name="cadd2f", candidate_name="cadd4f", cap="4f")
        self.assertTrue(row["candidate_problems"])
        self.assertFalse(row["metrics"]["noise_mean"]["available"])

    def test_non_control_geometry_rejected(self):
        bad = dict(CAP_GEOMETRY)
        bad["XM1.w"] = "9u"
        row = self.reduce(geometry=bad)
        self.assertTrue(any("archived control" in p for p in row["identity_problems"]),
                        row["identity_problems"])
        self.assertFalse(row["metrics"]["noise_mean"]["available"])

    def test_markdown_renders_screen_and_control(self):
        write_cap_screen(self.root, "cadd2f", "2f")
        result = {"campaign": "c", "control": sizesweep.cap_control(),
                  "screen": sizesweep.cap_screen(self.root), "full": []}
        md = sizesweep.render_capacitance_markdown(result)
        self.assertIn("cadd2f", md)
        self.assertIn("control", md)
        json.dumps(grade.json_safe(result), allow_nan=False)


class CapControlTests(unittest.TestCase):
    """The archived zero-added-capacitance control, re-derived from the
    committed #92 bias campaign (issue body, re-verified): 18-point noise
    mean 1.05259 mV rms at 36.27 nV/rtHz, worst screen Row 3c 1.862 ns."""

    def test_control_row_values(self):
        control = sizesweep.cap_control()
        noise = control["metrics"]["noise_mean"]
        td01 = control["metrics"]["td01_worst"]
        self.assertTrue(noise["available"] and td01["available"])
        self.assertAlmostEqual(noise["value"], 1.0525913, places=6)
        self.assertAlmostEqual(td01["value"], 1.86214, places=4)
        self.assertEqual(td01["point"], "ss_-40c_1.08v")
        self.assertEqual(control["archived"], "20261115-issue92-bias")
        self.assertEqual(control["cap_fF"], 0.0)


if __name__ == "__main__":
    unittest.main()


class CapFullTests(unittest.TestCase):
    """The issue #497 finalist table: candidate expectation threading and the
    archived 8 um baseline's Target verdicts carried beside each row."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.cand = self.root / "cadd2f.spice"
        self.cand.write_text(build.compose_candidate_netlist("2f"), encoding="utf-8")

    def _full_dir(self, name="cadd2f"):
        sub = self.root / f"full_{name}"
        sub.mkdir()
        return sub

    def write_full_bodies(self, name="cadd2f"):
        from kltsim.benches import BENCHES as all_benches
        sub = self._full_dir(name)
        for bname, bench in all_benches.items():
            (sub / f"{bname}.body.spice").write_text(
                build.compose_body(bench, build.BATCH_OSDI_DIR,
                                   param_overrides={"dut_ib": "1e-05"},
                                   geometry_overrides=CAP_GEOMETRY,
                                   candidate=(name, self.cand)), encoding="utf-8")
        return sub

    def run_cap_full(self, graded_rows, name="cadd2f"):
        self.write_full_bodies(name)
        calls = []
        orig = grade.grade_campaign

        def fake_grade_campaign(campaign_dir, candidate=None):
            calls.append((campaign_dir.name, candidate))
            return {"rows": graded_rows, "t1_item5": {"all_target_rows_pass": True}}

        grade.grade_campaign = fake_grade_campaign
        self.addCleanup(setattr, grade, "grade_campaign", orig)
        res = sizesweep.cap_full(self.root)
        self.assertEqual(len(res), 1)
        result = {"campaign": "c", "control": sizesweep.cap_control(),
                  "screen": [], "full": res}
        json.dumps(grade.json_safe(result), allow_nan=False)
        return res[0], calls, sizesweep.render_capacitance_markdown(result)

    def test_candidate_expectation_and_baseline_carry(self):
        rows = [{"id": rid, "target_verdict": grade.PASS, "stretch_verdict": grade.PASS,
                 "target_bound": 1.0, "stretch_bound": 1.0,
                 "target": {"points_valid": 45, "points_expected": 45, "points_failing": 0,
                            "worst": {"value": 0.5, "point": "tt_27c_1.2v"}},
                 "stretch": {"points_failing": 0}}
                for rid, _l, _u in sizesweep.FULL_ROWS]
        r, calls, md = self.run_cap_full(rows)
        self.assertEqual(r["candidate_status"], "available")
        self.assertEqual(calls, [("full_cadd2f", "cadd2f")])  # named expectation threaded
        # the archived 8 um baseline verdict is carried per row
        self.assertTrue(all(c.get("baseline_w8_l034_target") is not None
                            for c in r["rows"].values()))
        self.assertIn("Row 2 (Target <= 1.0 mV rms)", md)

    def test_baseline_broken_marked(self):
        # rows the 8 um baseline PASSes but the finalist FAILs preserve nothing
        def row(rid, verdict, value):
            return {"id": rid, "target_verdict": verdict, "stretch_verdict": verdict,
                    "target": {"points_valid": 45, "points_expected": 45,
                               "points_failing": 0 if verdict == grade.PASS else 3,
                               "worst": {"value": value, "point": "ff_125c_1.08v"}}}
        rows = [row("3a", grade.PASS, 0.7), row("3c", grade.FAIL, 2.4)]
        r, _calls, md = self.run_cap_full(rows)
        self.assertEqual(r["rows"]["3a"]["preservation"], "held")
        self.assertEqual(r["rows"]["3c"]["preservation"], "broken")
        self.assertIn("baseline-broken", md)

    def test_incomplete_row_is_unverified_not_broken(self):
        incomplete = {"id": "3a", "target_verdict": grade.INCOMPLETE,
                      "stretch_verdict": grade.INCOMPLETE,
                      "target": {"points_valid": 30, "points_expected": 45,
                                 "points_failing": 0,
                                 "binding": {"value": 0.7, "point": "tt_27c_1.2v"}}}
        empty = {"id": "3c", "target_verdict": grade.INCOMPLETE,
                 "stretch_verdict": grade.INCOMPLETE,
                 "target": {"points_valid": 0, "points_expected": 45}}
        r, _calls, md = self.run_cap_full([incomplete, empty])
        self.assertEqual(r["rows"]["3a"]["state"], "incomplete")
        self.assertEqual(r["rows"]["3a"]["preservation"], "unverified")
        self.assertEqual(r["rows"]["3c"]["preservation"], "unverified")
        self.assertNotIn("baseline-broken", md)

    def test_row2_summary_keeps_the_graders_grid_mean(self):
        entry = {"id": "2", "target_verdict": grade.FAIL,
                 "target": {"grid_mean": 1.0962763220245755, "points_valid": 45,
                            "points_expected": 45}}
        s = sizesweep._full_row_summary(entry)
        self.assertEqual(s["value"], 1.0962763220245755)
        self.assertEqual((s["points_valid"], s["points_expected"]), (45, 45))

    def test_finalist_without_envelopes_retains_real_grader_diagnostics(self):
        sub = self.write_full_bodies()
        entries = {r["id"]: r for r in grade.grade_campaign(sub, candidate="cadd2f")["rows"]}
        result = {"campaign": "c", "full": sizesweep.cap_full(self.root)}
        rows = result["full"][0]["rows"]
        self.assertEqual(rows["4c"]["state"], "incomplete")
        self.assertEqual(rows["4c"]["report_verdict"], entries["4c"]["report_verdict"])
        self.assertEqual(rows["5a"]["benches_fully_covered"], [])
        self.assertEqual(len(rows["5a"]["coverage_problems"]), 4)
        self.assertEqual(rows["5a"]["coverage_problems"], entries["5a"]["coverage_problems"])
        md = sizesweep.render_capacitance_markdown(result)
        self.assertIn("reporting requirement: INCOMPLETE", md)
        for reason in entries["5a"]["coverage_problems"]:
            self.assertIn(reason, md)

    def test_completed_reporting_and_coverage_rows_from_archived_grade(self):
        baseline = (build.EXPERIMENT_DIR / "campaigns" / sizesweep.BASELINE_CAMPAIGN
                    / sizesweep.BASELINE_FULL / "grading.json")
        entries = json.loads(baseline.read_bytes())["rows"]
        finalist, _, md = self.run_cap_full(entries)
        self.assertEqual(finalist["rows"]["4c"]["report_verdict"], grade.REPORTED)
        self.assertIn("reporting requirement: REPORTED", md)
        covered = next(r for r in entries if r["id"] == "5a")["benches_fully_covered"]
        self.assertEqual(finalist["rows"]["5a"]["benches_fully_covered"], covered)
        self.assertIn("covered: " + ", ".join(covered), md)

    def test_table_includes_reporting_and_coverage_rows(self):
        ids = [i for i, _l, _u in sizesweep._table_rows()]
        self.assertIn("4c", ids)
        self.assertIn("5a", ids)
        r, _calls, md = self.run_cap_full([])
        self.assertIn("4c", r["rows"])
        self.assertIn("5a", r["rows"])
        self.assertIn("5a grid coverage", md)

    def test_finalist_with_other_geometry_rejected_before_grading(self):
        from kltsim.benches import BENCHES as all_benches
        sub = self._full_dir("cadd2f")
        bad = dict(CAP_GEOMETRY)
        bad["XM1.w"] = "9u"
        for bname, bench in all_benches.items():
            (sub / f"{bname}.body.spice").write_text(
                build.compose_body(bench, build.BATCH_OSDI_DIR,
                                   param_overrides={"dut_ib": "1e-05"},
                                   geometry_overrides=bad,
                                   candidate=("cadd2f", self.cand)), encoding="utf-8")
        called = []
        orig = grade.grade_campaign
        grade.grade_campaign = lambda *a, **k: called.append(1) or {"rows": []}
        self.addCleanup(setattr, grade, "grade_campaign", orig)
        r = sizesweep.cap_full(self.root)[0]
        self.assertEqual(called, [])
        self.assertEqual(r["candidate_status"], "rejected")
        self.assertTrue(any("archived control identity" in x for x in r["rejection_reasons"]))

    def test_wrong_candidate_name_rejected_before_grading(self):
        sub = self._full_dir("cadd4f")  # dir says cadd4f, bodies declare cadd2f? no:
        # bodies are composed with name cadd4f but reference cadd2f's file ->
        # the declaration names cadd4f with cadd2f's bytes: reference mismatch
        from kltsim.benches import BENCHES as all_benches
        for bname, bench in all_benches.items():
            body = build.compose_body(bench, build.BATCH_OSDI_DIR,
                                      param_overrides={"dut_ib": "1e-05"},
                                      geometry_overrides=CAP_GEOMETRY,
                                      candidate=("cadd2f", self.cand))
            (sub / f"{bname}.body.spice").write_text(
                body.replace("name=cadd2f ", "name=cadd4f "), encoding="utf-8")
        r = sizesweep.cap_full(self.root)[0]
        self.assertEqual(r["candidate_status"], "rejected")
        self.assertTrue(r["rejection_reasons"])
        self.assertEqual(r["rows"]["3c"]["state"], "rejected")




class GradeCliCandidateTests(unittest.TestCase):
    def test_offset_n_with_candidate_is_rejected(self):
        import argparse
        import contextlib
        import io
        from kltsim import cli
        args = argparse.Namespace(campaign="x", offset_n=100, candidate="cadd2f")
        with mock.patch.object(cli, "_campaign_dir", return_value=Path("/nonexistent")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.cmd_grade(args), 2)
        self.assertIn("--offset-n", err.getvalue())

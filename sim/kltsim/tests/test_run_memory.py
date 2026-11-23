"""Campaign replay / record tests for sim/run_memory.py (issue #159). Stdlib
only: synthetic klt sim envelopes in a temporary campaign directory, no
ngspice, no network, nothing written under sim/."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kltsim import memory as mem

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import run_memory as rm  # noqa: E402

SERIES = "synthetic"


def _write_round(root: Path, arm: str, k: int, searches, thresholds):
    """Write the envelopes the fleet would have returned for round k."""
    spec = rm.ARMS[arm]
    plan = mem.build_plan(searches, k)
    rdir = root / SERIES / arm / f"round{k}"
    rdir.mkdir(parents=True, exist_ok=True)
    for proc in rm.processes_with_work(searches, spec["processes"]):
        corners = []
        for key in plan:
            if key[0] != proc:
                continue
            p, supply, temp = key
            vals = {"vdd_meas": supply, "temp_meas": float(temp)}
            mult = mem.round_mult(k == 1)
            for h in mem.HISTORIES:
                vals[mem.meas_name("lo", h)] = float(plan[key][h]["lo"])
                for m, probe in zip(mult, plan[key][h]["probes"]):
                    vals[mem.meas_name("d", h, m)] = (
                        1.0 if probe > thresholds(key, h) else -1.0)
                    vals[mem.meas_name("s", h, m)] = probe * 1e-6
            corners.append({
                "corner_id": f"{p}/{supply:.3f}V/{temp:g}C", "process": p,
                "supply_v": {"vsup": supply}, "temperature_c": temp, "status": "pass",
                "runtime_s": 2.0,
                "measurements": [{"name": n, "value": v, "status": "pass"} for n, v in vals.items()]})
        env = {"status": "pass", "corner_count": len(corners), "corners": corners,
               "environment": {"engine_version": "46",
                               "remote": {"job_id": f"job-{arm}-{k}-{proc}"}}}
        (rdir / f"{rm.tag_for(proc)}.envelope.json").write_text(json.dumps(env), encoding="utf-8")


def build_campaign(root: Path, nominal, long_thr, short_thr):
    for arm, thr in (("nominal", nominal), ("control-long", long_thr), ("control-short", short_thr)):
        for k in range(1, mem.MAX_ROUNDS + 1):
            searches, done = rm.replay(SERIES, arm, upto=k - 1)
            if not any(ps.active() for ps in searches.values()):
                break
            _write_round(root, arm, k, searches, thr)


class RecordTests(unittest.TestCase):
    def record(self, nominal, long_thr, short_thr):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(mem, "CAMPAIGNS_DIR", root):
                build_campaign(root, nominal, long_thr, short_thr)
                return rm.build_record(SERIES)

    def test_controls_pass_and_nominal_shift_is_signed(self):
        def nominal(key, h):
            return -300 if h == "P" else 450          # P below N: negative shift
        rec = self.record(nominal,
                          lambda key, h: 105 if h == "P" else 95,      # +10 uV
                          lambda key, h: 125 if h == "P" else 65)      # +60 uV
        s = rec["nominal"]["summary"]
        self.assertEqual((s["points"], s["points_with_two_thresholds"], s["points_rejected"]), (45, 45, 0))
        self.assertLess(s["memory_shift_mV"]["max"], 0)
        self.assertLessEqual(s["max_final_bracket_width_uV"], 10)
        self.assertEqual(rec["controls"]["long_reset"]["verdict"]["verdict"], "PASS")
        self.assertEqual(rec["controls"]["short_reset"]["verdict"]["verdict"], "PASS")
        self.assertEqual(rec["controls"]["bench_sensitivity_control"], "PASS")
        self.assertEqual(s["probe_classification_total"]["unresolved"], 0)
        self.assertGreater(s["probe_classification_total"]["wrong_polarity"], 0)

    def test_insensitive_short_reset_control_fails_and_blocks_the_conclusion(self):
        rec = self.record(lambda key, h: 0,
                          lambda key, h: 5 if h == "P" else -5,
                          lambda key, h: 5 if h == "P" else -5)
        c = rec["controls"]
        self.assertEqual(c["long_reset"]["verdict"]["verdict"], "PASS")
        self.assertEqual(c["short_reset"]["verdict"]["verdict"], "FAIL")
        self.assertEqual(c["bench_sensitivity_control"], "FAIL")
        self.assertIn("NOT supported", c["interpretation"])

    def test_noisy_long_reset_control_fails(self):
        rec = self.record(lambda key, h: 0,
                          lambda key, h: 60 if h == "P" else -60,
                          lambda key, h: 200 if h == "P" else -200)
        self.assertEqual(rec["controls"]["long_reset"]["verdict"]["verdict"], "FAIL")
        self.assertEqual(rec["controls"]["bench_sensitivity_control"], "FAIL")

    def test_rejected_point_is_listed_not_fabricated(self):
        def nominal(key, h):
            # one point's P history never switches inside the +/-50 mV range
            return 10 ** 9 if (key == ("mos_ss", 1.08, -40.0) and h == "P") else 0
        rec = self.record(nominal, lambda key, h: 0, lambda key, h: 0)
        s = rec["nominal"]["summary"]
        self.assertEqual(s["points_rejected"], 1)
        self.assertEqual(s["points_with_two_thresholds"], 44)
        row = [r for r in rec["nominal"]["points"] if r["corner"] == "ss/1.08V/-40C"][0]
        self.assertIsNone(row["memory_shift_mV"])
        self.assertIsNone(row["threshold_after_P_mV"])
        self.assertIn("initial bracket", row["rejected"]["P"])
        self.assertEqual(s["rejected_points"][0]["corner"], "ss/1.08V/-40C")

    def test_markdown_renders_every_point_and_the_caveat(self):
        rec = self.record(lambda key, h: 0, lambda key, h: 0, lambda key, h: 0)
        md = rm.render_markdown(rec)
        self.assertIn("Characterization, not compliance", md)
        self.assertEqual(md.count("| tt/") + md.count("| ff/") + md.count("| ss/")
                         + md.count("| fs/") + md.count("| sf/"), 45)


class DeterminismRepeatEvidenceTests(unittest.TestCase):
    """Issue #495: a determinism round whose inputs carry no measurements at
    the repeat point is insufficient evidence, never agreement.

    Issue #525: within a round that has measurements, a name with no value on
    both sides is unmeasured, never a compared value."""

    EMPTY_CORNER = {"corner_id": "tt/1.200V/27C", "process": "mos_tt",
                    "supply_v": {"vsup": 1.2}, "temperature_c": 27, "status": "pass",
                    "measurements": []}

    def bare_record(self, nominal_corners, repeat_corners):
        """build_record over a series holding only round-1 tt envelopes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for arm, corners in (("nominal", nominal_corners), ("repeat", repeat_corners)):
                rdir = root / SERIES / arm / "round1"
                rdir.mkdir(parents=True)
                (rdir / f"{rm.tag_for('mos_tt')}.envelope.json").write_text(
                    json.dumps({"status": "pass", "corner_count": len(corners), "corners": corners}))
            with mock.patch.object(mem, "CAMPAIGNS_DIR", root):
                return rm.build_record(SERIES)

    def populated_record(self, make_repeat_corner):
        """Full synthetic campaign plus a round-1 repeat envelope built from the
        nominal round-1 repeat-point corner (None drops the corner)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(mem, "CAMPAIGNS_DIR", root):
                build_campaign(root, lambda key, h: 0, lambda key, h: 0, lambda key, h: 0)
                nominal = json.loads((root / SERIES / "nominal" / "round1" /
                                      f"{rm.tag_for('mos_tt')}.envelope.json").read_text())
                corner = next(c for c in nominal["corners"]
                              if (c["process"], c["supply_v"]["vsup"], c["temperature_c"])
                              == rm.REPEAT_POINT)
                corner = make_repeat_corner(corner)
                corners = [] if corner is None else [corner]
                rdir = root / SERIES / "repeat" / "round1"
                rdir.mkdir(parents=True)
                (rdir / f"{rm.tag_for('mos_tt')}.envelope.json").write_text(
                    json.dumps({"status": "pass", "corner_count": len(corners), "corners": corners}))
                return rm.build_record(SERIES)

    def round1(self, rec):
        rounds = rec["determinism_repeat"]["rounds"]
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["round"], 1)
        return rounds[0]

    def test_absent_corner_on_both_sides_is_insufficient_evidence(self):
        rec = self.bare_record([], [])
        r = self.round1(rec)
        self.assertIsNone(r["identical"])
        self.assertEqual(r["values_compared"], 0)
        self.assertEqual(r["missing_measurements"], ["nominal", "repeat"])
        self.assertEqual(r["differences"], {})
        self.assertFalse(rec["determinism_repeat"]["all_identical"])
        md = rm.render_markdown(rec)
        self.assertIn("INSUFFICIENT EVIDENCE", md)
        self.assertIn("nominal and repeat envelope", md)
        self.assertNotIn("All rounds bit-identical: **True**", md)

    def test_matching_corners_with_empty_measurements_is_insufficient_evidence(self):
        rec = self.bare_record([self.EMPTY_CORNER], [dict(self.EMPTY_CORNER)])
        r = self.round1(rec)
        self.assertIsNone(r["identical"])
        self.assertEqual(r["values_compared"], 0)
        self.assertEqual(r["missing_measurements"], ["nominal", "repeat"])
        self.assertFalse(rec["determinism_repeat"]["all_identical"])
        self.assertIn("INSUFFICIENT EVIDENCE", rm.render_markdown(rec))

    def test_one_sided_absence_names_the_input_without_measurements(self):
        rec = self.populated_record(lambda c: None)
        r = self.round1(rec)
        self.assertIsNone(r["identical"])
        self.assertEqual(r["missing_measurements"], ["repeat"])
        self.assertFalse(rec["determinism_repeat"]["all_identical"])
        self.assertIn("repeat envelope", rm.render_markdown(rec))

    NULL_CORNER = {**EMPTY_CORNER, "measurements": [
        {"name": "vdd_meas", "value": None, "status": "error"}]}

    def test_all_null_measurements_on_both_sides_is_insufficient_evidence(self):
        rec = self.bare_record([self.NULL_CORNER], [dict(self.NULL_CORNER)])
        r = self.round1(rec)
        self.assertIsNone(r["identical"])
        self.assertEqual(r["values_compared"], 0)
        self.assertEqual(r["missing_measurements"], ["nominal", "repeat"])
        self.assertEqual(r["differences"], {})
        self.assertFalse(rec["determinism_repeat"]["all_identical"])
        md = rm.render_markdown(rec)
        self.assertIn("INSUFFICIENT EVIDENCE", md)
        self.assertNotIn("bit-identical: **True**", md)

    def test_absent_or_null_measurement_list_is_insufficient_evidence(self):
        absent = {k: v for k, v in self.EMPTY_CORNER.items() if k != "measurements"}
        null = {**self.EMPTY_CORNER, "measurements": None}
        rec = self.bare_record([absent], [null])
        r = self.round1(rec)
        self.assertIsNone(r["identical"])
        self.assertEqual(r["missing_measurements"], ["nominal", "repeat"])

    def test_all_null_input_paired_with_populated_input_is_insufficient_evidence(self):
        def nulled(c):
            return {**c, "measurements": [{**m, "value": None, "status": "error"}
                                          for m in c["measurements"]]}
        rec = self.populated_record(nulled)
        r = self.round1(rec)
        self.assertIsNone(r["identical"])
        self.assertEqual(r["values_compared"], 0)
        self.assertEqual(r["missing_measurements"], ["repeat"])
        self.assertFalse(rec["determinism_repeat"]["all_identical"])
        self.assertIn("repeat envelope", rm.render_markdown(rec))

    def test_numeric_zero_is_evidence(self):
        zero = {**self.EMPTY_CORNER, "measurements": [{"name": "x", "value": 0.0}]}
        rec = self.bare_record([zero], [dict(zero)])
        r = self.round1(rec)
        self.assertIs(r["identical"], True)
        self.assertEqual(r["values_compared"], 1)

    def test_populated_equal_rounds_still_report_agreement(self):
        rec = self.populated_record(lambda c: c)
        r = self.round1(rec)
        self.assertIs(r["identical"], True)
        self.assertGreater(r["values_compared"], 0)
        self.assertEqual(r["differences"], {})
        self.assertEqual(r["max_abs_difference"], 0.0)
        self.assertTrue(rec["determinism_repeat"]["all_identical"])
        self.assertIn("All rounds bit-identical: **True**", rm.render_markdown(rec))

    def test_populated_unequal_round_reports_the_difference(self):
        def bumped(c):
            return {**c, "measurements": [{**m, "value": m["value"] + 1.0}
                                          for m in c["measurements"]]}
        rec = self.populated_record(bumped)
        r = self.round1(rec)
        self.assertIs(r["identical"], False)
        self.assertGreater(r["values_compared"], 0)
        self.assertTrue(r["differences"])
        self.assertGreater(r["max_abs_difference"], 0.0)
        self.assertFalse(rec["determinism_repeat"]["all_identical"])
        self.assertIn("All rounds bit-identical: **False**", rm.render_markdown(rec))

    PARTIAL_CORNER = {**EMPTY_CORNER, "measurements": [
        {"name": "a", "value": None, "status": "error"},
        {"name": "b", "value": None, "status": "error"},
        {"name": "c", "value": 1.5, "status": "pass"}]}

    def test_null_on_both_sides_is_unmeasured_not_a_compared_value(self):
        rec = self.bare_record([self.PARTIAL_CORNER], [dict(self.PARTIAL_CORNER)])
        r = self.round1(rec)
        self.assertIs(r["identical"], True)
        self.assertEqual(r["values_compared"], 1)
        self.assertEqual(r["unmeasured"], ["a", "b"])
        self.assertEqual(r["differences"], {})
        self.assertTrue(rec["determinism_repeat"]["all_identical"])
        md = rm.render_markdown(rec)
        self.assertIn("round 1: PARTIALLY MEASURED", md)
        self.assertIn("a, b", md)
        self.assertNotIn("All rounds bit-identical", md)

    def test_unmeasured_names_do_not_hide_a_real_difference(self):
        def bumped(c):
            return {**c, "measurements": [{**m, "value": None if m["value"] is None
                                           else m["value"] + 1.0} for m in c["measurements"]]}
        rec = self.bare_record([self.PARTIAL_CORNER], [bumped(self.PARTIAL_CORNER)])
        r = self.round1(rec)
        self.assertIs(r["identical"], False)
        self.assertEqual(r["values_compared"], 1)
        self.assertEqual(r["unmeasured"], ["a", "b"])
        self.assertEqual(r["differences"], {"c": [1.5, 2.5]})
        self.assertAlmostEqual(r["max_abs_difference"], 1.0)
        self.assertNotIn("All rounds bit-identical", rm.render_markdown(rec))

    def test_value_on_one_side_only_is_unmeasured_and_still_a_difference(self):
        def one_nulled(c):
            ms = [dict(m) for m in c["measurements"]]
            ms[0].update(value=None, status="error")
            return {**c, "measurements": ms}
        full = self.round1(self.populated_record(lambda c: c))
        rec = self.populated_record(one_nulled)
        r = self.round1(rec)
        self.assertIs(r["identical"], False)
        self.assertEqual(r["differences"], {"vdd_meas": [1.2, None]})
        self.assertEqual(r["unmeasured"], ["vdd_meas"])
        self.assertEqual(r["values_compared"], full["values_compared"] - 1)

    def test_fully_measured_round_lists_nothing_unmeasured(self):
        rec = self.populated_record(lambda c: c)
        r = self.round1(rec)
        self.assertEqual(r["unmeasured"], [])
        self.assertIn("All rounds bit-identical: **True**", rm.render_markdown(rec))
        self.assertNotIn("PARTIALLY MEASURED", rm.render_markdown(rec))

    def test_error_status_with_a_numeric_value_counts_as_evidence(self):
        errored = {**self.EMPTY_CORNER, "measurements": [
            {"name": "x", "value": 1.5, "status": "error"}]}
        rec = self.bare_record([errored], [dict(errored)])
        r = self.round1(rec)
        self.assertIs(r["identical"], True)
        self.assertEqual(r["values_compared"], 1)
        self.assertEqual(r["unmeasured"], [])
        self.assertIn("All rounds bit-identical: **True**", rm.render_markdown(rec))

    def test_partially_measured_round_is_named_beside_an_insufficient_one(self):
        rec = self.bare_record([self.PARTIAL_CORNER], [dict(self.PARTIAL_CORNER)])
        rec["determinism_repeat"]["rounds"].append(
            {"round": 2, "values_compared": 0, "identical": None, "missing_measurements": ["repeat"],
             "max_abs_difference": None, "differences": {}})
        md = rm.render_markdown(rec)
        self.assertIn("round 2: INSUFFICIENT EVIDENCE", md)
        self.assertIn("round 1: PARTIALLY MEASURED", md)
        self.assertIn("Compared rounds bit-identical", md)
        self.assertNotIn("All rounds bit-identical", md)


class RepeatByteIdentityTests(unittest.TestCase):
    """Issue #426: cmd_repeat's planned request bytes must be identical to the
    pre-refactor output (the committed 20261010-08e31bed1 determinism repeat).
    _commit_planned is patched to capture and refuse, so nothing is written
    and nothing is submitted."""

    INPUT_REQ = {
        "bench": "memory",
        "corners": {
            "processes": ["tt"],
            "supply_v": {"vsup": [1.08, 1.2, 1.32]},
            "temperature_c": [-40, 27, 125],
        },
        "_comment": ["nominal round 1"],
        "_round": {"issue": 159, "arm": "nominal", "round": 1, "step_uV": 50.0,
                   "period_ns": 10.0},
    }

    #: golden: bytes captured from cmd_repeat BEFORE the REPEAT_POINT wiring
    #: (feature/issue-426 base 74c6c2d4a). temperature_c stays int 27.
    GOLDEN_REQUEST = (
        "{\n"
        "  \"bench\": \"memory\",\n"
        "  \"corners\": {\n"
        "    \"processes\": [\n"
        "      \"tt\"\n"
        "    ],\n"
        "    \"supply_v\": {\n"
        "      \"vsup\": [\n"
        "        1.2\n"
        "      ]\n"
        "    },\n"
        "    \"temperature_c\": [\n"
        "      27\n"
        "    ]\n"
        "  },\n"
        "  \"_comment\": [\n"
        "    \"nominal round 1\",\n"
        "    \"DETERMINISM REPEAT: the nominal campaign's round body, narrowed to tt / 1.20 V / 27 C.\"\n"
        "  ],\n"
        "  \"_round\": {\n"
        "    \"issue\": 159,\n"
        "    \"arm\": \"repeat\",\n"
        "    \"round\": 1,\n"
        "    \"step_uV\": 50.0,\n"
        "    \"period_ns\": 10.0\n"
        "  }\n"
        "}\n").encode("utf-8")

    def plan_repeat(self, commit_ok: bool, write_envelope: bool = False):
        """Run cmd_repeat over a synthetic nominal round; return (rc, captured)."""
        captured = []

        def fake_commit(planned, args, label):
            captured.extend(planned)
            return commit_ok

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rdir = root / SERIES / "nominal" / "round1"
            rdir.mkdir(parents=True)
            body = b"* synthetic body\n.end\n"
            (rdir / "memory.mos_tt.body.spice").write_bytes(body)
            (rdir / "memory.mos_tt.request.json").write_text(
                json.dumps(self.INPUT_REQ, indent=2) + "\n", encoding="utf-8")
            if write_envelope:
                env_dir = root / SERIES / "repeat" / "round1"
                env_dir.mkdir(parents=True)
                (env_dir / "memory.mos_tt.envelope.json").write_text(
                    json.dumps({"status": "pass"}), encoding="utf-8")
            with mock.patch.object(mem, "CAMPAIGNS_DIR", root), \
                 mock.patch.object(rm.kcli, "_commit_planned", side_effect=fake_commit), \
                 mock.patch.object(rm, "submit", side_effect=AssertionError("submit called")):
                rc = rm.cmd_repeat(argparse.Namespace(series=SERIES, parallel=1))
        return rc, captured, body

    def test_repeat_request_bytes_are_identical_to_the_pre_refactor_output(self):
        rc, captured, body = self.plan_repeat(commit_ok=False)
        self.assertEqual(rc, 1)                       # refusal path: planned, never submitted
        self.assertEqual(len(captured), 2)            # body + request
        body_path, body_bytes = captured[0]
        req_path, data = captured[1]
        self.assertEqual(body_path.name, "memory.mos_tt.body.spice")
        self.assertEqual(req_path.name, "memory.mos_tt.request.json")
        self.assertEqual(body_bytes, body)            # SAME body as the nominal round
        self.assertEqual(data, self.GOLDEN_REQUEST)   # byte-identical to pre-refactor
        req = json.loads(data)
        self.assertEqual(req["corners"]["temperature_c"], [27])
        self.assertIsInstance(req["corners"]["temperature_c"][0], int)
        self.assertEqual(req["corners"]["supply_v"], {"vsup": [1.2]})
        self.assertNotIn(b"27.0", data)

    def test_repeat_with_no_nominal_body_plans_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(mem, "CAMPAIGNS_DIR", Path(tmp)):
            captured = []
            with mock.patch.object(rm.kcli, "_commit_planned",
                                   side_effect=lambda p, a, l: captured.extend(p) or True):
                rc = rm.cmd_repeat(argparse.Namespace(series=SERIES, parallel=1))
        self.assertEqual((rc, captured), (0, []))

    def test_repeat_with_existing_envelope_submits_no_jobs(self):
        rc, captured, _ = self.plan_repeat(commit_ok=True, write_envelope=True)
        self.assertEqual(rc, 0)                       # planned, then envelope-skip: no jobs
        self.assertEqual(len(captured), 2)


if __name__ == "__main__":
    unittest.main()

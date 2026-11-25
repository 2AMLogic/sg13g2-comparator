"""CM-band decision-time tests (issue #164). Stdlib only, no PDK, no ngspice."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import run_decision_cm_band as rdcb  # noqa: E402
from kltsim import build
from kltsim import cmdecision as cd
from kltsim.benches import REGENERATION


def _corner(key, *, vcm=0.6, td50=0.7, td01=1.3, tau=100.0, status="pass", gate_ok=True,
            drop=None, ms_over=None):
    proc, v, t = key
    proc = f"mos_{proc}"
    ms = {
        "vdd_meas": (v, "V"), "vdda_meas": (v, "V"), "temp_meas": (t, "C"),
        "td_od50_ns": (td50, "ns"), "td_od1_ns": (1.0, "ns"), "td_od01_ns": (td01, "ns"),
        "tau_ps": (tau, "ps"), "resolve_decades": (8.0, "1"), "p_avg_uw": (50.0, "uW"),
        "vcm_meas": (vcm, "V"),
    }
    ms.update(ms_over or {})
    for g in cd.GATES:
        first = g.endswith("_first")
        ms[g] = ((0.0 if first else 1.0) if gate_ok else 0.5, "V/V")
    out = [{"name": n, "value": val, "unit": u,
            "status": "pass" if (gate_ok or n not in cd.GATES) else "fail"}
           for n, (val, u) in ms.items() if n != drop]
    for m in out:  # a (value, None) override models a missing unit
        if m["unit"] is None:
            del m["unit"]
    return {"corner_id": f"{proc}/{v}/{t}", "process": proc,
            "supply_v": {"vsup": v, "vsupa": v}, "temperature_c": t,
            "status": status, "measurements": out}


def _env(over=None):
    over = over or {}
    corners = []
    for k in cd.expected_keys():
        corners.append(_corner(k, **over.get(k, {})))
    return {"corners": corners}


class BodyTests(unittest.TestCase):
    def test_transform_round_trip_and_condition(self):
        body = "* a\n* b\nfoo\n" + cd.VCM_LINE + "\nbar"
        for cond in cd.CONDITIONS:
            out = cd.apply_transform(body, cond)
            self.assertIn(f".param vcm_delta={cond.delta_v!r}", out)
            self.assertIn(cd.VCM_LINE_CM, out)
            self.assertNotIn("\n" + cd.VCM_LINE + "\n", out)
            self.assertEqual(cd.undo_transform(out).split("\n")[2:], body.split("\n")[2:])

    def test_exactly_one_source_line_required(self):
        with self.assertRaises(cd.DecisionCmError):
            cd.apply_transform("a\nb\nc", cd.condition("vcm-nom"))
        with self.assertRaises(cd.DecisionCmError):
            cd.apply_transform(f"a\nb\n{cd.VCM_LINE}\n{cd.VCM_LINE}", cd.condition("vcm-nom"))

    def test_request_is_regeneration_plus_probe(self):
        req = cd.compose_request(cd.condition("vcm-m050"))
        names = [m["name"] for m in req["measurements"]]
        self.assertEqual(names, [m.name for m in REGENERATION.measurements] + ["vcm_meas"])
        self.assertEqual(req["backend"], "batch")
        self.assertNotIn("monte_carlo", req)
        self.assertEqual(len(req["corners"]["process"]), 5)
        self.assertEqual(req["corners"]["supply_v"]["vsup"], req["corners"]["supply_v"]["vsupa"])
        self.assertEqual(req["analysis"], {"kind": "tran", "args": "5p 60n"})
        self.assertEqual(req["_condition"]["vcm_delta_v"], -0.05)
        self.assertAlmostEqual(req["_condition"]["vcm_v"], 0.55)


class AppendOnlyConditionInputs(unittest.TestCase):
    """Issue #516: ``plan_condition_inputs`` + ``build.commit_inputs`` commit
    append-only: a conflict refuses before anything is written, an identical
    rebuild touches nothing."""

    def write(self, tmp, name="vcm-m050"):
        out = Path(tmp)
        planned = cd.plan_condition_inputs(cd.condition(name), out)
        build.commit_inputs(planned)
        return out / cd.BODY_NAME, out / cd.REQUEST_NAME

    def test_conflicting_input_refused_nothing_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            victim = Path(tmp) / cd.BODY_NAME
            victim.write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(build.BuildError):
                self.write(tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [victim])
            self.assertEqual(victim.read_text(), "tampered\n")

    def test_identical_rerun_preserves_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            body, req = self.write(tmp)
            for p in (body, req):  # push mtimes into the past so a rewrite is visible
                os.utime(p, (1_000_000_000, 1_000_000_000))
            self.assertEqual(self.write(tmp), (body, req))
            self.assertEqual({p.stat().st_mtime for p in (body, req)}, {1_000_000_000})

    def test_dangling_symlink_destination_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            target = out / "elsewhere" / cd.BODY_NAME
            (out / cd.BODY_NAME).symlink_to(target)
            with self.assertRaises(build.BuildError):
                self.write(tmp, "vcm-nom")
            self.assertFalse(target.exists())  # the symlink was not followed
            self.assertEqual([p.name for p in out.iterdir()], [cd.BODY_NAME])


class BuildCommandTests(unittest.TestCase):
    """Issue #540: ``run_decision_cm_band.cmd_build`` commits every selected
    condition as ONE append-only batch through ``cli.commit_build``; a
    conflict on any condition writes nothing."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.series = self.root / "s"
        p = mock.patch.object(cd, "SERIES_DIR", self.root)
        p.start()
        self.addCleanup(p.stop)
        self.args = argparse.Namespace(series="s", condition=None)

    def build(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rdcb.cmd_build(self.args)
        return rc, out.getvalue(), err.getvalue()

    def tree(self):
        return {p.relative_to(self.root): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_fresh_build_writes_every_condition(self):
        rc, out, err = self.build()
        self.assertEqual((rc, err), (0, ""))
        expected = sorted([cd.BODY_NAME, cd.REQUEST_NAME])
        self.assertEqual(sorted(p.name for p in self.series.iterdir()),
                         sorted(c.name for c in cd.CONDITIONS))
        for cond in cd.CONDITIONS:
            self.assertEqual(sorted(p.name for p in (self.series / cond.name).iterdir()),
                             expected)
        self.assertEqual([line.split()[0] for line in out.splitlines()],
                         ["wrote"] * 2 * len(cd.CONDITIONS))

    def test_identical_rebuild_is_byte_identical(self):
        self.assertEqual(self.build()[0], 0)
        before = self.tree()
        rc, out, err = self.build()
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(self.tree(), before)
        self.assertEqual([line.split()[0] for line in out.splitlines()],
                         ["unchanged"] * 2 * len(cd.CONDITIONS))

    def test_conflict_on_later_condition_writes_nothing(self):
        earlier, later = cd.CONDITIONS[0], cd.CONDITIONS[1]
        victim = self.series / later.name / cd.BODY_NAME
        victim.parent.mkdir(parents=True)
        victim.write_bytes(b"tampered\n")
        rc, out, err = self.build()
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("build: ", err)
        self.assertEqual(self.tree(), {victim.relative_to(self.root): b"tampered\n"})
        self.assertFalse((self.series / earlier.name).exists())


class AnalysisTests(unittest.TestCase):
    def test_all_valid(self):
        s = cd.summarize(cd.load_points(_env(), 0.6))
        self.assertEqual((s["points_valid"], s["rejected"]), (45, []))
        self.assertEqual(s["grid"]["td_od50_ns"]["target_fail_points"], 0)
        self.assertEqual(s["grid"]["td_od50_ns"]["stretch_fail_points"], 0)

    def test_target_fail_is_graded_not_rejected(self):
        k = cd.expected_keys()[3]
        s = cd.summarize(cd.load_points(_env({k: {"td50": 1.6}}), 0.6))
        self.assertEqual(s["points_valid"], 45)
        self.assertEqual(s["grid"]["td_od50_ns"]["target_fail_points"], 1)

    def test_rejections_named_with_reason(self):
        keys = cd.expected_keys()
        env = _env({keys[0]: {"status": "error"}, keys[1]: {"vcm": 0.7},
                      keys[2]: {"gate_ok": False}, keys[3]: {"drop": "tau_ps"}})
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 41)
        reasons = {r["point"]: r["reason"] for r in s["rejected"]}
        self.assertEqual(len(reasons), 4)
        self.assertIn("errored", reasons[cd.key_label(keys[0])])
        self.assertIn("vcm_meas", reasons[cd.key_label(keys[1])])
        self.assertIn("gate", reasons[cd.key_label(keys[2])])
        self.assertIn("tau_ps", reasons[cd.key_label(keys[3])])

    def _one(self, **kw):
        k = cd.expected_keys()[3]
        s = cd.summarize(cd.load_points(_env({k: kw}), 0.6))
        return k, s

    def test_unit_scaling_s_ps_mv(self):
        k, s = self._one(ms_over={"td_od50_ns": (0.7e-9, "s"), "td_od01_ns": (1300.0, "ps"),
                                  "tau_ps": (1e-10, "s"), "vcm_meas": (600.0, "mV")})
        self.assertEqual((s["points_valid"], s["rejected"]), (45, []))
        row = next(r for r in s["rows"] if tuple(r["key"]) == k)
        self.assertAlmostEqual(row["td_od50_ns"], 0.7)
        self.assertAlmostEqual(row["td_od01_ns"], 1.3)
        self.assertAlmostEqual(row["tau_ps"], 100.0)

    def test_seconds_value_is_scaled_so_it_fails_not_passes(self):
        # 0.7 s mislabelled as ns used to PASS; correctly scaled it is a numerical FAIL.
        k, s = self._one(ms_over={"td_od50_ns": (0.7, "s")})
        self.assertEqual(s["points_valid"], 45)
        row = next(r for r in s["rows"] if tuple(r["key"]) == k)
        self.assertEqual(row["td_od50_ns_target"], "FAIL")
        self.assertEqual(s["grid"]["td_od50_ns"]["target_fail_points"], 1)

    def test_bad_measurements_rejected_with_named_reason(self):
        cases = {
            "negative delay": ({"td_od50_ns": (-1.0, "ns")}, "td_od50_ns", "> 0"),
            # ZERO-DELAY POLICY (issue #266): exactly zero is rejected, delay must be > 0.
            "zero delay": ({"td_od01_ns": (0.0, "ns")}, "td_od01_ns", "> 0"),
            "zero tau": ({"tau_ps": (0.0, "ps")}, "tau_ps", "> 0"),
            "negative tau": ({"tau_ps": (-5.0, "ps")}, "tau_ps", "> 0"),
            "bool": ({"td_od50_ns": (True, "ns")}, "td_od50_ns", "not a number"),
            "nan": ({"tau_ps": (float("nan"), "ps")}, "tau_ps", "not finite"),
            "missing unit": ({"td_od50_ns": (0.7, None)}, "td_od50_ns", "no declared unit"),
            "wrong dimension": ({"td_od50_ns": (0.7, "V")}, "td_od50_ns", "not usable"),
            "unknown unit": ({"tau_ps": (100.0, "furlong")}, "tau_ps", "not usable"),
            "bad vcm unit": ({"vcm_meas": (0.6, "ns")}, "vcm_meas", "not usable"),
            "no vcm unit": ({"vcm_meas": (0.6, None)}, "vcm_meas", "no declared unit"),
            "bool vcm": ({"vcm_meas": (True, "V")}, "vcm_meas", "not a number"),
            "bad td_od1": ({"td_od1_ns": (-1.0, "ns")}, "td_od1_ns", "> 0"),
            "bool decades": ({"resolve_decades": (True, "1")}, "resolve_decades", "not a number"),
            "nan power": ({"p_avg_uw": (float("inf"), "uW")}, "p_avg_uw", "not finite"),
            "power unit": ({"p_avg_uw": (50.0, "V")}, "p_avg_uw", "not usable"),
            "negative power": ({"p_avg_uw": (-1.0, "uW")}, "p_avg_uw", ">= 0"),
        }
        for label, (over, name, text) in cases.items():
            with self.subTest(label):
                k, s = self._one(ms_over=over)
                self.assertEqual(s["points_valid"], 44)
                (rej,) = s["rejected"]
                self.assertEqual(rej["point"], cd.key_label(k))
                self.assertIn(name, rej["reason"])
                self.assertIn(text, rej["reason"])

    def test_raw_envelope_not_mutated(self):
        import copy
        k = cd.expected_keys()[3]
        env = _env({k: {"ms_over": {"td_od50_ns": (700.0, "ps")}}})
        before = copy.deepcopy(env)
        cd.load_points(env, 0.6)
        self.assertEqual(env, before)

    def test_missing_point_is_rejected(self):
        env = _env()
        env["corners"].pop()
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 44)
        self.assertIn("missing", s["rejected"][0]["reason"])

    def test_reproduction(self):
        a, b = _env(), _env()
        for c in b["corners"]:
            c["measurements"] = [m for m in c["measurements"] if m["name"] != "vcm_meas"]
        self.assertTrue(cd.reproduction(a, b)["bit_identical"])
        b["corners"][5]["measurements"][4]["value"] += 1e-12
        rep = cd.reproduction(a, b)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(len(rep["mismatches"]), 1)

    def _drop(self, env, name, only=None):
        for i, c in enumerate(env["corners"]):
            if only is None or i == only:
                c["measurements"] = [m for m in c["measurements"] if m["name"] != name]

    def test_reproduction_missing_measurement_one_point(self):
        a, b = _env(), _env()
        self._drop(a, "td_od1_ns", only=7)
        rep = cd.reproduction(a, b)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(len(rep["mismatches"]), 1)
        self.assertEqual(rep["mismatches"][0]["measurement"], "td_od1_ns")
        self.assertEqual(rep["mismatches"][0]["point"], cd.key_label(cd.expected_keys()[7]))

    def test_reproduction_missing_measurement_all_points(self):
        a, b = _env(), _env()
        self._drop(a, "td_od1_ns")
        rep = cd.reproduction(a, b)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(len(rep["mismatches"]), 45)
        self.assertTrue(all(m["measurement"] == "td_od1_ns" for m in rep["mismatches"]))

    def test_reproduction_extra_nominal_probe_still_identical(self):
        a, b = _env(), _env()
        self._drop(b, "vcm_meas")
        rep = cd.reproduction(a, b)
        self.assertTrue(rep["bit_identical"])
        self.assertEqual(rep["values_compared"], 45 * 9 + 45 * len(cd.GATES))

    def test_reproduction_missing_corner_and_malformed_lists(self):
        a, b = _env(), _env()
        a["corners"].pop()
        self.assertFalse(cd.reproduction(a, b)["bit_identical"])
        a = _env()
        a["corners"][3]["measurements"].append(dict(a["corners"][3]["measurements"][0]))
        self.assertFalse(cd.reproduction(a, b)["bit_identical"])
        a = _env()
        a["corners"][3]["measurements"] = "bad"
        self.assertFalse(cd.reproduction(a, b)["bit_identical"])

    def _null(self, env, name, only=None):
        for i, c in enumerate(env["corners"]):
            if only is None or i == only:
                for m in c["measurements"]:
                    if m["name"] == name:
                        m["value"] = None

    def test_reproduction_null_null_pair_not_compared(self):
        # issue #532: a None/None pair is not evidence of identity
        a, b = _env(), _env()
        self._null(a, "td_od1_ns", only=7)
        self._null(b, "td_od1_ns", only=7)
        rep = cd.reproduction(a, b)
        self.assertEqual(rep["values_compared"], 45 * 10 + 45 * len(cd.GATES) - 1)
        self.assertEqual(rep["unmeasured"],
                         [{"point": cd.key_label(cd.expected_keys()[7]),
                           "measurement": "td_od1_ns"}])
        self.assertEqual(rep["mismatches"], [])

    def test_reproduction_null_on_one_side_is_mismatch(self):
        a, b = _env(), _env()
        self._null(a, "td_od1_ns", only=7)
        rep = cd.reproduction(a, b)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(rep["values_compared"], 45 * 10 + 45 * len(cd.GATES) - 1)
        self.assertEqual(rep["unmeasured"], [])
        self.assertEqual(len(rep["mismatches"]), 1)
        self.assertEqual(rep["mismatches"][0]["measurement"], "td_od1_ns")

    def test_reproduction_all_null_values_not_bit_identical(self):
        a, b = _env(), _env()
        for env in (a, b):
            for c in env["corners"]:
                for m in c["measurements"]:
                    m["value"] = None
        rep = cd.reproduction(a, b)
        self.assertEqual(rep["values_compared"], 0)
        self.assertFalse(rep["bit_identical"])
        self.assertEqual(len(rep["unmeasured"]), 45 * (10 + len(cd.GATES)))

    def test_reproduction_markdown_names_unmeasured(self):
        a, b = _env(), _env()
        self._null(a, "td_od1_ns", only=7)
        self._null(b, "td_od1_ns", only=7)
        md = cd.render_markdown({"series": "s", "reference_campaign": "c", "conditions": {},
                                 "reproduction": cd.reproduction(a, b)})
        self.assertIn("1 unmeasured value pair", md)
        self.assertNotIn("BIT-IDENTICAL", md)

    def test_vcm_probe_rejections(self):
        keys = cd.expected_keys()
        bad = [float("nan"), float("inf"), float("-inf"), True, False, None, "0.6", [0.6], {}]
        for v in bad:
            with self.subTest(v=v):
                env = _env({keys[2]: {"vcm": v}})
                s = cd.summarize(cd.load_points(env, 0.6))
                self.assertEqual(s["points_valid"], 44)
                self.assertEqual(len(s["rejected"]), 1)
                self.assertIn("vcm_meas", s["rejected"][0]["reason"])
        env = _env({keys[2]: {"drop": "vcm_meas"}})
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 44)
        self.assertIn("vcm_meas", s["rejected"][0]["reason"])

    def test_vcm_probe_controls(self):
        keys = cd.expected_keys()
        env = _env({keys[0]: {"vcm": 0.6 + 5e-7}, keys[1]: {"vcm": 0.7}})
        s = cd.summarize(cd.load_points(env, 0.6))
        self.assertEqual(s["points_valid"], 44)
        self.assertIn("does not match", s["rejected"][0]["reason"])


if __name__ == "__main__":
    unittest.main()

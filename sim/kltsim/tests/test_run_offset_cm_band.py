"""Orchestration tests for sim/run_offset_cm_band.py (issues #186, #194).
Stdlib only; kcli._submit, kcli._last_attempt_refused_at_cap and time.sleep
are patched."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import run_offset_cm_band as rcb  # noqa: E402
from kltsim import cli as kcli  # noqa: E402
from kltsim import cmband  # noqa: E402

COND = cmband.CONDITIONS[0].name
TAGS = cmband.part_tags()


def _args(series_dir, **kw):
    d = dict(series="s", condition=COND, part=None, skip_existing=False,
             retry_refused=0, retry_wait=7, process="mos_tt", force=False)
    d.update(kw)
    return argparse.Namespace(**d)


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.series = Path(tmp.name)
        p = mock.patch.object(cmband, "SERIES_DIR", self.series.parent)
        p.start()
        self.addCleanup(p.stop)
        self.args = _args(self.series, series=self.series.name)
        self.calls, self.codes, self.refused = [], [], []
        self.out_dirs, self.sleeps = [], []
        for obj, name, fn in (
                (kcli, "_submit", self._submit),
                (kcli, "_last_attempt_refused_at_cap", self._refused),
                (time, "sleep",
                 self.sleeps.append)):
            p = mock.patch.object(obj, name, fn)
            p.start()
            self.addCleanup(p.stop)

    def _submit(self, request, out_dir, tag, args, extra=None):
        self.calls.append((tag, extra["kind"]))
        self.out_dirs.append(out_dir)
        return self.codes.pop(0) if self.codes else 0

    def _refused(self, out_dir):
        return self.refused.pop(0) if self.refused else False

    @property
    def cond_dir(self):
        return self.series / COND

    def make_requests(self, tags=TAGS):
        self.cond_dir.mkdir(parents=True, exist_ok=True)
        for t in tags:
            (self.cond_dir / f"{t}.request.json").write_text("{}")

    def envelope(self, tag, text="{}"):
        self.cond_dir.mkdir(parents=True, exist_ok=True)
        path = self.cond_dir / f"{tag}.envelope.json"
        path.write_text(text)
        return path

    def capture(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = rcb.cmd_run(self.args)
        return code, err.getvalue()


class RetryTests(Base):
    def go(self, retry):
        self.args.retry_refused = retry
        return rcb._submit_with_retry(Path("r"), Path("o"), "t", self.args, {"kind": "k"})

    def test_success_first_try(self):
        self.assertEqual(self.go(3), 0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.sleeps, [])

    def test_refused_then_success(self):
        self.codes, self.refused = [2, 0], [True]
        self.assertEqual(self.go(3), 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.sleeps, [7])

    def test_refused_through_exhaustion(self):
        self.codes, self.refused = [2] * 9, [True] * 9
        self.assertEqual(self.go(2), 2)
        self.assertEqual(len(self.calls), 3)  # 1 try + 2 retries
        self.assertEqual(self.sleeps, [7, 7])

    def test_no_retry_budget_submits_once(self):
        self.codes, self.refused = [2], [True]
        self.assertEqual(self.go(0), 2)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.sleeps, [])

    def test_non_cap_failure_not_retried(self):
        self.codes, self.refused = [5], [False]
        self.assertEqual(self.go(3), 5)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.sleeps, [])


class RunTests(Base):
    def test_submits_every_part(self):
        self.make_requests()
        self.assertEqual(rcb.cmd_run(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], TAGS)
        self.assertTrue(all(c[1] == "campaign" for c in self.calls))

    def test_missing_request_errors_without_submitting(self):
        self.make_requests(TAGS[:0])
        self.assertEqual(rcb.cmd_run(self.args), 1)
        self.assertEqual(self.calls, [])

    def test_missing_request_at_later_tag_submits_nothing(self):
        self.make_requests(TAGS[:-1])
        code, err = self.capture()
        self.assertEqual(code, 1)
        self.assertEqual(self.calls, [])  # preflight precedes any submission
        self.assertIn(f"no request at {self.cond_dir / f'{TAGS[-1]}.request.json'}", err)
        self.assertIn("`build`", err)

    def test_skip_existing_skips_only_enveloped_parts(self):
        self.make_requests()
        self.envelope(TAGS[0])
        self.args.skip_existing = True
        self.assertEqual(rcb.cmd_run(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], TAGS[1:])

    def test_default_mode_refuses_existing_envelope(self):
        self.make_requests()
        path = self.envelope(TAGS[0], '{"recorded": true}')
        code, err = self.capture()
        self.assertEqual(code, 1)
        self.assertEqual(self.calls, [])
        self.assertIn(TAGS[0], err)
        self.assertIn(str(path), err)
        self.assertIn("--skip-existing", err)
        self.assertIn("--series", err)
        self.assertEqual(path.read_text(), '{"recorded": true}')  # untouched

    def test_conflict_at_last_tag_submits_nothing(self):
        self.make_requests()
        self.envelope(TAGS[-1])
        code, _ = self.capture()
        self.assertEqual(code, 1)
        self.assertEqual(self.calls, [])

    def test_names_every_conflicting_tag(self):
        self.make_requests()
        self.envelope(TAGS[0])
        self.envelope(TAGS[-1])
        code, err = self.capture()
        self.assertEqual(code, 1)
        self.assertIn(TAGS[0], err)
        self.assertIn(TAGS[-1], err)

    def test_resume_all_enveloped_is_successful_noop(self):
        for t in TAGS:
            self.envelope(t)
        self.args.skip_existing = True
        code, err = self.capture()
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])
        for t in TAGS:
            self.assertIn(f"{t}: envelope present, skipped", err)

    def test_resume_skipped_part_needs_no_request(self):
        self.envelope(TAGS[0])
        self.make_requests(TAGS[1:])
        self.args.skip_existing = True
        self.assertEqual(rcb.cmd_run(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], TAGS[1:])

    def test_unselected_parts_are_ignored(self):
        self.envelope(TAGS[0])  # unselected envelope does not refuse
        self.make_requests([TAGS[1]])
        self.args.part = [TAGS[1]]
        self.assertEqual(rcb.cmd_run(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], [TAGS[1]])

    def test_force_does_not_override_refusal(self):
        self.make_requests()
        path = self.envelope(TAGS[0], '{"recorded": true}')
        self.args.force = True
        code, _ = self.capture()
        self.assertEqual(code, 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(path.read_text(), '{"recorded": true}')

    def test_force_resume_still_skips_envelope(self):
        self.make_requests()
        path = self.envelope(TAGS[0], '{"recorded": true}')
        self.args.force = True
        self.args.skip_existing = True
        self.assertEqual(rcb.cmd_run(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], TAGS[1:])
        self.assertEqual(path.read_text(), '{"recorded": true}')

    def test_part_filter(self):
        self.make_requests()
        self.args.part = [TAGS[1]]
        rcb.cmd_run(self.args)
        self.assertEqual([c[0] for c in self.calls], [TAGS[1]])

    def test_exit_code_is_max_of_parts(self):
        self.make_requests()
        self.codes = [0, 4, 3] + [0] * len(TAGS)
        self.assertEqual(rcb.cmd_run(self.args), 4)

    def test_per_part_failures_named_and_max_preserved(self):
        self.make_requests()
        self.codes = [4] + [0] * (len(TAGS) - 2) + [3]
        code, err = self.capture()
        self.assertEqual(code, 4)  # aggregate stays max of part codes
        self.assertEqual(len(self.calls), len(TAGS))  # later parts still run
        self.assertIn(f"{TAGS[0]}: part failed with final code 4", err)
        self.assertIn(f"{TAGS[-1]}: part failed with final code 3", err)


class CliTests(Base):
    def test_run_help_documents_refusal_and_resume(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            rcb.main(["run", "--help"])
        self.assertEqual(raised.exception.code, 0)
        text = out.getvalue()
        self.assertIn("--skip-existing", text)
        self.assertIn("resume", text)
        self.assertIn("append-only", text)
        self.assertIn("--series", text)

    def test_main_run_submits_every_part(self):
        self.make_requests()
        self.assertEqual(
            rcb.main(["run", "--series", self.series.name, "--condition", COND]), 0)
        self.assertEqual([c[0] for c in self.calls], TAGS)

    def test_main_run_refuses_conflict_without_submissions(self):
        self.make_requests()
        self.envelope(TAGS[2])
        self.assertEqual(
            rcb.main(["run", "--series", self.series.name, "--condition", COND]), 1)
        self.assertEqual(self.calls, [])


class ControlRepeatGuardTests(Base):
    def guard(self, fn, tag):
        ctl = self.series / "controls"
        ctl.mkdir(parents=True)
        (ctl / f"{tag}.envelope.json").write_text("{}")
        self.assertEqual(fn(self.args), 1)
        self.assertEqual(self.calls, [])
        self.assertEqual([p.name for p in ctl.iterdir()], [f"{tag}.envelope.json"])

    def test_control_refuses_when_envelope_exists(self):
        self.guard(rcb.cmd_control, f"negctrl.{COND}")

    def test_repeat_refuses_when_envelope_exists(self):
        self.guard(rcb.cmd_repeat, f"repeat.{COND}.mos_tt")


if __name__ == "__main__":
    unittest.main()


def _mc_envelope(section, points, *, seeds=None, vcm=0.6):
    """A synthetic klt sim Monte-Carlo envelope with explicit per-sample
    seeds: ``points`` maps (supply, temp) -> list of (seed, vos_mv-or-None).
    ``None`` vos marks an errored draw (the parent campaign's abort shape)."""
    corners = []
    for (supply, temp), samples in points.items():
        base = f"{section}/{supply:.3f}V/{temp:g}C"
        for k, (seed, vos) in enumerate(samples):
            errored = vos is None
            lowcount = None if errored else (vos / 1e3 + 0.048) / 0.003 + 0.5
            meas = []
            for name, value, unit in (("vdd_meas", supply, "V"),
                                      ("temp_meas", float(temp), "C"),
                                      ("lowcount", lowcount, "levels"),
                                      ("vos_mv", vos, "mV"),
                                      ("vcm_meas", vcm, "V")):
                entry = {"name": name, "unit": unit,
                         "value": value, "status": "error" if errored else "pass",
                         "margin": None}
                meas.append(entry)
            corners.append({
                "corner_id": f"{base}/mc{k}",
                "process": section,
                "supply_v": {"vsup": supply},
                "temperature_c": temp,
                "status": "error" if errored else "pass",
                "runtime_s": 2.5,
                "measurements": meas,
                "diagnostics": ([] if not errored else
                                [{"severity": "error", "code": "measurement",
                                  "message": "measurement 'vos_mv' produced no value"}]),
                "monte_carlo": {"sample_index": k, "seed": seed},
            })
    return {"status": "pass", "corners": corners}


def _pop(n=60, scale=3.0, shift=0.0):
    return [shift + scale * math.sin(1.7 * k + 0.3) for k in range(n)]


def _seed(section, supply, temp, k):
    return int(hashlib.sha256(f"{section}:{supply}:{temp}:{k}".encode()).hexdigest()[:8], 16)


class SupplementComposition(unittest.TestCase):
    def test_supplement_points_are_the_two_rejected_ones(self):
        self.assertEqual(cmband.SUPPLEMENT_POINTS,
                         (("mos_tt_mismatch", 1.32, -40.0),
                          ("mos_sf_mismatch", 1.2, -40.0)))
        self.assertEqual(cmband.supplement_sections(),
                         ["mos_tt_mismatch", "mos_sf_mismatch"])

    def test_retained_grid_is_an_odometer_prefix(self):
        from kltsim.benches import SUPPLIES_V, TEMPERATURES_C
        full = [(s, t) for s in SUPPLIES_V for t in TEMPERATURES_C]
        for section, supply, temp in cmband.SUPPLEMENT_POINTS:
            grid = cmband.supplement_grid(section)
            self.assertEqual(grid[-1], (supply, temp))
            self.assertEqual(grid, full[:full.index((supply, temp)) + 1])
        self.assertEqual(len(cmband.supplement_grid("mos_tt_mismatch")), 7)
        self.assertEqual(len(cmband.supplement_grid("mos_sf_mismatch")), 4)

    def test_excludes_drop_exactly_the_post_target_tail(self):
        from kltsim.benches import SUPPLIES_V, TEMPERATURES_C
        for section, supply, temp in cmband.SUPPLEMENT_POINTS:
            expected = [{"supply_v": {"vsup": s}, "temperature_c": t}
                        for s in SUPPLIES_V for t in TEMPERATURES_C
                        if (s, t) > (supply, temp)]
            self.assertEqual(cmband.supplement_excludes(section), expected)

    def test_request_injects_max_step_and_keeps_the_parent_basis(self):
        req = cmband.compose_supplement_request(
            cmband.condition("vcm-m050"), cmband.BODY_NAME, "mos_tt_mismatch")
        self.assertEqual(req["analysis"], {"kind": "tran", "args": "100p 990n 0 20p"})
        self.assertEqual(req["corners"], {
            "process": ["mos_tt_mismatch"],
            "supply_v": {"vsup": [1.08, 1.2, 1.32]},
            "temperature_c": [-40, 27, 125]})
        self.assertEqual(req["monte_carlo"]["n"], 60)
        self.assertEqual(req["monte_carlo"]["seed"], 20260916)
        self.assertEqual(req["backend"], "batch")
        self.assertEqual(req["options"], {"timeout_s": 300, "keep_artifacts": True})
        self.assertEqual(req["_supplement"]["kind"], "max-step-supplement")
        self.assertEqual(req["_supplement"]["parent_campaign"], cmband.SUPPLEMENT_PARENT)
        self.assertEqual(req["_supplement"]["target"],
                         {"process": "mos_tt_mismatch", "supply_v": 1.32,
                          "temperature_c": -40.0})
        names = [m["name"] for m in req["measurements"]]
        self.assertEqual(names, ["vdd_meas", "temp_meas", "vbias_mv", "lowcount",
                                 "vos_mv", "vcm_meas"])

    def test_seed_contract_identical_across_conditions(self):
        """Structural pairing: for one section, the three conditions'
        requests enumerate the same corners in the same order with the same
        monte_carlo basis, so corner/sample -> seed is condition-invariant."""
        per_cond = {}
        for cond in cmband.CONDITIONS:
            req = cmband.compose_supplement_request(
                cond, cmband.BODY_NAME, "mos_tt_mismatch")
            per_cond[cond.name] = (req["corners"], req["exclude"],
                                   req["monte_carlo"], req["analysis"])
        self.assertEqual(len({repr(v) for v in per_cond.values()}), 1)


class HistoricalBuildUnchanged(unittest.TestCase):
    """Issue #89's supplementary mode must not perturb the issue #79 build:
    current code regenerates the committed parent campaign byte for byte."""

    PARENT = cmband.SERIES_DIR / "20261009-5185f52"

    def test_parent_inputs_regenerate_byte_identically(self):
        from kltsim import build as build_mod
        from kltsim.benches import OFFSET_MC
        # Runs in CI too: the parent's vcm-*/*.spice and *.request.json are in
        # the harness-unit-tests sparse cone (ci.yml; sim/README.md audit).
        self.assertTrue(self.PARENT.is_dir(), "committed parent campaign missing")
        for cond in cmband.CONDITIONS:
            body = self.PARENT / cond.name / cmband.BODY_NAME
            self.assertEqual(body.read_bytes(),
                             cmband.compose_cm_body(cond, build_mod.BATCH_OSDI_DIR)
                             .encode("utf-8"))
            for section in OFFSET_MC.process_sections:
                req = self.PARENT / cond.name / f"{cmband.BENCH_NAME}.{section}.request.json"
                gen = json.dumps(cmband.compose_cm_request(
                    cond, cmband.BODY_NAME, section), indent=2) + "\n"
                self.assertEqual(req.read_text(), gen)

    def test_historical_build_has_no_supplement_fields(self):
        from kltsim.benches import OFFSET_MC
        for cond in cmband.CONDITIONS:
            for section in OFFSET_MC.process_sections:
                req = cmband.compose_cm_request(cond, cmband.BODY_NAME, section)
                self.assertNotIn("exclude", req)
                self.assertNotIn("_supplement", req)
                self.assertEqual(req["analysis"]["args"], "100p 990n")


class SupplementBuildTests(Base):
    def setUp(self):
        super().setUp()
        self.args.condition = None

    def test_build_writes_body_and_two_requests_per_condition(self):
        self.assertEqual(rcb.cmd_supplement_build(self.args), 0)
        for cond in cmband.CONDITIONS:
            d = self.series / cond.name
            self.assertEqual(sorted(p.name for p in d.iterdir()), [
                "offset_cm.body.spice",
                "offset_cm.mos_sf_mismatch.request.json",
                "offset_cm.mos_tt_mismatch.request.json"])

    def test_build_is_idempotent(self):
        self.assertEqual(rcb.cmd_supplement_build(self.args), 0)
        before = {p: p.read_bytes() for p in self.series.rglob("*") if p.is_file()}
        self.assertEqual(rcb.cmd_supplement_build(self.args), 0)
        after = {p: p.read_bytes() for p in self.series.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_build_refuses_conflicting_existing_input(self):
        self.assertEqual(rcb.cmd_supplement_build(self.args), 0)
        victim = self.series / COND / "offset_cm.mos_tt_mismatch.request.json"
        victim.write_text("{}\n")
        self.assertEqual(rcb.cmd_supplement_build(self.args), 1)
        self.assertEqual(victim.read_text(), "{}\n")  # nothing rewritten


class SupplementRunTests(Base):
    def setUp(self):
        super().setUp()
        self.args.condition = None

    def make_requests(self):
        for cond in cmband.CONDITIONS:
            d = self.series / cond.name
            d.mkdir(parents=True)
            for section in cmband.supplement_sections():
                (d / f"offset_cm.{section}.request.json").write_text("{}")

    def test_submits_both_sections_at_all_three_conditions(self):
        self.make_requests()
        self.assertEqual(rcb.cmd_supplement_run(self.args), 0)
        self.assertEqual(len(self.calls), 6)
        self.assertTrue(all(c[1] == "max-step-supplement" for c in self.calls))
        # each (condition, section) pair submitted exactly once, into its
        # own condition directory
        pairs = sorted(zip(self.out_dirs, (c[0] for c in self.calls)))
        self.assertEqual(len(set(pairs)), 6)
        self.assertEqual({p[1] for p in pairs},
                         {f"offset_cm.{s}" for s in cmband.supplement_sections()})
        self.assertEqual({p[0].name for p in pairs},
                         {c.name for c in cmband.CONDITIONS})

    def test_refuses_when_any_envelope_exists(self):
        self.make_requests()
        (self.series / COND / "offset_cm.mos_tt_mismatch.envelope.json").write_text("{}")
        self.assertEqual(rcb.cmd_supplement_run(self.args), 1)
        self.assertEqual(self.calls, [])

    def test_missing_request_errors_without_submitting(self):
        self.series.joinpath(COND).mkdir(parents=True)
        self.assertEqual(rcb.cmd_supplement_run(self.args), 1)
        self.assertEqual(self.calls, [])

    def test_failure_propagates_as_max_exit_code(self):
        self.make_requests()
        self.codes = [0, 4] + [0] * 10
        self.assertEqual(rcb.cmd_supplement_run(self.args), 4)


class SupplementReportTests(Base):
    """End-to-end report fixtures over synthetic envelopes: a parent
    campaign tree and a supplement series under the patched SERIES_DIR."""

    def setUp(self):
        super().setUp()
        # SERIES_DIR is patched to self.series.parent, so the synthetic
        # parent campaign lives BESIDE the supplement series, as in sim/.
        self.parent = self.series.parent / cmband.SUPPLEMENT_PARENT
        self.supp = self.series

    def write_pair(self, section, cond, *, supp_points, parent_points):
        for series, points in ((self.supp, supp_points), (self.parent, parent_points)):
            d = series / cond.name
            d.mkdir(parents=True, exist_ok=True)
            (d / f"offset_cm.{section}.envelope.json").write_text(
                json.dumps(_mc_envelope(section, points, vcm=cond.vcm_v())))

    def full_pair(self, section, cond, *, shift=0.0, bad_seed=False, abort_k=None,
                  supp_abort_k=None):
        """Retained-grid populations: parent at the original step, supplement
        shifted by ``shift`` mV; ``abort_k`` marks one aborted draw in the
        parent's target population, ``supp_abort_k`` one in the supplement's
        (the remaining-failure case, reported as-is)."""
        supply, temp = dict((s, (v, t)) for s, v, t in cmband.SUPPLEMENT_POINTS)[section]
        grid = cmband.supplement_grid(section)
        parent, supp = {}, {}
        for (s, t) in grid:
            rows = [(_seed(section, s, t, k), v) for k, v in enumerate(_pop())]
            if abort_k is not None and (s, t) == (supply, temp):
                rows[abort_k] = (rows[abort_k][0], None)
            parent[(s, t)] = rows
            shifted = _pop(shift=shift if (s, t) == (supply, temp) else 0.0)
            srows = [(_seed(section, s, t, k) + (1 if bad_seed else 0), v)
                     for k, v in enumerate(shifted)]
            if supp_abort_k is not None and (s, t) == (supply, temp):
                srows[supp_abort_k] = (srows[supp_abort_k][0], None)
            supp[(s, t)] = srows
        self.write_pair(section, cond, supp_points=supp, parent_points=parent)

    def test_neutral_sensitivity_and_completion(self):
        for section in cmband.supplement_sections():
            for cond in cmband.CONDITIONS:
                self.full_pair(section, cond, abort_k=12 if cond.name == "vcm-m050" else None)
        result = cmband.compare_supplement(self.supp)
        self.assertEqual(result["missing_envelopes"], [])
        self.assertEqual(len(result["populations"]), 6)
        complete = [t for t in result["conclusion"]["targets_complete"] if t["valid"]]
        self.assertEqual(len(complete), 6)
        for p in result["populations"]:
            self.assertEqual(p["stats"]["n"], 60)
            self.assertIsNone(p["stats"]["rejected"])
            self.assertTrue(p["pairing_vs_parent"]["seeds_paired"])
        # parent m050 targets show the abort; nom/p050 were valid
        m050 = [p for p in result["populations"] if p["condition"] == "vcm-m050"]
        self.assertTrue(all("untrusted draw" in (p["parent_status"] or "") for p in m050))
        self.assertTrue(all(
            p["pairing_vs_parent"]["seeds_paired"] for p in result["populations"]))
        c = result["conclusion"]
        self.assertTrue(c["pairing_all_matched"])
        self.assertEqual(c["pairs_identical"], c["pairs_compared"])
        self.assertEqual(c["max_abs_delta_mv"], 0.0)
        self.assertIn("remains open", c["cause"])
        md = cmband.render_supplement_markdown(result)
        self.assertIn("max-step supplement", md)
        self.assertIn("bit-identical", md)

    def test_non_neutral_sensitivity_is_reported(self):
        for section in cmband.supplement_sections():
            for cond in cmband.CONDITIONS:
                self.full_pair(section, cond, shift=1.25)
        result = cmband.compare_supplement(self.supp)
        c = result["conclusion"]
        # only the 6 target populations shifted; the 9 padding populations
        # (the seed contract's odometer prefix) stay bit-identical
        self.assertEqual(c["pairs_identical"], c["pairs_compared"] - 6 * 60)
        self.assertGreater(c["max_abs_delta_mv"], 1.0)
        target_rows = [s for s in result["sensitivity"] if s["target"]]
        self.assertTrue(all(
            abs(s["sensitivity"]["delta_mean_mv"] - 1.25) < 1e-9 for s in target_rows))
        md = cmband.render_supplement_markdown(result)
        self.assertIn("+1.2500", md)

    def test_seed_mismatch_breaks_pairing(self):
        for section in cmband.supplement_sections():
            for cond in cmband.CONDITIONS:
                self.full_pair(section, cond, bad_seed=True)
        result = cmband.compare_supplement(self.supp)
        self.assertFalse(result["conclusion"]["pairing_all_matched"])
        for p in result["populations"]:
            self.assertFalse(p["pairing_vs_parent"]["seeds_paired"])
            self.assertGreater(p["pairing_vs_parent"]["seed_mismatches"], 0)

    def test_retained_failure_reported_as_is(self):
        for section in cmband.supplement_sections():
            for cond in cmband.CONDITIONS:
                self.full_pair(section, cond,
                               abort_k=3 if cond.name == "vcm-m050" else None,
                               supp_abort_k=7 if cond.name == "vcm-m050" else None)
        result = cmband.compare_supplement(self.supp)
        bad = [p for p in result["populations"]
               if p["condition"] == "vcm-m050" and p["stats"]["rejected"]]
        self.assertEqual(len(bad), 2)
        self.assertIn("untrusted draw", bad[0]["stats"]["rejected"])
        self.assertTrue(result["conclusion"]["incomplete"])
        self.assertIn("reported as-is", result["conclusion"]["cause"])
        md = cmband.render_supplement_markdown(result)
        self.assertIn("Failures, reported as-is", md)

    def test_missing_envelope_fails_the_command(self):
        self.full_pair("mos_tt_mismatch", cmband.condition("vcm-m050"))
        args = argparse.Namespace(series=self.supp.name, parent=cmband.SUPPLEMENT_PARENT)
        self.assertEqual(rcb.cmd_supplement_report(args), 1)
        result = json.loads((self.supp / "supplement-report.json").read_text())
        self.assertEqual(len(result["missing_envelopes"]), 5)
        md = (self.supp / "supplement-report.md").read_text()
        self.assertIn("Missing or malformed envelopes", md)

    def test_malformed_envelope_fails_the_command(self):
        for section in cmband.supplement_sections():
            for cond in cmband.CONDITIONS:
                self.full_pair(section, cond)
        d = self.supp / "vcm-nom"
        (d / "offset_cm.mos_tt_mismatch.envelope.json").write_text("{not json")
        args = argparse.Namespace(series=self.supp.name, parent=cmband.SUPPLEMENT_PARENT)
        self.assertEqual(rcb.cmd_supplement_report(args), 1)
        result = json.loads((self.supp / "supplement-report.json").read_text())
        self.assertTrue(any("malformed" in m for m in result["missing_envelopes"]))

    def test_no_data_run_reads_zero_valid_and_gzip_envelopes(self):
        """A batch run that produced no draws: N valid is 0/60 (not the
        requested 60), the seed check is labelled request-level, and the
        byte-exact ``.envelope.json.gz`` form loads with the plain JSON's hash."""
        import gzip
        for section in cmband.supplement_sections():
            for cond in cmband.CONDITIONS:
                self.full_pair(section, cond)
                grid = cmband.supplement_grid(section)
                dead = {(s, t): [(_seed(section, s, t, k), None) for k in range(60)]
                        for (s, t) in grid}
                path = self.supp / cond.name / f"offset_cm.{section}.envelope.json"
                raw = json.dumps(_mc_envelope(section, dead, vcm=cond.vcm_v())).encode()
                path.write_bytes(raw)
        gz_path = self.supp / "vcm-nom" / "offset_cm.mos_tt_mismatch.envelope.json"
        raw = gz_path.read_bytes()
        gz_path.with_name(gz_path.name + ".gz").write_bytes(gzip.compress(raw))
        gz_path.unlink()
        result = cmband.compare_supplement(self.supp)
        self.assertEqual(result["missing_envelopes"], [])
        self.assertEqual(result["sources"]["vcm-nom/offset_cm.mos_tt_mismatch"]
                         ["envelope_sha256"], hashlib.sha256(raw).hexdigest())
        for p in result["populations"]:
            self.assertEqual(p["n_valid"], 0)
            self.assertTrue(p["pairing_vs_parent"]["seeds_paired"])
        self.assertEqual(result["conclusion"]["pairs_compared"], 0)
        md = cmband.render_supplement_markdown(result)
        self.assertIn("| 0/60 |", md)
        self.assertNotIn("| 60/60 |", md)
        self.assertIn("request seeds = parent", md)
        self.assertIn("structural, request-level", md)
        self.assertIn("0/6 populations valid", md)

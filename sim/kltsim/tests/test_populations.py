"""Population-integrity regressions for the main compliance reducers and the
yield collector (issue #245). Stdlib only."""

from __future__ import annotations

import copy
import unittest

from kltsim import grade
from kltsim import populations as pops
from kltsim import yield_reports as yr
from kltsim.tests.test_grade import (
    GRID, _body, _evidence, _row, _spec, noise_envelope, offset_envelope)
from kltsim.tests.test_yield_reports import offset_bench

POINT = ("ss", 1.2, 27)


def _at_point(env, point=POINT):
    return [c for c in env["corners"]
            if c.get("monte_carlo") is not None
            and grade._corner_key(c) == (point[0], round(point[1], 6), point[2])]


def _drop(env, corner):
    env["corners"] = [c for c in env["corners"] if c is not corner]


class _Base:
    BENCH = ""
    ROW = ""

    def setUp(self):
        self.body = _body(self.BENCH)
        self.dut = grade.load_dut_reference()

    def grade_env(self, env):
        return self.grade_ev(_evidence(self.BENCH, env, self.body))

    def grade_ev(self, ev):
        return grade.grade(_spec([_row(self.ROW)]), {self.BENCH: ev}, self.dut)["rows"][0]

    def assert_point_rejected(self, env, fragment=None):
        row = self.grade_env(env)
        self.assertNotEqual(row["target_verdict"], grade.PASS)
        bad = row["target"]["points_missing_or_invalid"]
        self.assertTrue(bad, row["target"])
        if fragment:
            self.assertTrue(any(fragment in b["why"] for b in bad), bad)
        return row

    def test_valid_population_passes(self):
        self.assertEqual(self.grade_env(self.make())["target_verdict"], grade.PASS)

    def test_deleting_one_sample_is_not_pass(self):
        env = self.make()
        _drop(env, _at_point(env)[7])
        self.assert_point_rejected(env, "sample records")

    def test_one_sample_per_point_is_not_pass(self):
        env = self.make()
        env["corners"] = [c for c in env["corners"] if c["monte_carlo"]["sample_index"] == 0]
        self.assert_point_rejected(env)

    def test_adding_a_sample_is_not_pass(self):
        env = self.make()
        extra = copy.deepcopy(_at_point(env)[0])
        extra["monte_carlo"]["sample_index"] = 10_000
        extra["corner_id"] = extra["corner_id"].rsplit("/mc", 1)[0] + "/mc10000"
        env["corners"].append(extra)
        self.assert_point_rejected(env, "sample records")

    def _duplicate(self, reverse=False):
        env = self.make()
        pt = _at_point(env)
        pt[5]["monte_carlo"]["sample_index"] = pt[4]["monte_carlo"]["sample_index"]
        if reverse:
            env["corners"].reverse()
        return env

    def test_duplicate_index_is_rejected_in_any_order(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.assert_point_rejected(self._duplicate(reverse=reverse), "more than once")

    def test_duplicate_index_across_envelopes_is_rejected_in_either_order(self):
        for first in (True, False):
            with self.subTest(first=first):
                env = self._duplicate()
                moved = _at_point(env)[5]
                env["corners"] = [c for c in env["corners"] if c is not moved]
                other = {k: v for k, v in env.items() if k not in ("corners", "measurements")}
                other["corners"], other["measurements"] = [moved], []
                envs = [(self.BENCH, env), ("late", other)]
                ev = grade.BenchEvidence(name=self.BENCH, body_text=self.body,
                                         envelopes=envs if first else envs[::-1])
                self.assertNotEqual(self.grade_ev(ev)["target_verdict"], grade.PASS)

    def test_malformed_sample_metadata_is_rejected(self):
        for bad in ("3", True, -1, 2.0, None):
            with self.subTest(index=bad):
                env = self.make()
                _at_point(env)[3]["monte_carlo"]["sample_index"] = bad
                self.assert_point_rejected(env, "sample_index")
        env = self.make()
        _at_point(env)[3]["monte_carlo"] = {}
        self.assert_point_rejected(env, "sample_index")

    def test_conflicting_base_ids_are_rejected(self):
        env = self.make()
        c = _at_point(env)[9]
        c["corner_id"] = "other_base/" + c["corner_id"].split("/", 1)[1]
        self.assert_point_rejected(env, "several base corners")

    def test_only_the_affected_point_is_rejected(self):
        env = self.make()
        _drop(env, _at_point(env)[0])
        row = self.grade_env(env)
        self.assertEqual(len(row["target"]["points_missing_or_invalid"]), 1)

    def test_inconsistent_summary_counts_are_rejected(self):
        for mutate in (lambda e: e.update(errored=None), lambda e: e.pop("errored"),
                       lambda e: e.update(errored="0")):
            with self.subTest():
                env = self.make()
                for m in env["measurements"]:
                    for e in m["monte_carlo"]["by_corner"]:
                        mutate(e)
                self.assert_point_rejected(env)

    def test_summary_hiding_errored_records_is_rejected(self):
        env = self.make()
        _at_point(env)[2]["status"] = "error"  # summary still says errored = 0
        self.assert_point_rejected(env)


class OffsetPopulationTests(_Base, unittest.TestCase):
    BENCH, ROW = "offset_mc", "1"

    def make(self):
        return offset_envelope(self.body)

    def test_numerical_miss_elsewhere_keeps_fail_precedence(self):
        env = offset_envelope(self.body, stddev=lambda p, v, t: 30.0 if p == "ff" else 3.0)
        _drop(env, _at_point(env)[0])  # an invalid population at a different point
        self.assertEqual(self.grade_env(env)["target_verdict"], grade.FAIL)


class NoisePopulationTests(_Base, unittest.TestCase):
    BENCH, ROW = "transient_noise", "2"

    def make(self):
        return noise_envelope(self.body, kplus=lambda *a: 78, kminus=lambda *a: 2)

    def test_duplicate_index_with_distinct_raw_noise_is_rejected(self):
        # The raw-noise independence check cannot see this: draws are distinct.
        env = self._duplicate()
        a, b = _at_point(env)[4], _at_point(env)[5]
        draw = lambda c: next(m["value"] for m in c["measurements"] if m["name"] == "vn0_a")
        self.assertNotEqual(draw(a), draw(b))
        self.assert_point_rejected(env, "more than once")


class SharedHelperTests(unittest.TestCase):
    def test_summary_count_consistency(self):
        recs = [{"status": "pass"}] * 4 + [{"status": "error"}]
        self.assertIsNone(pops.check_summary({"n": 4, "errored": 1}, recs))
        self.assertIn("do not match", pops.check_summary({"n": 5, "errored": 1}, recs))
        self.assertIn("errored", pops.check_summary({"n": 5, "errored": 0}, recs[:4] + [recs[4]]))
        for bad in ({"n": 5}, {"n": "5", "errored": 0}, {"n": True, "errored": 0},
                    {"n": 5.5, "errored": 0}, {"n": float("nan"), "errored": 0}):
            self.assertIn("malformed", pops.check_summary(bad, recs))

    def test_validate_point_is_order_invariant(self):
        cs = [{"corner_id": f"b/mc{k}", "monte_carlo": {"sample_index": k}} for k in range(3)]
        self.assertEqual(pops.validate_point(cs, 3), pops.validate_point(cs[::-1], 3))


class YieldCollectorPopulationTests(unittest.TestCase):
    def collect(self, bench):
        return yr.collect_populations(bench, "vos_mv", "mV", GRID, 60)

    @staticmethod
    def point(bench):
        return [c for c in bench.envelopes[0][1]["corners"]
                if c.get("monte_carlo") and grade._corner_key(c) == ("ss", 1.2, 27)]

    def test_valid_population_collects(self):
        self.assertEqual(len(self.collect(offset_bench())), 45)

    def _rejected(self, mutate, fragment):
        bench = offset_bench()
        mutate(bench, self.point(bench))
        with self.assertRaises(yr.YieldInputError) as cm:
            self.collect(bench)
        self.assertIn(fragment, str(cm.exception))

    def test_duplicate_index(self):
        def mutate(b, c):
            c[5]["monte_carlo"]["sample_index"] = c[4]["monte_carlo"]["sample_index"]
        self._rejected(mutate, "more than once")

    def test_conflicting_base_ids(self):
        def mutate(b, c):
            c[2]["corner_id"] = "x/" + c[2]["corner_id"].split("/", 1)[1]
        self._rejected(mutate, "several base corners")

    def test_malformed_index(self):
        def mutate(b, c):
            c[2]["monte_carlo"]["sample_index"] = True
        self._rejected(mutate, "sample_index")

    def test_deleted_sample(self):
        def mutate(b, c):
            b.envelopes[0][1]["corners"].remove(c[3])
        self._rejected(mutate, "59 draws")

    def test_added_sample(self):
        def mutate(b, c):
            extra = copy.deepcopy(c[0])
            extra["monte_carlo"]["sample_index"] = 999
            b.envelopes[0][1]["corners"].append(extra)
        self._rejected(mutate, "61 draws")


if __name__ == "__main__":
    unittest.main()

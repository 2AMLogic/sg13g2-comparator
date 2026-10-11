"""Stdlib-only tests for the issue #81 noise-split arithmetic."""

import math
import unittest
from statistics import NormalDist

from kltsim import noise_full as nf


class SigmaSeTest(unittest.TestCase):
    def test_sigma_recovers_known_slope(self):
        nd = NormalDist()
        sigma = 1.3  # mV
        od = 1.0
        p_plus, p_minus = nd.cdf(od / sigma), nd.cdf(-od / sigma)
        s, se = nf.sigma_se(p_plus, p_minus, 80, od)
        self.assertAlmostEqual(s, sigma, places=9)
        # ~13 % per-corner scatter at N = 80 near this operating point
        self.assertTrue(0.05 < se / s < 0.25, se / s)

    def test_se_shrinks_with_n(self):
        _, se80 = nf.sigma_se(0.78, 0.22, 80, 1.0)
        _, se320 = nf.sigma_se(0.78, 0.22, 320, 1.0)
        self.assertAlmostEqual(se80 / se320, 2.0, places=9)

    def test_unordered_rungs_rejected(self):
        with self.assertRaises(ValueError):
            nf.sigma_se(0.3, 0.7, 80, 1.0)


class QuadratureTest(unittest.TestCase):
    def test_independent_sources_close_exactly(self):
        s = nf.quadrature_split(1.2, 0.5, math.hypot(1.2, 0.5))
        self.assertAlmostEqual(s["closure"], 1.0)
        self.assertAlmostEqual(s["internal_increment"], 0.5)
        self.assertFalse(s["internal_increment_negative"])

    def test_total_below_front_end_is_scatter_not_negative(self):
        s = nf.quadrature_split(1.2, 0.5, 1.1)
        self.assertEqual(s["internal_increment"], 0.0)
        self.assertTrue(s["internal_increment_negative"])

    def test_split_without_internal_term_has_no_closure(self):
        s = nf.quadrature_split(1.2, None, 1.3)
        self.assertIsNone(s["closure"])
        self.assertIsNone(s["internal_alone"])


class SaturationAndControlTest(unittest.TestCase):
    def test_upper_bound_matches_rule_of_three(self):
        # 80/80 high => p >= 0.05**(1/80) = 0.9632 at 95 %  => z = 1.79
        ub = nf.sigma_upper_bound_95(80, 1.0)
        self.assertAlmostEqual(ub, 1.0 / NormalDist().inv_cdf(0.05 ** (1 / 80)))
        self.assertTrue(0.5 < ub < 0.6)

    def test_upper_bound_tightens_with_n(self):
        self.assertLess(nf.sigma_upper_bound_95(800, 1.0), nf.sigma_upper_bound_95(80, 1.0))

    def test_two_proportion_z(self):
        self.assertEqual(nf.two_proportion_z(1.0, 1.0, 80), 0.0)
        self.assertEqual(nf.two_proportion_z(0.5, 0.5, 80), 0.0)
        self.assertGreater(nf.two_proportion_z(0.9, 0.7, 80), 2.0)
        self.assertLess(nf.two_proportion_z(0.7, 0.9, 80), -2.0)


def _pt(sigma, se, shared=0):
    return {"sigma": sigma, "sigma_se": se, "p_plus": 0.8, "p_minus": 0.2, "n": 80,
            "samples_sharing_a_draw_with_another_point": shared, "problem": None}


NOTE = "6/9 samples repeat a raw noise draw also seen at ANOTHER grid point"


class GridUncertaintyTest(unittest.TestCase):
    def test_unequal_errors_bound_formula(self):
        u = nf.grid_mean_uncertainty([0.1, 0.2, 0.3])
        self.assertAlmostEqual(u["fully_correlated_bound"], 0.2)
        self.assertAlmostEqual(u["independent"], math.sqrt(0.14) / 3)
        self.assertGreaterEqual(u["fully_correlated_bound"], u["independent"])

    def test_equal_errors_independent_is_se_over_sqrt_n(self):
        u = nf.grid_mean_uncertainty([0.2] * 4)
        self.assertAlmostEqual(u["independent"], 0.1)
        self.assertAlmostEqual(u["fully_correlated_bound"], 0.2)

    def test_independent_points_report_no_shared_draws(self):
        s = nf._summarise([_pt(1.0, 0.1), _pt(1.2, 0.2)], [])
        self.assertTrue(s["complete"])
        self.assertNotIn("partial", s)
        self.assertEqual((s["shared_draw_samples"], s["shared_draw_points"]), (0, 0))
        self.assertAlmostEqual(s["grid_mean_se_fully_correlated_bound"], 0.15)
        self.assertNotIn("grid_mean_se", s)

    def test_shared_draw_notes_and_counts_survive(self):
        s = nf._summarise([_pt(1.0, 0.1, 3), _pt(1.2, 0.2, 3), _pt(1.1, 0.1, 0)], [NOTE])
        self.assertEqual((s["shared_draw_samples"], s["shared_draw_points"]), (6, 2))
        self.assertEqual(s["shared_draw_notes"], [NOTE])

    def test_missing_or_invalid_point_is_partial(self):
        bad = {"sigma": None, "problem": "no Monte-Carlo population for this grid point"}
        s = nf._summarise([_pt(1.0, 0.1), _pt(1.2, 0.3), bad], [])
        self.assertFalse(s["complete"])
        self.assertTrue(s["partial"])
        self.assertIn("2 of 3", s["partial_label"])
        self.assertAlmostEqual(s["grid_mean_se_fully_correlated_bound"], 0.2)  # over included


def _result(cfgs):
    return {"od_x_mv": 1.0, "expected_n": 80, "points": [], "configs": cfgs,
            "target_max_mv": 1.0, "stretch_max_mv": 0.6,
            "as_measured": {"incomplete": True, "why": "x"}}


class RenderTest(unittest.TestCase):
    def test_render_carries_both_errors_notes_and_partial(self):
        full = nf._summarise([_pt(1.0, 0.1, 3), _pt(1.2, 0.2, 3)], [NOTE])
        part = nf._summarise([_pt(1.0, 0.1), {"sigma": None, "problem": "p"}], [])
        indep = nf._summarise([_pt(1.0, 0.1), _pt(1.2, 0.2)], [])
        md = nf.render_markdown(_result({"both": full, "fe": part, "zero": indep}))
        self.assertIn("conditional", md.lower())
        self.assertIn("corr. bound", md)
        self.assertIn(NOTE, md)
        self.assertIn("PARTIAL", md)
        self.assertIn("NOT proof of independence", md)
        self.assertIn("0.150", md)  # fully-correlated bound of `both`


if __name__ == "__main__":
    unittest.main()

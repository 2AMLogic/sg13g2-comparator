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


if __name__ == "__main__":
    unittest.main()


def _pt(name, sigma, se, shared=0):
    return {"point": name, "sigma": sigma, "sigma_se": se, "problem": None,
            "samples_sharing_a_draw_with_another_point": shared}


class GridUncertaintyTest(unittest.TestCase):
    def test_conservative_bound_formula_unequal_errors(self):
        ind, corr = nf.grid_mean_se_bounds([0.1, 0.2, 0.3])
        self.assertAlmostEqual(ind, math.sqrt(0.14) / 3)
        self.assertAlmostEqual(corr, 0.2)
        self.assertGreaterEqual(corr, ind)

    def test_independent_fixture_has_no_shared_draws(self):
        c = nf._summarise([_pt("a", 1.0, 0.1), _pt("b", 1.2, 0.3)], [])
        self.assertEqual((c["shared_draw_samples"], c["shared_draw_points"]), (0, 0))
        self.assertEqual(c["grader_notes"], [])
        self.assertAlmostEqual(c["grid_mean_se"], math.hypot(0.1, 0.3) / 2)
        self.assertAlmostEqual(c["grid_mean_se_fully_correlated_bound"], 0.2)
        self.assertTrue(c["complete"])
        self.assertNotIn("partial", c)

    def test_shared_draw_notes_and_counts_survive(self):
        note = "5/160 samples repeat a raw noise draw also seen at ANOTHER grid point"
        c = nf._summarise([_pt("a", 1.0, 0.1, 3), _pt("b", 1.2, 0.3, 2), _pt("c", 1.1, 0.2)],
                          [note])
        self.assertEqual((c["shared_draw_samples"], c["shared_draw_points"]), (5, 2))
        self.assertEqual(c["grader_notes"], [note])

    def test_incomplete_grid_labelled_partial(self):
        bad = {"point": "c", "sigma": None, "problem": "saturated"}
        c = nf._summarise([_pt("a", 1.0, 0.1), _pt("b", 1.2, 0.3), bad], [])
        self.assertFalse(c["complete"])
        self.assertTrue(c["partial"])
        self.assertIn("PARTIAL", c["partial_label"])
        self.assertAlmostEqual(c["grid_mean_se_fully_correlated_bound"], 0.2)  # 2 included points

    def test_render_carries_disclosures(self):
        note = "2/80 samples repeat a raw noise draw also seen at ANOTHER grid point"
        bad = {"point": "c", "sigma": None, "problem": "saturated"}
        cfg = nf._summarise([_pt("a", 1.0, 0.1, 2), bad], [note])
        pts = [{"point": "a", "both": {"sigma": 1.0, "sigma_se": 0.1}},
               {"point": "c", "both": {"sigma": None, "problem": "saturated"}}]
        result = {"od_x_mv": 1.0, "expected_n": 80, "target_max_mv": 1.0, "stretch_max_mv": 0.6,
                  "configs": {"both": cfg}, "points": pts, "uncertainty_basis": nf.UNCERTAINTY_BASIS,
                  "as_measured": {"incomplete": True, "why": "x"}}
        md = nf.render_markdown(result)
        for text in ("independent points assumed", "fully correlated", "PARTIAL, ungraded",
                     "grader note: " + note, "2 (1 points)", "none certifies"):
            self.assertIn(text, md)

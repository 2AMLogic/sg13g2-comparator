"""Known-charge Q_kick fixture tests (issue #78). Stdlib only, no PDK, no
ngspice, writes nothing.

The fixture deck injects analytic charges through the same ammeter+integrator
block as the kickback bench. These tests pin (1) that the real bench's Q_kick
measure strings are the shared template's (so what the fixture validates is
what is graded), (2) that the deck's PWL currents integrate to the analytic
expectations under the instrument's measurement semantics, (3) that the
bipolar case separates a peak instrument from an end-of-window one, (4) that
a window/reference error would be caught, and (5) that the committed fixture
envelope agrees with the analytic values.
"""

from __future__ import annotations

import json
import re
import unittest

from kltsim import build, cli, fixture
from kltsim.benches import (
    BENCHES, FIXTURE_BENCHES, FIXTURE_CASES, FIXTURE_TOL_FC, KICKBACK, KICKBACK_FIXTURE,
    qkick_measurements,
)

CAMPAIGNS = build.EXPERIMENT_DIR / "campaigns"


def _cards():
    return fixture.parse_pwl_sources(fixture.fixture_circuit_text())


class SharedStringsTest(unittest.TestCase):
    def test_real_bench_strings_match_the_template(self):
        for node, side in (("qp", "p"), ("qn", "n")):
            for m in qkick_measurements(node, side):
                self.assertEqual(KICKBACK.measurement(m.name).spice, m.spice)

    def test_real_bench_strings_are_the_ones_already_submitted(self):
        # the campaign request that produced the 45-point result
        req = json.loads((CAMPAIGNS / "20261009-d73a9ac" / "kickback.request.json").read_text("utf-8"))
        submitted = {m["name"]: m["spice"] for m in req["measurements"]}
        for node, side in (("qp", "p"), ("qn", "n")):
            for m in qkick_measurements(node, side):
                self.assertEqual(submitted[m.name], m.spice)

    def test_fixture_cases_use_the_same_template(self):
        for case, spec in FIXTURE_CASES.items():
            for m in qkick_measurements(spec["node"], case):
                self.assertEqual(KICKBACK_FIXTURE.measurement(m.name).spice, m.spice)

    def test_window_constants_are_the_ratified_definition(self):
        spice = " ".join(m.spice for m in qkick_measurements("qp", "p"))
        self.assertIn("at=29n", spice)
        self.assertEqual(spice.count("from=30n to=45n"), 2)
        self.assertEqual((fixture.REF_NS, fixture.WIN_LO_NS, fixture.WIN_HI_NS), (29.0, 30.0, 45.0))

    def test_instrument_block_matches_the_real_deck(self):
        squash = lambda t: re.sub(r"[ \t]+", " ", t)
        real = squash((build.BENCH_DIR / "kickback.circuit.spice").read_text("utf-8"))
        fx = squash(fixture.fixture_circuit_text())
        for side, ammeter in (("p", "vkp"), ("n", "vkn")):
            for line in (f"Bq{side} 0 q{side} i = 'i({ammeter})'", f"Cq{side} q{side} 0 1p",
                         f"Rq{side} q{side} 0 1e9"):
                self.assertIn("\n" + line + "\n", real)
        for case in FIXTURE_CASES:
            for line in (f"Bq{case} 0 q{case} i = 'i(vk{case})'", f"Cq{case} q{case} 0 1p",
                         f"Rq{case} q{case} 0 1e9"):
                self.assertIn("\n" + line + "\n", fx)

    def test_fixture_is_not_in_the_graded_bench_set(self):
        self.assertNotIn("kickback_fixture", BENCHES)
        self.assertIn("kickback_fixture", FIXTURE_BENCHES)


class AnalyticTest(unittest.TestCase):
    def test_deck_pwl_integrates_to_the_expected_values(self):
        cards = _cards()
        self.assertEqual(set(cards), set(FIXTURE_CASES))
        for case, spec in FIXTURE_CASES.items():
            got = fixture.reference_response(cards[case])
            self.assertAlmostEqual(got["peak_fc"], spec["q_fc"], delta=FIXTURE_TOL_FC, msg=case)
            # instrument convention: charge INTO the pin node lowers v(q)
            self.assertAlmostEqual(-got["net_fc"], spec["net_fc"], delta=FIXTURE_TOL_FC, msg=case)

    def test_bipolar_has_zero_net_and_nonzero_peak(self):
        got = fixture.reference_response(_cards()["c"])
        self.assertAlmostEqual(got["net_fc"], 0.0, delta=FIXTURE_TOL_FC)
        self.assertGreater(got["peak_fc"], 19.0)
        self.assertGreater(abs(got["pos_fc"]) + abs(got["neg_fc"]), 19.0)

    def test_end_window_estimator_fails_the_bipolar_case(self):
        got = fixture.reference_response(_cards()["c"])
        naive = fixture.end_window_estimator_fc(got["net_fc"])
        self.assertGreater(abs(naive - FIXTURE_CASES["c"]["q_fc"]), 10 * FIXTURE_TOL_FC)

    def test_pre_and_post_window_pulses_are_excluded(self):
        # case a carries +7 fC before 29 ns and +4 fC after 45 ns
        a = _cards()["a"]
        self.assertAlmostEqual(fixture.reference_response(a)["peak_fc"], 10.0, delta=FIXTURE_TOL_FC)
        # a reference at 20 ns would wrongly include the early pulse: 17 fC
        self.assertAlmostEqual(fixture.reference_response(a, ref_ns=19.0)["peak_fc"], 17.0, delta=0.05)
        # a window running to 60 ns would wrongly include the late pulse: 14 fC
        self.assertAlmostEqual(fixture.reference_response(a, win_hi_ns=60.0)["peak_fc"], 14.0, delta=0.05)

    def test_restoration_case_defeats_volts_times_c(self):
        # tau = 1 kohm * 100 fF = 100 ps; 1 uA settles the node to ~1 mV,
        # so V x C_in ~ 0.1 fC against a delivered 10 fC
        self.assertLess(1e-6 * 1e3 * 100e-15 * 1e15, 0.2)
        self.assertEqual(FIXTURE_CASES["d"]["q_fc"], 10.0)


class EnvelopeTest(unittest.TestCase):
    def test_committed_fixture_envelope_agrees(self):
        found = sorted(CAMPAIGNS.glob("*/fixture/kickback_fixture.envelope.json"))
        if not found:
            self.skipTest("no committed fixture envelope")
        for path in found:
            report = fixture.check_envelope(KICKBACK_FIXTURE, json.loads(path.read_text("utf-8")))
            self.assertTrue(report["ok"], path)
            self.assertTrue(report["end_window_estimator_fails_bipolar"], path)

    def test_a_wrong_reading_fails_the_check(self):
        found = sorted(CAMPAIGNS.glob("*/fixture/kickback_fixture.envelope.json"))
        if not found:
            self.skipTest("no committed fixture envelope")
        env = json.loads(found[0].read_text("utf-8"))
        for m in env["corners"][0]["measurements"]:
            if m["name"] == "qkick_c_fc":
                m["value"] = 0.0  # what an end-of-window instrument would read
        self.assertFalse(fixture.check_envelope(KICKBACK_FIXTURE, env)["ok"])

    def test_missing_measurement_is_a_failure_not_a_pass(self):
        env = {"corners": [{"measurements": []}]}
        self.assertFalse(fixture.check_envelope(KICKBACK_FIXTURE, env)["ok"])


class AbHelperTest(unittest.TestCase):
    def test_strip_instrument_rewires_the_dut_pins(self):
        body = build.compose_body(BENCHES["kickback"], build.BATCH_OSDI_DIR)
        stripped = cli.strip_instrument(body)
        for token in ("vkp ", "vkn ", "Bqp ", "Cqn ", "Rqn "):
            self.assertNotIn("\n" + token, stripped)
        xa = next(l for l in stripped.split("\n") if l.startswith("Xa "))
        self.assertNotIn("_pin", xa)
        self.assertEqual(xa.split()[1:3], ["apa", "ana"])


if __name__ == "__main__":
    unittest.main()

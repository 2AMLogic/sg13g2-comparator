"""Campaign replay / record tests for sim/run_memory.py (issue #159). Stdlib
only: synthetic klt sim envelopes in a temporary campaign directory, no
ngspice, no network, nothing written under sim/."""

from __future__ import annotations

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
            mult = list(range(0, 11)) if k == 1 else list(range(1, 10))
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


if __name__ == "__main__":
    unittest.main()

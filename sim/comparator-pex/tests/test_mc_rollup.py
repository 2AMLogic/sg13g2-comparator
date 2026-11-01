import json
import subprocess
import sys
import unittest
from pathlib import Path

PEX = Path(__file__).resolve().parents[1]
# Latest roll-up. Older stems are append-only history; they were fresh when written and are not re-checked.
STEM = PEX / "reports" / "mc-rollup.20261101-b"


class McRollup(unittest.TestCase):
    def test_committed_rollup_is_fresh(self):
        r = subprocess.run([sys.executable, str(PEX / "make_mc_rollup.py"), "--check", str(STEM)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_verdict_and_bounds_unchanged(self):
        d = json.loads(STEM.with_name(STEM.name + ".json").read_text())
        self.assertEqual(d["bounds_quoted"]["offset_3sigma_target_mv"], 15.0)
        self.assertEqual(d["bounds_quoted"]["noise_target_mv_rms"], 1.0)
        for e in d["offset"]["points"] + d["noise"]["points"]:
            self.assertLessEqual(e["n_compared"], e["n_requested"])

    def test_refuses_overwrite(self):
        r = subprocess.run([sys.executable, str(PEX / "make_mc_rollup.py"), str(STEM)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()

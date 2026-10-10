"""Negative controls for scripts/check_readme_claims.py (issue #174).

Stdlib only. The positive case runs the real README against the real
committed report; negative cases mutate a copy of one or the other.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_readme_claims.py"
spec = importlib.util.spec_from_file_location("check_readme_claims", SCRIPT)
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

README = chk.DEFAULT_README.read_text(encoding="utf-8")
REPORT = chk.load_report(chk.DEFAULT_REPORT)


def _run(readme_text, report):
    with tempfile.TemporaryDirectory() as td:
        rp, jp = Path(td, "README.md"), Path(td, "report.json")
        rp.write_text(readme_text, encoding="utf-8")
        jp.write_text(json.dumps(report), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = chk.main(["--readme", str(rp), "--report", str(jp)])
    return code, out.getvalue(), err.getvalue()


class ReadmeClaims(unittest.TestCase):
    def test_committed_readme_matches_committed_report(self):
        code, out, err = _run(README, REPORT)
        self.assertEqual(code, 0, err)
        self.assertIn(f"checked {len(chk.CLAIMS)}/{len(chk.CLAIMS)}", out)

    def test_unmapped_claims_are_reported_not_passed(self):
        _, out, _ = _run(README, REPORT)
        self.assertIn("UNCHECKED count in row 'Offset sigma'", out)

    def test_mutated_readme_count_fails_with_both_values(self):
        mutated = README.replace("39/45 points over 25 fC", "38/45 points over 25 fC")
        self.assertNotEqual(mutated, README)
        code, _, err = _run(mutated, REPORT)
        self.assertEqual(code, 1)
        self.assertIn("README says 38", err)
        self.assertIn("report (4a/target/points_failing) says 39", err)

    def test_mutated_readme_value_fails(self):
        mutated = README.replace("binding point `ff_125c_1.32v` (31.46 fC;",
                                 "binding point `ff_125c_1.32v` (30.46 fC;")
        self.assertNotEqual(mutated, README)
        code, _, err = _run(mutated, REPORT)
        self.assertEqual(code, 1)
        self.assertIn("README says 30.46, report", err)
        self.assertIn("says 31.46", err)

    def test_mutated_report_fails(self):
        report = json.loads(json.dumps(REPORT))
        row = next(r for r in report["rows"] if r["id"] == "3b")
        row["target"]["range"]["max"]["value"] = 170.0
        code, _, err = _run(README, report)
        self.assertEqual(code, 1)
        self.assertIn("tau max ps", err)

    def test_pattern_that_stops_matching_fails_loudly(self):
        code, _, err = _run(README.replace("fC/side**", "fC per side**"), REPORT)
        self.assertEqual(code, 1)
        self.assertIn("no longer matches", err)

    def test_rounding_is_half_up_at_readme_precision(self):
        self.assertEqual(chk._round_to(167.256, "167.3"), "167.3")
        self.assertEqual(chk._round_to(0.8125, "0.813"), "0.813")
        self.assertEqual(chk._round_to(7.0, "7"), "7")

    def test_missing_report_row_fails(self):
        report = json.loads(json.dumps(REPORT))
        report["rows"] = [r for r in report["rows"] if r["id"] != "4a"]
        code, _, err = _run(README, report)
        self.assertEqual(code, 1)
        self.assertIn("no row id '4a'", err)


if __name__ == "__main__":
    unittest.main()

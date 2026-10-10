"""Regression tests for scripts/check_klt_pin.py (issue #135).

Each test builds a minimal temp-dir repo fixture holding every machine-read
pin copy; stdlib only.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_klt_pin.py"
spec = importlib.util.spec_from_file_location("check_klt_pin", SCRIPT)
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

SHA = "e8ca621a6961879cec1af60cc932c3b3d58ddcaa"
VER = "0.5.0+ge8ca621a6961"
KLAYOUT = "0.30.10"
OTHER_SHA = "86740f86d44f0000000000000000000000000000"

CI = f"""\
jobs:
  signoff-manifest-parity:
    steps:
      - name: Install klt
        run: |
          python3 -m pip install \\
            "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@{SHA}"
  layout-reproducibility:
    steps:
      - name: Install klt + KLayout
        run: |
          python3 -m pip install \\
            "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@{SHA}" \\
            "klayout=={KLAYOUT}"
"""

RUN_FLOW = f"""\
#!/usr/bin/env bash
set -euo pipefail
KLT_PIN="{SHA}"
KLAYOUT_PIN="{KLAYOUT}"  # tested against
echo "${{KLT_PIN}}"
"""


class Fixture:
    def __init__(self, root):
        self.root = Path(root)
        self.write_json(chk.PIN_FILE, {
            "klt_commit": SHA, "klt_version": VER, "klayout_version": KLAYOUT})
        self.write(chk.CI_YML, CI)
        self.write(chk.RUN_FLOW, RUN_FLOW)
        self.write_json(chk.SIGNOFF, {
            "build": {"version": VER, "git_commit": SHA}, "items": []})
        for rel in chk.LAYOUT_REPORTS:
            self.write_json(rel, {"provenance": {
                "klt_version": VER, "klayout_version": KLAYOUT}})
        # Deliberately different build: must be ignored by the guard.
        self.write_json("layout/comparator/pex_report.json", {"provenance": {
            "klt_version": "0.7.0+g86740f86d44f", "klayout_version": "0.30.12"}})

    def path(self, rel):
        return self.root / rel

    def write(self, rel, text):
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def write_json(self, rel, data):
        self.write(rel, json.dumps(data, indent=2) + "\n")

    def read(self, rel):
        return self.path(rel).read_text(encoding="utf-8")

    def read_json(self, rel):
        return json.loads(self.read(rel))

    def edit(self, rel, old, new, count=1):
        text = self.read(rel)
        assert old in text, (rel, old)
        self.write(rel, text.replace(old, new, count))

    def run(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = chk.main(["--root", str(self.root)])
        return rc, out.getvalue(), err.getvalue()


class KltPinTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def assertFails(self, *needles):
        rc, _out, err = self.fx.run()
        self.assertEqual(rc, 1, err)
        for n in needles:
            self.assertIn(n, err)
        return err

    # -- agree --------------------------------------------------------------

    def test_agree(self):
        rc, out, err = self.fx.run()
        self.assertEqual(rc, 0, err)
        self.assertIn("klt pin OK", out)
        # 2 ci klt + 1 ci klayout + 2 run_flow + 2 signoff + 3x2 reports
        self.assertIn("13 copies agree", out)

    def test_pex_report_is_ignored(self):
        self.fx.path("layout/comparator/pex_report.json").unlink()
        rc, _out, err = self.fx.run()
        self.assertEqual(rc, 0, err)

    # -- disagree: one copy per location class ------------------------------

    def test_disagree_ci_klt_second_line(self):
        text = self.fx.read(chk.CI_YML)
        i = text.rindex(SHA)
        self.fx.write(chk.CI_YML, text[:i] + OTHER_SHA + text[i + len(SHA):])
        err = self.assertFails(chk.PIN_FILE + ":klt_commit", SHA, OTHER_SHA,
                               chk.CI_YML + ":13")
        self.assertNotIn(chk.CI_YML + ":7 ", err)

    def test_disagree_ci_klayout(self):
        self.fx.edit(chk.CI_YML, f"klayout=={KLAYOUT}", "klayout==0.30.12")
        self.assertFails(chk.PIN_FILE + ":klayout_version", "0.30.12",
                         chk.CI_YML + ":14")

    def test_disagree_run_flow_klt(self):
        self.fx.edit(chk.RUN_FLOW, f'KLT_PIN="{SHA}"', f'KLT_PIN="{OTHER_SHA}"')
        self.assertFails(chk.RUN_FLOW + ":3 (KLT_PIN)", OTHER_SHA, SHA)

    def test_disagree_run_flow_klayout(self):
        self.fx.edit(chk.RUN_FLOW, f'KLAYOUT_PIN="{KLAYOUT}"', 'KLAYOUT_PIN="0.30.12"')
        self.assertFails(chk.RUN_FLOW + ":4 (KLAYOUT_PIN)", "0.30.12")

    def test_disagree_signoff_build(self):
        d = self.fx.read_json(chk.SIGNOFF)
        d["build"]["git_commit"] = OTHER_SHA
        d["build"]["version"] = "0.7.0+g86740f86d44f"
        self.fx.write_json(chk.SIGNOFF, d)
        self.assertFails(chk.SIGNOFF + ":build.git_commit",
                         chk.SIGNOFF + ":build.version", "0.7.0+g86740f86d44f")

    def test_disagree_each_layout_report(self):
        for rel in chk.LAYOUT_REPORTS:
            with self.subTest(rel=rel):
                good = self.fx.read(rel)
                d = json.loads(good)
                d["provenance"]["klt_version"] = "0.7.0+g86740f86d44f"
                d["provenance"]["klayout_version"] = "0.30.12"
                self.fx.write_json(rel, d)
                self.assertFails(rel + ":provenance.klt_version",
                                 rel + ":provenance.klayout_version")
                self.fx.write(rel, good)

    def test_disagree_pin_file_moved_alone(self):
        self.fx.write_json(chk.PIN_FILE, {
            "klt_commit": OTHER_SHA, "klt_version": "0.7.0+g86740f86d44f",
            "klayout_version": KLAYOUT})
        err = self.assertFails(OTHER_SHA, SHA)
        # every klt copy is named
        for loc in (chk.CI_YML, chk.RUN_FLOW, chk.SIGNOFF, *chk.LAYOUT_REPORTS):
            self.assertIn(loc, err)

    def test_pin_file_version_not_matching_commit(self):
        d = self.fx.read_json(chk.PIN_FILE)
        d["klt_version"] = "0.5.0+g000000000000"
        self.fx.write_json(chk.PIN_FILE, d)
        self.assertFails("does not end in '+ge8ca621a6961'")

    # -- missing copy -------------------------------------------------------

    def test_missing_ci_klt_line(self):
        text = self.fx.read(chk.CI_YML)
        i = text.index(f'"klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@{SHA}"')
        j = text.index("\n", i)
        self.fx.write(chk.CI_YML, text[:i] + '"klayout-tools"' + text[j:])
        self.assertFails("missing copy", chk.CI_YML, "expected at least 2")

    def test_missing_ci_klayout_line(self):
        self.fx.edit(chk.CI_YML, f'"klayout=={KLAYOUT}"', '"klayout"')
        self.assertFails("missing copy", "klayout==<version>")

    def test_missing_run_flow_var(self):
        self.fx.edit(chk.RUN_FLOW, f'KLAYOUT_PIN="{KLAYOUT}"', "")
        self.assertFails("missing copy", chk.RUN_FLOW, "KLAYOUT_PIN")

    def test_missing_signoff_key(self):
        d = self.fx.read_json(chk.SIGNOFF)
        del d["build"]["git_commit"]
        self.fx.write_json(chk.SIGNOFF, d)
        self.assertFails("missing copy", chk.SIGNOFF, "build.git_commit")

    def test_missing_report_file(self):
        self.fx.path(chk.LAYOUT_REPORTS[1]).unlink()
        self.assertFails("missing copy", chk.LAYOUT_REPORTS[1], "does not exist")

    def test_missing_report_key(self):
        rel = chk.LAYOUT_REPORTS[2]
        self.fx.write_json(rel, {"provenance": {"klt_version": VER}})
        self.assertFails("missing copy", rel, "provenance.klayout_version")

    def test_missing_pin_file(self):
        self.fx.path(chk.PIN_FILE).unlink()
        self.assertFails("missing copy", chk.PIN_FILE)

    def test_missing_pin_key(self):
        self.fx.write_json(chk.PIN_FILE, {"klt_commit": SHA, "klt_version": VER})
        self.assertFails(chk.PIN_FILE, "klayout_version")


if __name__ == "__main__":
    unittest.main()

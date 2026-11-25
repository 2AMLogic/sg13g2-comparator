"""Item 5 spec_rows verdict regression (issue #478).

The manifest declares the DR-0002 row set under ``spec_rows["5"]`` and cites
one envelope per row group. This module exercises the verdicts of the REAL
pinned grader (``klt signoff``, the build pinned by manifests/klt-pin.json)
against the committed manifest and against scratch manifests built in a
temporary directory:

* baseline: the committed citations render item 5 ``unmet`` / ``check_failed``
  with the kickback envelope as the sole failed citation, Rows 4a/4b in
  ``failed_rows``, and Rows 1/2/5a in ``declared_gaps`` -- so Row 2 is never
  reported as covered and passing, including while kickback fails;
* a passing kickback citation (the committed issue #92 sizing-study envelope,
  a real 45/45-pass run of the same bench, standing in for a fixed Row 4a)
  with the same declared gaps keeps item 5 ``unmet`` / ``partial_coverage``
  with every citation met -- the Row 2 gap alone holds the item unmet;
* a reduced fixture with Row 2 as the SOLE declared gap (all other rows
  covered, no other gap to mask a false pass) still renders ``unmet`` /
  ``partial_coverage`` with Row 2 uncovered and without a coverage source;
* the declared row ids reconcile with the Target-bearing entries of
  sim/klt-corner-verification/rows.json (Row 5a's coverage Target included).

Stdlib only. The grader is located as ``KLT_BIN`` or ``klt`` on $PATH and
must match manifests/klt-pin.json (read from HEAD so a sparse cone without
manifests/ still works); otherwise the tests skip -- CI runs them for real
in the ``signoff-manifest-parity`` job, whose sparse cone carries every
input below. No simulation is ever run.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "sg13g2-comparator.json"
ROWS = ROOT / "sim" / "klt-corner-verification" / "rows.json"
D73 = "sim/klt-corner-verification/campaigns/20261009-d73a9ac"
PASSING_KICKBACK = ("sim/klt-corner-verification/campaigns/"
                    "20261009-issue92/full_w8_l034/kickback.envelope.json")
ACCEPTED_EXITS = (0, 3)


def _pinned_klt():
    """Path to a klt matching manifests/klt-pin.json, else None."""
    exe = os.environ.get("KLT_BIN") or shutil.which("klt")
    if not exe:
        return None
    try:
        pin = json.loads(subprocess.run(
            ["git", "show", "HEAD:manifests/klt-pin.json"], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout)
        version = subprocess.run([exe, "--version"], cwd=ROOT,
                                 capture_output=True, text=True,
                                 check=True).stdout
    except (subprocess.CalledProcessError, OSError, ValueError):
        return None
    match = re.fullmatch(r"klt\s+(\S+)", version.strip())
    return exe if match and match.group(1) == pin["klt_version"] else None


class PinnedKltVersionGate(unittest.TestCase):
    """_pinned_klt() gates on an exact klt --version match (issue #487).

    A dev build of the pinned release must skip (its grading rules differ
    from the release the report was frozen with), and only the full pinned
    version string -- release or dev form -- may run the item 5 tests.
    """

    @staticmethod
    def _committed_pin():
        proc = subprocess.run(
            ["git", "show", "HEAD:manifests/klt-pin.json"], cwd=ROOT,
            capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)["klt_version"]

    FAKE_KLT = "/nonexistent/klt-stub"

    def _pinned_with(self, version_output):
        """Run _pinned_klt() with ``klt --version`` answered by a stub.

        The version subprocess is stubbed in-process (no shell script on
        disk), so the comparison runs even where the temporary directory is
        mounted noexec. Other subprocess calls (git show) pass through.
        """
        real_run = subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if list(cmd) == [self.FAKE_KLT, "--version"]:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=version_output, stderr="")
            return real_run(cmd, *args, **kwargs)

        with mock.patch.dict(os.environ, {"KLT_BIN": self.FAKE_KLT}), \
                mock.patch.object(subprocess, "run", side_effect=fake_run):
            return _pinned_klt()

    def test_exact_pin_match_returns_exe(self):
        pin = self._committed_pin()
        self.assertEqual(self._pinned_with("klt " + pin), self.FAKE_KLT)

    def test_dev_build_of_pinned_release_skips(self):
        pin = self._committed_pin()
        outcome = self._pinned_with(
            "klt " + pin + ".dev1029+g76f47afa48f1")
        self.assertIsNone(outcome)

    def test_extra_tokens_after_version_skip(self):
        pin = self._committed_pin()
        self.assertIsNone(self._pinned_with("klt " + pin + " extra tokens"))

    def test_trailing_whitespace_still_matches(self):
        pin = self._committed_pin()
        self.assertEqual(
            self._pinned_with("klt " + pin + "\n\n   "), self.FAKE_KLT)


def _input_hash(rel):
    """provenance.input.content_hash of a committed envelope (repo-relative)."""
    envelope = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    return envelope["provenance"]["input"]["content_hash"]


def _render(klt, manifest_path):
    return subprocess.run(
        [klt, "signoff", "--manifest", str(manifest_path), "--format", "json"],
        cwd=ROOT, capture_output=True, text=True)


def _item5(report):
    items = [i for i in report["items"] if i.get("id") == 5]
    assert items, "report has no item 5"
    return items[0]


def _gap_ids(item):
    return {g["id"] for g in item["detail"]["declared_gaps"]}


@unittest.skipUnless(_pinned_klt(), "pinned klt (manifests/klt-pin.json) not available")
class Item5Verdicts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klt = _pinned_klt()
        needed = [MANIFEST,
                  ROOT / D73 / "regeneration.envelope.json",
                  ROOT / D73 / "kickback.envelope.json",
                  ROOT / PASSING_KICKBACK]
        missing = [str(p) for p in needed if not p.is_file()]
        if missing:
            raise unittest.SkipTest(
                "item 5 inputs outside this checkout's cone: " + ", ".join(missing))
        cls.baseline = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def _fixture(self, evidence5, spec_rows):
        manifest = json.loads(json.dumps(self.baseline))
        manifest["evidence"]["5"] = evidence5
        manifest["spec_rows"] = {"5": spec_rows}
        return manifest

    def _render_fixture(self, manifest):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            proc = _render(self.klt, path)
        return proc

    @staticmethod
    def _citations(regeneration_rows, kickback, kickback_rows):
        return [
            {"file": f"{D73}/regeneration.envelope.json",
             "content_hash": _input_hash(f"{D73}/regeneration.envelope.json"),
             "rows": regeneration_rows},
            {"file": kickback,
             "content_hash": _input_hash(kickback),
             "rows": kickback_rows},
        ]

    _DECLARED = [
        {"id": "1", "gap": "row 1 statistic not gradeable from an envelope status"},
        {"id": "2", "gap": "row 2 statistic not gradeable from an envelope status"},
        {"id": "3a"}, {"id": "3b"}, {"id": "3c"},
        {"id": "4a"}, {"id": "4b"},
        {"id": "5a", "gap": "joint grid coverage not gradeable from one envelope"},
    ]

    def test_baseline_committed_manifest(self):
        proc = _render(self.klt, MANIFEST)
        self.assertIn(proc.returncode, ACCEPTED_EXITS, proc.stderr)
        item = _item5(json.loads(proc.stdout))
        self.assertEqual(item["status"], "unmet")
        self.assertEqual(item["reason"], "check_failed")
        detail = item["detail"]
        self.assertEqual(detail["failed_citations"],
                         [f"{D73}/kickback.envelope.json"])
        self.assertIn("4a", detail["failed_rows"])
        self.assertEqual(_gap_ids(item), {"1", "2", "5a"})
        self.assertEqual(detail["uncovered_rows"], [])
        self.assertNotIn("2", detail.get("row_sources", {}))

    def test_passing_kickback_keeps_row2_gap_unmet(self):
        manifest = self._fixture(
            self._citations(["3a", "3b", "3c"], PASSING_KICKBACK, ["4a", "4b"]),
            self._DECLARED)
        proc = self._render_fixture(manifest)
        self.assertIn(proc.returncode, ACCEPTED_EXITS, proc.stderr)
        item = _item5(json.loads(proc.stdout))
        self.assertEqual(item["status"], "unmet")
        self.assertEqual(item["reason"], "partial_coverage")
        detail = item["detail"]
        self.assertEqual(detail["uncovered_rows"], [])
        self.assertEqual(_gap_ids(item), {"1", "2", "5a"})
        self.assertNotIn("2", detail.get("row_sources", {}))
        for graded in item["citations_graded"]:
            self.assertEqual(graded["status"], "met", graded["citation"])

    def test_row2_sole_gap_still_unmet(self):
        manifest = self._fixture(
            self._citations(["3a", "3b", "3c"], PASSING_KICKBACK, ["4a", "4b"]),
            [{"id": "2", "gap": "row 2 statistic not gradeable from an "
                                "envelope status"},
             {"id": "3a"}, {"id": "3b"}, {"id": "3c"},
             {"id": "4a"}, {"id": "4b"}])
        proc = self._render_fixture(manifest)
        self.assertIn(proc.returncode, ACCEPTED_EXITS, proc.stderr)
        item = _item5(json.loads(proc.stdout))
        self.assertEqual(item["status"], "unmet")
        self.assertEqual(item["reason"], "partial_coverage")
        detail = item["detail"]
        self.assertEqual(_gap_ids(item), {"2"})
        self.assertEqual(detail["uncovered_rows"], [])
        self.assertNotIn("2", detail.get("row_sources", {}))
        for graded in item["citations_graded"]:
            self.assertEqual(graded["status"], "met", graded["citation"])


@unittest.skipUnless(ROWS.is_file() and MANIFEST.is_file(),
                     "rows.json / manifest outside this checkout's cone")
class DeclaredRowsReconcile(unittest.TestCase):
    def test_spec_rows_match_target_bearing_rows(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        declared = {row["id"] for row in manifest["spec_rows"]["5"]}
        gap_ids = {row["id"] for row in manifest["spec_rows"]["5"]
                   if "gap" in row}
        rows = json.loads(ROWS.read_text(encoding="utf-8"))["rows"]
        targeted = {row["id"] for row in rows
                    if row.get("target") is not None}
        self.assertEqual(declared, targeted,
                         "spec_rows[\"5\"] must declare exactly the "
                         "Target-bearing rows of rows.json")
        for citation in manifest["evidence"]["5"]:
            for row in citation["rows"]:
                self.assertIn(row, declared)
                self.assertNotIn(row, gap_ids)


if __name__ == "__main__":
    unittest.main()

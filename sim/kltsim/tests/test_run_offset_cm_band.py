"""Orchestration tests for sim/run_offset_cm_band.py (issue #186). Stdlib only;
kcli._submit, kcli._last_attempt_refused_at_cap and time.sleep are patched."""

from __future__ import annotations

import argparse
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
             retry_refused=0, retry_wait=7, process="mos_tt")
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
        self.sleeps = []
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
        return self.codes.pop(0) if self.codes else 0

    def _refused(self, out_dir):
        return self.refused.pop(0) if self.refused else False

    @property
    def cond_dir(self):
        return self.series / COND


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
    def make_requests(self, tags=TAGS):
        self.cond_dir.mkdir(parents=True)
        for t in tags:
            (self.cond_dir / f"{t}.request.json").write_text("{}")

    def test_submits_every_part(self):
        self.make_requests()
        self.assertEqual(rcb.cmd_run(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], TAGS)
        self.assertTrue(all(c[1] == "campaign" for c in self.calls))

    def test_missing_request_errors_without_submitting(self):
        self.make_requests(TAGS[:0])
        self.assertEqual(rcb.cmd_run(self.args), 1)
        self.assertEqual(self.calls, [])

    def test_skip_existing_skips_only_enveloped_parts(self):
        self.make_requests()
        (self.cond_dir / f"{TAGS[0]}.envelope.json").write_text("{}")
        self.args.skip_existing = True
        self.assertEqual(rcb.cmd_run(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], TAGS[1:])

    def test_without_skip_existing_resubmits_enveloped_part(self):
        # Pins current behaviour (see issue #186): not a statement it is right.
        self.make_requests()
        (self.cond_dir / f"{TAGS[0]}.envelope.json").write_text("{}")
        rcb.cmd_run(self.args)
        self.assertEqual([c[0] for c in self.calls], TAGS)

    def test_part_filter(self):
        self.make_requests()
        self.args.part = [TAGS[1]]
        rcb.cmd_run(self.args)
        self.assertEqual([c[0] for c in self.calls], [TAGS[1]])

    def test_exit_code_is_max_of_parts(self):
        self.make_requests()
        self.codes = [0, 4, 3] + [0] * len(TAGS)
        self.assertEqual(rcb.cmd_run(self.args), 4)


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

# 0017: Evidence-size exception for the decision-time common-mode band campaign (issue #164)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. The campaign it
  covers is evidence for the DR-0004 CM-range row and is graded against the
  unchanged DR-0002 Row 3 limits. It authorizes one raise of the `sim/` total
  ceiling in `sim/evidence-size-budget.json` (issue #132's contract), exactly
  the measured overage of 1514937 B. It takes effect with the reviewed merge of
  the PR that lands it, as for DR-0005 to DR-0016. The drafting agent does
  not merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #164 (size record added by the
  Doctor after Judge review). The operator reviews the raise as a governance
  item at merge.
- **Related**:
  [`0016-clock-supply-sensitivity-evidence-size-exception.md`](0016-clock-supply-sensitivity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)

## Context

Issue #164 adds a new experiment, `sim/comparator-decision-cm-band/`, with
three conditions (`dut_vcm` -50 mV, nominal, +50 mV), each a 45-point
`regeneration` envelope run as a `klt sim` batch campaign, plus harness code
(`sim/kltsim/cmdecision.py`, `sim/run_decision_cm_band.py`), unit tests and a
README. Per-corner artifacts are not kept; the envelopes, requests, bodies,
invocations and the comparison table are the evidence itself, so they cannot
be dropped. The campaign unit is 1484273 B, far under the 47 MiB new-unit
ceiling; only the `sim/` total is raised. After DR-0016 `sim/` was exactly at
its ceiling, so any addition needs this exception.

## Decision

Raise the `sim/` total ceiling by exactly **1514937 B**. The single `sim` entry
carries the cumulative 26503473 + 1514937 = **28018410 B** and cites this
record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28018410}
```

(Cumulative: 26503473 B from DR-0005 to DR-0016 and 1514937 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No existing `sim/` evidence file is
  modified, and no spec bound changes.

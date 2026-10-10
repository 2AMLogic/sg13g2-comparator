# 0005: Evidence-size exception for the N = 200 offset campaign (issue #167)

- **Status**: proposed. **This is an evidence-budget record only.** It
  ratifies no bound, relaxes no Target or Stretch number, and changes no
  line of `spec/` or `README.md`'s target table. It authorizes two exact
  raises of the evidence-size ceilings in `sim/evidence-size-budget.json`
  (issue [#132](https://github.com/2AMLogic/sg13g2-comparator/issues/132)'s
  contract) so one campaign can be committed.
- **Date**: 2026-10-10
- **Decided by**: Builder agent, issue
  [#167](https://github.com/2AMLogic/sg13g2-comparator/issues/167); reviewers
  judge the rationale below as well as the numbers.
- **Related**: [#63](https://github.com/2AMLogic/sg13g2-comparator/issues/63)
  (the `klt yield` adapter whose N = 60 populations were undersized),
  [#3](https://github.com/2AMLogic/sg13g2-comparator/issues/3) (T1 tracker),
  [#82](https://github.com/2AMLogic/sg13g2-comparator/issues/82) (unresolved
  offset discrepancy, not settled here),
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  (Row 1, unchanged)
- **Supersedes**: none. **Superseded by**: none

## Context

T1 item 6 cited a `klt yield` report built from N = 60 draws per PVT point
and rendered `unmet` / `undersized_sample`: the pinned engine needs N = 183
for its default interval half-width of 0.01 and the precision target must not
be relaxed. Issue #167 authorizes one explicit, offset-only campaign at
N = 200 per point (45 points, 9,000 whole-latch Monte-Carlo units).

Before submission, `python3 sim/run_klt_corner_verification.py estimate
--offset-n 200` projected 62,010,403 B for the campaign unit against the
49,283,072 B new-unit ceiling and a `sim/` total over the 538,958,901 B
ceiling, so the overage was known and recorded before any fleet spend. The
committed campaign measures 61,709,133 B (the estimate was within 0.5 %).

## Decision

1. The campaign unit `sim/klt-corner-verification/campaigns/20261010-n200` is
   committed whole: request, invocation and envelope per process corner, the
   per-corner `ngspice.log` / generated deck artifacts, `grading.json`/`.md`
   and the seed/mismatch preflight. It exceeds the new-unit ceiling by exactly
   12426061 B.
2. The `sim/` total exceeds its ceiling by exactly 15571105 B (this campaign
   plus its 0.8 MB `klt yield` unit, the declared-N tooling and docs under `sim/`, and the exception entries themselves).

Reducing the unit instead was considered and rejected: dropping the
per-corner artifacts would make this campaign structurally unlike every
other committed `klt sim` campaign and remove the logs that let a reviewer
audit a single draw; sub-sampling to fit would defeat the purpose (N = 183+
at every point, no pooling). The raises are exactly the measured overages, so
no further growth is silently allowed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim/klt-corner-verification/campaigns/20261010-n200", "additional_bytes": 12426061}
```

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15571105}
```

## Consequences

- Future campaigns of this size need their own record; this one is exact, not
  a standing allowance. `python3 scripts/check_evidence_size.py --tree HEAD`
  passes with these two entries and fails without them.
- No claim changes: the 15 mV Row 1 bound is untouched, the quantization-
  corrected 3-sigma statistic stays separate from the yield interval, and
  issue #82's discrepancy warning is carried in the new report unchanged.

# 0029: Evidence-size exception for I_B sweep probe validation (issue #267)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 10486 B. It takes effect
  only with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0027. The drafting agent does not merge it, and drafting it is not agents
  relaxing the ratified spec.
- **Date**: 2026-10-12
- **Decided by**: Doctor agent for PR #271 (issue #267), following the DR-0027
  pattern. The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0027-yield-index-rederivation-evidence-size-exception.md`](0027-yield-index-rederivation-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none
- **Numbering**: DR-0028 is taken by open PR #265, and DR-0024 remains
  double-booked by open, unmerged PRs (#249, #243). This record chains its
  cumulative `sim` entry on DR-0027, the latest merged raise. Whichever PR
  merges first keeps its number and cumulative figure; the others are
  renumbered on rebase with their cumulative `sim` entry re-measured. This
  record's own 10486 B does not change unless this PR's `sim/` diff changes.

## Context

Issue #267 makes `ibsweep.probe_summary` validate each expected physical
(process, V, T) point before aggregating its mirror and headroom probes
(errored or repeated corners, malformed or non-finite measurements, bad units,
non-positive reference, out-of-grid and missing points), and report coverage
(`points_valid`, `points_expected`, `complete`, `rejected`). On main, `sim/`
was exactly at its ceiling, so any addition needs this exception. The growth is
code and tests, not evidence. No committed evidence file is modified and no
report is regenerated:

| Path | Nature | Bytes |
|---|---|---|
| `sim/kltsim/ibsweep.py` and `sim/kltsim/tests/test_ibsweep.py` | per-point probe validation, coverage keys, 12 new fixtures | +10411 |
| `sim/evidence-size-budget.json` | extended cumulative entry | +75 |

The total is the measured overage, 10411 + 75 = 10486 B. This record lives
under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **10486 B**. The single `sim` entry
carries the cumulative 28228705 + 10486 = **28239191 B** and cites this
record. The baseline, the 10 % allowance and all existing evidence are
unchanged. No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28239191}
```

(Cumulative: 28228705 B from DR-0005 to DR-0027 and 10486 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance: the next `sim/` growth needs its own
  record.

# 0017: Evidence-size exception for the full-noise re-analysis evidence (issue #192)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json`
  (issue #132's contract), exactly the measured overage of 132178 B. It takes
  effect with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0016. The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR #200 (Refs issue #192). The operator
  reviews the raise as a governance item at merge.
- **Related**:
  [`0012-noise-uncertainty-evidence-size-exception.md`](0012-noise-uncertainty-evidence-size-exception.md)
  (the issue #192 reducer code, landed by PR #198),
  [`0016-clock-supply-sensitivity-evidence-size-exception.md`](0016-clock-supply-sensitivity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

PR #198 closed issue #192: the issue #81 full-noise reducer now carries the
grader's shared-draw notes and counts, labels the independent-point grid-mean
standard error as conditional, adds the conservative fully-correlated bound,
and labels partial grids (DR-0012 covered that code). It did not re-run the
reducer over the committed issue #81 campaign, so that campaign's reports
still show the old single, unlabelled standard error.

This record covers the re-analysis evidence. A `noise-full --identity NAME`
option writes the revised report under a NEW evidence identity,
`sim/klt-corner-verification/campaigns/20261011-issue81-reanalysis-issue192`
(JSON plus Markdown). It was re-reduced offline from the committed issue #81
envelopes with the #198 reducer; no new simulation ran. The committed
`20261009-issue81` outputs are untouched, and the option refuses to overwrite
an identity that already holds a report.

| Path | Bytes added |
|---|---|
| `sim/klt-corner-verification/campaigns/20261011-issue81-reanalysis-issue192/noise_full.json` (new unit) | 118006 |
| `sim/klt-corner-verification/campaigns/20261011-issue81-reanalysis-issue192/noise_full.md` (new unit) | 11647 |
| `sim/kltsim/tests/test_noise_full.py` | 1677 |
| `sim/kltsim/cli.py` | 730 |
| `sim/evidence-size-budget.json` (this exception entry) | 118 |
| **Total** | **132178** |

## Decision

Raise the `sim/` total ceiling by exactly **132178 B**. The single `sim` entry
carries the cumulative 26503473 + 132178 = **26635651 B** and cites this
record. The new unit is far below the new-unit ceiling.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 26635651}
```

(Cumulative: 26503473 B from DR-0005 to DR-0016 and 132178 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No committed `sim/` evidence file is
  modified.

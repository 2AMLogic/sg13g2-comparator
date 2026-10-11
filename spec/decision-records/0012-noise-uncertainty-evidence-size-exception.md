# 0012: Evidence-size exception for noise-analysis uncertainty code and tests (issue #192)

- **Status**: proposed. **This record covers the evidence budget only, and the
  growth it covers is reducer/renderer code and unit tests, not evidence.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json`
  (issue #132's contract), exactly the measured overage of 5936 B. It takes
  effect with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0011. The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #192. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0011-cm-band-runner-tests-evidence-size-exception.md`](0011-cm-band-runner-tests-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #192 makes `sim/kltsim/noise_full.py` keep the grader's cross-point
shared-draw notes and counts, label the grid-mean SE as conditional on
independent points, add the fully correlated SE bound and partial labelling,
with synthetic unit tests. No committed campaign output is modified or
regenerated. After DR-0011 `sim/` was exactly at its ceiling.

| Path | Bytes added |
|---|---|
| `sim/kltsim/noise_full.py` | 3099 |
| `sim/kltsim/tests/test_noise_full.py` | 2764 |
| `sim/evidence-size-budget.json` (this exception entry) | 73 |
| **Total** | **5936** |

## Decision

Raise the `sim/` total ceiling by exactly **5936 B**. The single `sim` entry
carries the cumulative 15620585 + 5936 = **15626521 B** and cites this record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15626521}
```

(Cumulative: 15620585 B from DR-0005 to DR-0011 and 5936 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No `sim/` evidence file is modified.

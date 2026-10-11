# 0012: Evidence-size exception for the full-noise uncertainty reanalysis (issue #192)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json`
  (issue #132's contract), exactly the measured overage of 138428 B. It takes
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

Issue #192 makes the issue #81 full-noise reducer carry the grader's
shared-draw notes and counts, label the independent-point grid-mean standard
error as conditional, add the conservative fully-correlated bound, and label
partial grids. The revised analysis is written under a NEW evidence identity,
`sim/klt-corner-verification/campaigns/20261011-issue81-reanalysis-issue192`
(JSON plus Markdown, re-reduced offline from the committed issue #81
envelopes; no new simulation). The committed `20261009-issue81` outputs are
untouched.

| Path | Bytes added |
|---|---|
| `sim/klt-corner-verification/campaigns/20261011-issue81-reanalysis-issue192/` (new unit) | reanalysis JSON + Markdown |
| `sim/kltsim/noise_full.py`, `sim/kltsim/cli.py`, `sim/kltsim/tests/test_noise_full.py` | reducer, renderer, `--identity`, tests |
| `sim/evidence-size-budget.json` (this exception entry) | entry text |
| **Total** | **138428** |

## Decision

Raise the `sim/` total ceiling by exactly **138428 B**. The checker rejects
duplicate exception paths, so the single `sim` entry carries the cumulative
15620585 + 138428 = **15759013 B** and cites this record. The DR-0005 to DR-0011
parts carry over unchanged. The new unit is far below the new-unit ceiling.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15759013}
```

(Cumulative: 15620585 B from DR-0005 to DR-0011 and 138428 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No committed `sim/` evidence file is
  modified.

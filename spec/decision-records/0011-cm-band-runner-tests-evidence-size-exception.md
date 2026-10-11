# 0011: Evidence-size exception for CM-band runner unit tests (issue #186)

- **Status**: proposed. **This record covers the evidence budget only, and
  the growth it covers is test code, not evidence.** It ratifies no bound and
  relaxes no Target or Stretch number. It authorizes one raise of the `sim/`
  total ceiling in `sim/evidence-size-budget.json` (issue #132's contract),
  exactly the measured overage of 5524 B. It takes effect with the reviewed
  merge of the PR that lands it, as for DR-0005 to DR-0010. The drafting agent
  does not merge it. 0004 is reserved by the unmerged DR-0004 draft (#166).
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #186. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0010-harness-frozen-inputs-evidence-size-exception.md`](0010-harness-frozen-inputs-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #186 adds stdlib unit tests for `sim/run_offset_cm_band.py`, the
CM-band campaign orchestrator: the `_submit_with_retry` bounds and exit codes,
`cmd_run` with and without `--skip-existing`, and the append-only refusals in
`cmd_control` and `cmd_repeat`. The budget counts every tracked blob under
`sim/`, and the tests sit beside the other kltsim tests. After DR-0010 `sim/`
was exactly at its ceiling, so any added file overflows.

| Path | Bytes added |
|---|---|
| `sim/kltsim/tests/test_run_offset_cm_band.py` | 5470 |
| `sim/evidence-size-budget.json` (this exception entry) | 54 |
| **Total** | **5524** |

No new evidence unit is added; only the total needs a raise.

## Decision

Raise the `sim/` total ceiling by exactly **5524 B**. The checker rejects
duplicate exception paths, so the single `sim` entry carries the cumulative
15615061 + 5524 = **15620585 B** and cites this record. The DR-0005 to DR-0010
parts carry over unchanged.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15620585}
```

(Cumulative: 15615061 B from DR-0005 to DR-0010 and 5524 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No `sim/` evidence file is modified.

# 0013: Evidence-size exception for runner timeout-diagnostics code and tests (issue #197)

- **Status**: proposed. **This record covers the evidence budget only. The
  growth it covers is harness code and unit tests, not evidence.** It ratifies
  no bound and relaxes no Target or Stretch number. It authorizes one raise of
  the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue #132's
  contract) by exactly the measured overage of 4369 B. It takes effect when the
  PR that lands it is reviewed and merged, as for DR-0005 to DR-0012. The
  drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR #201 for issue #197. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0012-noise-uncertainty-evidence-size-exception.md`](0012-noise-uncertainty-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #197 changes `sim/harness/runner.py` so that a local PVT point that
times out keeps ngspice's partial stdout and stderr in its log. The point is
still recorded as `status="error"`, and its partial output is never parsed.
The PR also adds synthetic unit tests. No committed campaign output is
modified or regenerated, and no evidence is added. After DR-0012 the `sim/`
total was exactly at its ceiling. `sim/harness/` counts toward that ceiling,
so this code alone pushes the total over it.

| Path | Bytes added |
|---|---|
| `sim/harness/runner.py` | 1529 |
| `sim/harness/tests/test_runner.py` | 2755 |
| `sim/evidence-size-budget.json` (this exception entry) | 85 |
| **Total** | **4369** |

## Decision

Raise the `sim/` total ceiling by exactly **4369 B**. The single `sim` entry
holds the cumulative 15626521 + 4369 = **15630890 B** and cites this record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15630890}
```

(Cumulative: 15626521 B from DR-0005 to DR-0012, plus 4369 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- This is an exact raise, not a standing allowance. No `sim/` evidence file is
  modified.

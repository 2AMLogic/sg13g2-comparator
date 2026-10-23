# 0026: Evidence-size exception for CM-band empty-reproduction verdict (issue #252)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 4925 B. It takes effect
  only with the reviewed merge of the PR that lands it (PR #256), as for
  DR-0005 to DR-0025. The drafting agent does not merge it, and drafting it is
  not agents relaxing the ratified spec.
- **Date**: 2026-10-12
- **Decided by**: Doctor agent for issue #252, drafted at the Judge's request
  on PR #256. The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0025-cm-offset-draw-validation-evidence-size-exception.md`](0025-cm-offset-draw-validation-evidence-size-exception.md)
  (previous `sim/` total raise; still stands),
  [`0021-cm-decision-validation-evidence-size-exception.md`](0021-cm-decision-validation-evidence-size-exception.md),
  [`0011-cm-band-runner-tests-evidence-size-exception.md`](0011-cm-band-runner-tests-evidence-size-exception.md)
- **Supersedes**: none. **Superseded by**: none
- **Numbering**: DR-0024 is in use by open, unmerged PRs (#249, #243). If one
  of them merges first and changes `sim/`, the cumulative `sim` entry is
  re-measured on rebase. This record's own 4925 B does not change unless this
  PR's `sim/` diff changes.

## Context

Issue #252 tightens the reproduction check in the whole-latch common-mode
offset characterization (`sim/kltsim/cmband.py`):

- An empty comparison (no shared points, or a shared point with no expected
  and no observed draws) is reported as `INCOMPLETE` with
  `empty_comparison=true` and an `empty_reason`, not as reproduced.
- `rejected_draws` counts one entry per rejected record on each side, so
  repeated invalid identities and every copy of a duplicate index are counted.

On main, `sim/` was exactly at its ceiling, so any addition needs this
exception. The growth is code and tests, not evidence. No existing evidence
file is modified and no report is regenerated:

| Path | Nature | Bytes |
|---|---|---|
| `sim/kltsim/cmband.py` | empty-comparison verdict, per-record rejected-draw identities | +1152 |
| `sim/kltsim/tests/test_cmband.py` | empty-reproduction and rejected-draw count tests | +3653 |
| `sim/evidence-size-budget.json` | extended cumulative entry | +120 |

The total is the measured overage, 4805 + 120 = 4925 B. This record lives
under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **4925 B**. The single `sim` entry
carries the cumulative 28211007 + 4925 = **28215932 B** and cites this
record. The baseline, the 10 % allowance and all existing evidence are
unchanged. No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28215932}
```

(Cumulative: 28211007 B from DR-0005 to DR-0025 and 4925 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance: the next `sim/` growth needs its own
  record.

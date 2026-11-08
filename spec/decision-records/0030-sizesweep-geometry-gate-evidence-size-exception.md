# 0030: Evidence-size exception for sizing-finalist geometry gate (issue #269)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 6685 B. It takes effect
  only with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0029. The drafting agent does not merge it, and drafting it is not agents
  relaxing the ratified spec.
- **Date**: 2026-10-12
- **Decided by**: Doctor agent for PR #273 (issue #269), following the DR-0029
  pattern. The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0029-ibsweep-validation-evidence-size-exception.md`](0029-ibsweep-validation-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)
- **Numbering**: DR-0028 is taken by open PR #265, and DR-0024 remains
  double-booked by open, unmerged PRs (#249, #243). This record chains its
  cumulative `sim` entry on DR-0029, the latest merged raise. Whichever PR
  merges first keeps its number and cumulative figure; the others are
  renumbered on rebase with their cumulative `sim` entry re-measured. This
  record's own 6685 B does not change unless this PR's `sim/` diff changes.

## Context

Issue #269 gates the full-grid finalist summary in `sim/kltsim/sizesweep.py`
on cross-bench geometry validation. A candidate whose bench geometry is
inconsistent or unreadable is marked `rejected` with reasons. Its cells are not
graded MET or FAIL, and the per-bench grades are kept as diagnostics. On main,
`sim/` was exactly at its ceiling, so any addition needs this exception. The
growth is code and tests, not evidence. No committed evidence file is modified
and no report is regenerated:

| Path | Nature | Bytes |
|---|---|---|
| `sim/kltsim/sizesweep.py` | finalist geometry gate, rejected state, Markdown/JSON reporting | +1973 |
| `sim/kltsim/tests/test_sizesweep.py` | 5 new fixtures (consistent baseline/override, conflicting, unreadable, missing bench) | +4616 |
| `sim/evidence-size-budget.json` | extended cumulative entry | +96 |

The total is the measured overage, 1973 + 4616 + 96 = 6685 B. This record
lives under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **6685 B**. The single `sim` entry
carries the cumulative 28239191 + 6685 = **28245876 B** and cites this record.
The baseline, the 10 % allowance and all existing evidence are unchanged. No
ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28245876}
```

(Cumulative: 28239191 B from DR-0005 to DR-0029 and 6685 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance: the next `sim/` growth needs its own
  record.

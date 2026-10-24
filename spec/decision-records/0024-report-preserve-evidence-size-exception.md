# 0024: Evidence-size exception for derived report-pair preservation (issue #237)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 17962 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0023.
  The drafting agent does not merge it.
- **Date**: 2026-10-12
- **Decided by**: Builder agent, PR for issue #237 (pending Judge review).
  The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0030-sizesweep-geometry-gate-evidence-size-exception.md`](0030-sizesweep-geometry-gate-evidence-size-exception.md)
  (previous `sim/` total raise on main; still stands)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)

## Context

Issue #237 adds a shared append-only planned-byte writer
(`sim/kltsim/artifacts.py`) and uses it for the grading, noise-full and clock
comparison report pairs, with read-only `--check` and `--report-dir`. After
DR-0023 `sim/` was exactly at its ceiling, so any addition needs this
exception. The growth is code, tests and docs, not evidence; no existing
evidence file is modified and no report is regenerated. The total is the
measured overage of the PR (new/changed files under `sim/`, including the
budget file's own reason text).

While this PR was in review, main advanced from DR-0023 to DR-0030
(+65089 B, issues #250/#252/#255/#267/#269), so the branch was rebased onto
it. The raise authorized here is unchanged at 17962 B over the DR-0030
state; only the cumulative basis moved.

## Decision

Raise the `sim/` total ceiling by exactly **17962 B**. The single `sim` entry
carries the cumulative 28245876 + 17962 = **28263838 B** and cites this record. No
ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28263838}
```

(Cumulative: 28245876 B from DR-0005 to DR-0030 as on main and 17962 B
authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

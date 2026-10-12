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
  [`0023-pex-decision-validity-evidence-size-exception.md`](0023-pex-decision-validity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #237 adds a shared append-only planned-byte writer
(`sim/kltsim/artifacts.py`) and uses it for the grading, noise-full and clock
comparison report pairs, with read-only `--check` and `--report-dir`. After
DR-0023 `sim/` was exactly at its ceiling, so any addition needs this
exception. The growth is code, tests and docs, not evidence; no existing
evidence file is modified and no report is regenerated. The total is the
measured overage of the PR (new/changed files under `sim/`, including the
budget file's own reason text).

## Decision

Raise the `sim/` total ceiling by exactly **17962 B**. The single `sim` entry
carries the cumulative 28180787 + 17962 = **28198749 B** and cites this record. No
ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28198749}
```

(Cumulative: 28180787 B from DR-0005 to DR-0023 and 17962 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

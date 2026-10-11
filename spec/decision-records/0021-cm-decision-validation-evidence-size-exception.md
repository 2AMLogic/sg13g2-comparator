# 0021: Evidence-size exception for the CM decision-band validation fix (issue #209)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 3604 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0020.
  The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR #225 for issue #209, at the Judge's request.
  The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0020-sparse-lint-population-evidence-size-exception.md`](0020-sparse-lint-population-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #209 hardens the CM decision-band validation in `sim/kltsim/`:
`reproduction()` now compares every reference measurement at each expected
point, and `load_points()` rejects non-finite or non-numeric `vcm_meas`
probes before the tolerance comparison. The validation code grows
`sim/kltsim/cmdecision.py` by 651 B and its regression tests grow
`sim/kltsim/tests/test_cmdecision.py` by 2854 B, 3505 B in total. These are
code and tests, not evidence. No existing evidence file is modified. After
DR-0020, `sim/` was exactly at its ceiling, so any addition needs this
exception. Extending the cumulative budget exception entry adds a further
99 B to `sim/evidence-size-budget.json`, which is a `sim/` file and counts
toward the total. The measured overage is therefore 3505 + 99 = 3604 B. This
record lives under `spec/` and adds nothing to `sim/`. The tests were not
trimmed to fit, so regression coverage is unchanged.

## Decision

Raise the `sim/` total ceiling by exactly **3604 B**. The single `sim` entry
carries the cumulative 28032418 + 3604 = **28036022 B** and cites this record.
No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28036022}
```

(Cumulative: 28032418 B from DR-0005 to DR-0020 and 3604 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

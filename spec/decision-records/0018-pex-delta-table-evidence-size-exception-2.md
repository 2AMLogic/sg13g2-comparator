# 0018: Evidence-size exception for the PEX delta-table renderer fix (issue #211)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 6122 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0017.
  The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR for issue #211 (after Judge review). The
  operator reviews the raise as a governance item at merge.
- **Related**:
  [`0017-decision-cm-band-evidence-size-exception.md`](0017-decision-cm-band-evidence-size-exception.md)
  (previous `sim/` total raise; still stands),
  [`0009-pex-delta-table-evidence-size-exception.md`](0009-pex-delta-table-evidence-size-exception.md)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)

## Context

Issue #211 changes the PEX delta-table renderer
(`sim/comparator-pex/make_delta_table.py`, +2169 B) and its unit tests
(`sim/comparator-pex/tests/test_delta_table.py`, +3885 B), 6054 B in total.
These are code and tests, not evidence; no existing evidence file is modified.
After DR-0017 `sim/` was exactly at its ceiling, so any addition needs this
exception. Updating the budget exception entry itself adds a further 78 B to
`sim/evidence-size-budget.json` (a `sim/` file that counts toward the total),
bringing the measured overage to 6044 + 78 = 6122 B. This record lives under
`spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **6122 B**. The single `sim` entry
carries the cumulative 28018410 + 6122 = **28024532 B** and cites this record.
No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28024532}
```

(Cumulative: 28018410 B from DR-0005 to DR-0017 and 6122 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

# 0019: Evidence-size exception for the CM-band preflight run-submission guard (issue #194)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 7127 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0018.
  The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR for issue #194 (after Judge review). The
  operator reviews the raise as a governance item at merge.
- **Related**:
  [`0018-pex-delta-table-evidence-size-exception-2.md`](0018-pex-delta-table-evidence-size-exception-2.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #194 adds preflight run-submission checks to the CM-band runner
(`sim/run_offset_cm_band.py`, +1597 B), extends its unit tests
(`sim/kltsim/tests/test_run_offset_cm_band.py`, +4606 B), and documents the
new behavior (`sim/comparator-offset-cm-band/README.md`, +830 B), 7033 B in
total. These are code, tests and docs, not evidence; no existing evidence file
is modified. After DR-0018 `sim/` was exactly at its ceiling, so any addition
needs this exception. Updating the budget exception entry itself adds a
further 94 B to `sim/evidence-size-budget.json` (a `sim/` file that counts
toward the total), bringing the measured overage to 7033 + 94 = 7127 B. This
record lives under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **7127 B**. The single `sim` entry
carries the cumulative 28024532 + 7127 = **28031659 B** and cites this record.
No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28031659}
```

(Cumulative: 28024532 B from DR-0005 to DR-0018 and 7127 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

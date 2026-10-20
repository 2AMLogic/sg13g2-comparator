# 0031: Evidence-size exception for the kickback common-mode-band campaign (issue #165)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number, and the campaign
  it covers is characterization for the candidate DR-0004 row, not
  compliance. It authorizes one raise of the `sim/` total ceiling in
  `sim/evidence-size-budget.json` (issue #132's contract), exactly the
  measured overage of 1794306 B. It takes effect with the reviewed merge of
  the PR that lands it, as for DR-0005 to DR-0030. The drafting agent does
  not merge it.
- **Date**: 2026-10-11 (cumulative entry re-measured on merge, 2026-10-15)
- **Decided by**: Builder agent, PR for issue #165. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0030-sizesweep-geometry-gate-evidence-size-exception.md`](0030-sizesweep-geometry-gate-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none
- **Numbering**: this record was drafted as DR-0018 against an earlier
  `main`; DR-0018 is taken by the merged pex-delta-table raise (issue #211,
  `0018-pex-delta-table-evidence-size-exception-2.md`). Per the DR-0030
  convention the record is renumbered on merge to the next free number,
  0031, and its cumulative `sim` entry is re-measured: `main` advanced by
  DR-0018 (6122 B) through DR-0030 (6685 B), including DR-0024 (17962 B,
  issue #237), 245428 B in total. This
  record's own raise is unchanged at 1794306 B.

## Context

Issue #165 adds `sim/comparator-kickback-cm-band/`: three deterministic
45-point kickback envelopes (about 0.46 MB each) with their per-corner
artifacts (kept, as in the reference `20261009-d73a9ac/kickback`), requests,
bodies, invocations and a generated comparison, plus one module, runner,
tests and README. The envelopes are the evidence itself and cannot be dropped.
After DR-0030 `sim/` was exactly at its ceiling, so any addition needs this
exception. The campaign unit (about 1.7 MB) is far under the 47 MiB new-unit
ceiling; only the `sim/` total is raised.

## Decision

Raise the `sim/` total ceiling by exactly **1794306 B**. The single `sim` entry
carries the cumulative 28263838 + 1794306 = **30058144 B** and cites this record.
The 28263838 B covers DR-0005 to DR-0030 (including DR-0024) on merged `main` and carries over
unchanged; the only new allowance here is the 1794306 B increment.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 30058144}
```

(Cumulative: 28263838 B from DR-0005 to DR-0030 on merged `main` and 1794306 B
authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No existing `sim/` evidence file is
  modified.

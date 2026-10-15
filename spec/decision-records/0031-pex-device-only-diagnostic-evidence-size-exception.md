# 0031: Evidence-size exception for the extracted-device-only PEX diagnostic leg (issue #191)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json`
  (issue #132's contract), exactly the measured overage of 331406 B. It takes
  effect with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0030. The drafting agent does not merge it.
- **Date**: 2026-10-11 (cumulative entry re-measured on merge, 2026-10-13; re-measured again 2026-10-15 after DR-0024 landed)
- **Decided by**: Builder agent, PR for issue #191. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0030-sizesweep-geometry-gate-evidence-size-exception.md`](0030-sizesweep-geometry-gate-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none
- **Numbering**: this record was drafted as DR-0013 against an earlier
  `main`; DR-0013 is taken by the merged runner timeout-diagnostics raise
  (issue #197, `0013-runner-timeout-diagnostics-evidence-size-exception.md`).
  Per the DR-0030 convention the record is renumbered on merge to the next
  free number, 0031, and its cumulative `sim` entry is re-measured: `main`
  advanced by DR-0013 (4369 B) through DR-0030 (6685 B), 12619355 B in total.
  This record's own raise is unchanged at 331406 B. A second re-measure
  followed once DR-0024 (issue #237, 17962 B) merged to `main` ahead of this
  record: the cumulative base is now 28263838 B.

## Context

Issue #191 adds a diagnostic extracted-device-only leg under
`sim/comparator-pex/`: the netlist adapter and its tests, the generated
device-only netlist, testbench and requests, and a newly named three-leg
report. The largest part is the verbatim 45-point batch envelope
(`reports/devonly-pvt-batch.20261011.json`, all points errored,
`batch_runner_version_mismatch`), kept because every PVT point must be
retained, failures included. Nothing existing is modified.

## Decision

Raise the `sim/` total ceiling by exactly **331406 B**. The checker rejects
duplicate exception paths, so the single `sim` entry carries the cumulative
28263838 (main after DR-0030 and DR-0024) + 331406 = **28595244 B** and cites
this record. The 28263838 B covers DR-0005 to DR-0030 on merged `main`
(including DR-0024's 17962 B) and carries over
unchanged; the only new allowance here is the 331406 B increment.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28595244}
```

(Cumulative: 28263838 B from DR-0005 to DR-0030 on merged `main` and 331406 B
authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No existing `sim/` evidence file is
  modified.

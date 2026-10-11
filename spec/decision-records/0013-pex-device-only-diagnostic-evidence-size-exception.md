# 0013: Evidence-size exception for the extracted-device-only PEX diagnostic leg (issue #191)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json`
  (issue #132's contract), exactly the measured overage of 331406 B. It takes
  effect with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0012. The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #191. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0012-noise-uncertainty-evidence-size-exception.md`](0012-noise-uncertainty-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

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
15626521 (main after DR-0012) + 331406 = **15957927 B** and cites this record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15957927}
```

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No existing `sim/` evidence file is
  modified.

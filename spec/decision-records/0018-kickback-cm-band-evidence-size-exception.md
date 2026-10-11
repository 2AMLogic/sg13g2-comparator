# 0018: Evidence-size exception for the kickback common-mode-band campaign (issue #165)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number, and the campaign
  it covers is characterization for the candidate DR-0004 row, not
  compliance. It authorizes one raise of the `sim/` total ceiling in
  `sim/evidence-size-budget.json` (issue #132's contract), exactly the
  measured overage of 1794306 B. It takes effect with the reviewed merge of
  the PR that lands it, as for DR-0005 to DR-0017. The drafting agent does
  not merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #165. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0017-decision-cm-band-evidence-size-exception.md`](0017-decision-cm-band-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #165 adds `sim/comparator-kickback-cm-band/`: three deterministic
45-point kickback envelopes (about 0.46 MB each) with their per-corner
artifacts (kept, as in the reference `20261009-d73a9ac/kickback`), requests,
bodies, invocations and a generated comparison, plus one module, runner,
tests and README. The envelopes are the evidence itself and cannot be dropped.
After DR-0017 `sim/` was exactly at its ceiling, so any addition needs this
exception. The campaign unit (about 1.7 MB) is far under the 47 MiB new-unit
ceiling; only the `sim/` total is raised.

## Decision

Raise the `sim/` total ceiling by exactly **1794306 B**. The single `sim` entry
carries the cumulative 28018410 + 1794306 = **29812716 B** and cites this record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 29812716}
```

(Cumulative: 28018410 B from DR-0005 to DR-0017 and 1794306 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No existing `sim/` evidence file is
  modified.

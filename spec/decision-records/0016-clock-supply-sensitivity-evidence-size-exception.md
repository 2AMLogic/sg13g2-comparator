# 0016: Evidence-size exception for the clock-edge and supply-disturbance sensitivity campaign (issue #173)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number, and the campaign
  it covers is characterization, not compliance. It authorizes one raise of
  the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue #132's
  contract), exactly the measured overage of 10838239 B. It takes effect with
  the reviewed merge of the PR that lands it, as for DR-0005 to DR-0015. The
  drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #173. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0015-model-source-identity-evidence-size-exception.md`](0015-model-source-identity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #173 adds a new experiment, `sim/comparator-clock-supply-sensitivity/`,
with nine conditions, each a 45-point regeneration envelope and a 20-point
x 16-draw paired offset envelope, plus harness code, unit tests and a README.
The campaign is already the reduced form the issue asks for: per-corner
artifacts are not kept (`keep_artifacts: false`), the offset grid is 20 of 45
points and N = 16 of 60 draws, and the envelopes (about 0.84 MB per offset
envelope and 0.30 MB per regeneration envelope) are the evidence itself, so
they cannot be dropped. After DR-0015 `sim/` was exactly at its ceiling, so
any addition needs this exception. The campaign unit (about 10.8 MB) is far
under the 47 MiB new-unit ceiling; only the `sim/` total is raised.

## Decision

Raise the `sim/` total ceiling by exactly **10838239 B**. The single `sim` entry
carries the cumulative 15665234 + 10838239 = **26503473 B** and cites this
record.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 26503473}
```

(Cumulative: 15665234 B from DR-0005 to DR-0015 and 10838239 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance. No existing `sim/` evidence file is
  modified.

# 0028: Evidence-size exception for timestep smoke validation (issue #263)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 33058 B. It takes effect
  only with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0027. The drafting agent does not merge it.
- **Date**: 2026-10-12
- **Decided by**: Builder agent for issue #263, following the DR-0027 pattern.
  The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0027-yield-index-rederivation-evidence-size-exception.md`](0027-yield-index-rederivation-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none
- **Numbering**: DR-0024 remains double-booked by open PRs, as DR-0026 and
  DR-0027 record. If another open PR lands a record with a `sim` entry first,
  this one is renumbered on rebase and its cumulative entry re-measured.

## Context

Issue #263 makes `sim/kltsim/noise_full.py` `timestep_convergence()` validate
each `smoke/timestep-<step>` rung (saved hash chain, smoke request contract,
nominal corner, `tn_full_both` body and DUT, sample identities, un-errored and
trusted samples, finite 0/1 hits, distinct raw-noise draws, declared N) before
any sigma or SE is computed, and compare rungs only when nothing but the solver
step / max step differs. Invalid rungs keep diagnostics and contribute no
statistic; absent smoke evidence is reported as unavailable.

On main, `sim/` was exactly at its ceiling, so any addition needs this
exception. The growth is code, tests and documentation, not evidence. No
existing evidence file is modified and no report is regenerated (the validator
reproduces the historical 1.324 / 1.116 / 1.414 mV table, checked in a
throwaway run):

| Path | Nature |
|---|---|
| `sim/kltsim/noise_full.py` | smoke validation, cross-rung comparability, renderer |
| `sim/kltsim/tests/test_noise_full.py` | temporary-fixture tests (identity, provenance, probes, cross-rung change, missing rungs, declared N) |
| `sim/comparator-transient-noise-full/README.md` | what the timestep validator checks |
| `sim/evidence-size-budget.json` | extended cumulative entry |

The total is the measured overage, 33058 B. This record lives under `spec/` and
adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **33058 B**. The single `sim` entry
carries the cumulative 28228705 + 33058 = **28261763 B** and cites this record. The
baseline, the 10 % allowance and all existing evidence are unchanged. No
ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28261763}
```

(Cumulative: 28228705 B from DR-0005 to DR-0027 and 33058 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance: the next `sim/` growth needs its own
  record.

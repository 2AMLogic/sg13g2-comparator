# 0019: Evidence-size exception for the max-step supplement failed-attempt evidence (issue #89)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 495286 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0018.
  The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR for issue #89 (after Judge review). The
  operator reviews the raise as a governance item at merge.
- **Related**:
  [`0018-pex-delta-table-evidence-size-exception-2.md`](0018-pex-delta-table-evidence-size-exception-2.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #89 adds the max-step supplement workflow: harness code
(`sim/kltsim/cmband.py`, `sim/run_offset_cm_band.py`), unit tests, README
updates, and the campaign unit
`sim/comparator-offset-cm-band/campaigns/20261011-33aef587e-maxstep20p`
(445730 B) recording a batch submission that produced **no simulation data**
(every job failed as `batch_job_failed`: the fleet runner ran klt 0.5.0,
incompatible with the 0.6.0/0.7.0 submitting clients). Per the Judge review,
the six no-data envelopes are committed slim as byte-exact `gzip -9n` copies
(`*.envelope.json.gz`, 196363 B total) whose decompressed bytes still hash to
each invocation's `envelope_sha256`; the rest of the unit is requests, bodies,
attempts, invocations and the generated report. The campaign directory is new
in this PR — no pre-existing evidence file is modified. The workflow's code,
tests and docs under `sim/` add a further 49464 B. After DR-0018 `sim/` was
exactly at its ceiling, so any addition needs this exception (the workflow
necessarily ships code under `sim/`, so net-zero growth is not available).
Updating the budget exception entry itself adds 92 B to
`sim/evidence-size-budget.json` (a `sim/` file that counts toward the total),
bringing the measured overage to 445730 + 49464 + 92 = **495286 B**. This
record lives under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **495286 B**. The single `sim` entry
carries the cumulative 28024532 + 495286 = **28519818 B** and cites this
record. No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28519818}
```

(Cumulative: 28024532 B from DR-0005 to DR-0018 and 495286 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.
- The gzip form applies to this run's no-data envelopes only because they are
  new in this PR; it is not a licence to recompress already-merged evidence.

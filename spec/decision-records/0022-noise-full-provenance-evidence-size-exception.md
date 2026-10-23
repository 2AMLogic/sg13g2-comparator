# 0022: Evidence-size exception for noise-full provenance validation (issue #236)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 133526 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0021.
  The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #236. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0021-cm-decision-validation-evidence-size-exception.md`](0021-cm-decision-validation-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #236 makes `sim/kltsim/noise_full.py` validate each `tn_full_*`
configuration's request/invocation/envelope hashes, request semantics, input
hash, embedded DUT and body injection configuration before any sigma is
computed, rejecting (never `complete`) a configuration that fails. After
DR-0021, `sim/` was within 62 B of its ceiling, so any addition needs this
exception. The growth is:

| Path | Nature | Approx. bytes |
|---|---|---|
| `sim/comparator-transient-noise-full/reports/analysis-20261011-issue236/` | new evidence namespace: provenance-validated re-analysis of the unchanged issue #81 inputs (`noise_full.json` compact, `noise_full.md`) | 112019 |
| `sim/kltsim/noise_full.py`, `cli.py`, `tests/test_noise_full.py` | validation code and temporary-fixture tests | ~20000 |
| `sim/comparator-transient-noise-full/README.md` | pointer to the re-analysis | ~1000 |
| `sim/evidence-size-budget.json` | extended cumulative entry | 100 |

The exact total is the measured overage, 133526 B. The historical issue #81
`noise_full.*` is not modified or regenerated (the command now refuses to
overwrite existing output); the new analysis reproduces its numbers. The
per-point JSON was written compactly to limit the growth; the tests were not
trimmed to fit.

## Decision

Raise the `sim/` total ceiling by exactly **133526 B**. The single `sim` entry
carries the cumulative 28036022 + 133526 = **28169548 B** and cites this
record. No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28169548}
```

(Cumulative: 28036022 B from DR-0005 to DR-0021 and 133526 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

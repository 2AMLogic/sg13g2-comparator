# 0024: Evidence-size exception for Monte Carlo sample-population validation (issue #245)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 113973 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0023.
  The drafting agent does not merge it.
- **Date**: 2026-10-12
- **Decided by**: Builder agent, PR for issue #245 (pending Judge review).
  The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0023-pex-decision-validity-evidence-size-exception.md`](0023-pex-decision-validity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #245 makes the offset and transient-noise compliance reducers validate
each PVT point's actual Monte Carlo sample records (unique sample indices,
one base corner, exactly the declared N, consistent summary counts) before
using a klt summary, sharing one validator with the yield collector. After
DR-0023 `sim/` was exactly at its ceiling, so any addition needs this
exception. The grader's sha256 is an indexed source of the T1 item 8
characterization report, and report directories are append-only, so the
report is re-minted in a NEW directory; the earlier one is untouched. Its
numbers are identical (the grader still equals the committed `grading.json`);
only the grader digest and hence the input-index hash differ.

| Path | Nature | Bytes |
|---|---|---|
| `sim/characterization/20261009-d73a9ac-schematic-r2/` | re-minted derived report (4 files) | see below |
| `sim/kltsim/populations.py` | shared validator (new) | see below |
| `sim/kltsim/tests/test_populations.py` | regression tests (new) | see below |
| `sim/kltsim/{grade,yield_reports,characterization}.py`, `sim/README.md` | integration, report-id map, docs | see below |
| `sim/evidence-size-budget.json` | extended cumulative entry | see below |

The total is the measured overage, 113973 B (blob bytes at the PR head, from
`python3 scripts/check_evidence_size.py --tree HEAD`). This record lives under
`spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **113973 B**. The single `sim` entry
carries the cumulative 28180787 + 113973 = **28294760 B** and cites this record. No
ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28294760}
```

(Cumulative: 28180787 B from DR-0005 to DR-0023 and 113973 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

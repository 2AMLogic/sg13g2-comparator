# 0020: Evidence-size exception for the sparse lint-population preflight docs (issue #216)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 759 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0019.
  The drafting agent does not merge it.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue #216. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0019-cm-band-preflight-evidence-size-exception.md`](0019-cm-band-preflight-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)

## Context

Issue #216 completes the harness job's sparse cone for the reviewed ruff
F-rule scope and documents that audit: the `sim/README.md` sparse-checkout
table row for the harness job plus one guard paragraph grow the file by
682 B. These are documentation only, not evidence; no existing evidence file
is modified (the new preflight script and its tests live under `scripts/`,
outside the budget). After DR-0019 `sim/` was exactly at its ceiling, so any
addition needs this exception. Extending the cumulative budget exception
entry itself adds a further 77 B to `sim/evidence-size-budget.json` (a
`sim/` file that counts toward the total), bringing the measured overage to
682 + 77 = 759 B. This record lives under `spec/` and adds nothing to
`sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **759 B**. The single `sim` entry
carries the cumulative 28031659 + 759 = **28032418 B** and cites this record.
No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28032418}
```

(Cumulative: 28031659 B from DR-0005 to DR-0019 and 759 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.

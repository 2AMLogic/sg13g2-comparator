# 0007: Evidence-size exception for the repeated-measurement harness fix (issue #177)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It changes
  nothing in `spec/` target tables or in `README.md`'s target table. It
  authorizes one raise of the `sim/` total ceiling in
  `sim/evidence-size-budget.json` (issue
  [#132](https://github.com/2AMLogic/sg13g2-comparator/issues/132)'s
  contract). The raise is exactly the measured overage of 2806 B, so the
  harness fix can be committed. The record takes effect with the reviewed
  merge of the PR that lands it. That merge commit is the record of
  acceptance, as for DR-0005 and DR-0006. The drafting agent does not merge
  it. 0004 stays reserved by the in-flight DR-0004 draft
  ([#166](https://github.com/2AMLogic/sg13g2-comparator/pull/166)), and
  0005 and 0006 are taken.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR
  [#183](https://github.com/2AMLogic/sg13g2-comparator/pull/183) for issue
  [#177](https://github.com/2AMLogic/sg13g2-comparator/issues/177).
  Reviewers judge the rationale below as well as the numbers. The operator
  reviews the raise as a governance item at merge.
- **Related**:
  [`0006-offset-significance-evidence-size-exception.md`](0006-offset-significance-evidence-size-exception.md)
  (the previous `sim/` total raise of 14103 B),
  [`0005-offset-n200-evidence-size-exception.md`](0005-offset-n200-evidence-size-exception.md)
  (15571193 B). Both are unchanged and still stand.
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #177 is a correctness fix in the simulation harness. If ngspice prints
a requested measurement name more than once, the point now fails as
ambiguous and does not keep whichever value came last. The harness code
lives under `sim/harness/`, so it counts toward the `sim/` total. It adds
no simulation evidence and runs no SPICE.

DR-0006 was an exact raise, so `sim/` on `main` sits at its ceiling of
554544197 B (538958901 B plus 15585296 B) with 0 B of headroom. Measured
with `git ls-tree -rl`, this change adds 2806 B to `sim/`:

| Path | Bytes added |
|---|---|
| `sim/harness/tests/test_runner.py` (acceptance-criterion tests) | 1981 |
| `sim/harness/runner.py` (the fix) | 633 |
| `sim/harness/report.py` ("ambiguous" summary label) | 115 |
| `sim/evidence-size-budget.json` (this exception entry) | 77 |
| **Total** | **2806** |

That puts `sim/` at 554547003 B, which is over the ceiling by exactly
2806 B. No evidence unit changes, so only the total needs a raise.

## Decision

1. Raise the `sim/` total ceiling by exactly **2806 B**, the measured
   overage.
2. The checker rejects duplicate exception paths, so the single `sim` entry
   in `sim/evidence-size-budget.json` now carries the cumulative figure
   15585296 + 2806 = **15588102 B**, and it cites this record. The
   15585296 B carried over is the DR-0005 and DR-0006 authorization,
   unchanged. The only new allowance here is the 2806 B increment.

Shrinking the change instead was considered. The three-occurrence test was
already folded into the parametrized duplicate cases, which saved 81 B
against the first draft. Each remaining test maps to an acceptance
criterion of #177: duplicates fail in either order, finite and overflow
mixes fail with the raw text kept, a rejected point cannot produce a
full-grid PASS, and unique or unrequested names behave as before. Dropping
any of them would remove required coverage. Any code fix under `sim/`
needs some raise, because there is no headroom. `sim/` is append-only, so
no existing evidence may be shrunk to make room.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15588102}
```

(Cumulative: 15571193 B from DR-0005, 14103 B from DR-0006, and 2806 B
authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- This is an exact raise, not a standing allowance. Future growth under
  `sim/`, harness code included, needs its own record, which updates the
  cumulative `sim` figure the same way.
- No claim changes. Every ratified bound and target stays untouched.

# 0009: Evidence-size exception for the PEX delta-table renderer (issue #181)

- **Status**: proposed. **This record covers the evidence budget only, and
  the growth it covers is renderer code, tests and docs, not evidence.** It
  ratifies no bound and relaxes no Target or Stretch number. It changes
  nothing in `spec/` target tables or in `README.md`'s target table. It
  authorizes one raise of the `sim/` total ceiling in
  `sim/evidence-size-budget.json` (issue
  [#132](https://github.com/2AMLogic/sg13g2-comparator/issues/132)'s
  contract). The raise is exactly the measured overage of 14615 B. The record
  takes effect with the reviewed merge of the PR that lands it, as for
  DR-0005 to DR-0008. The drafting agent does not merge it. 0004 is still
  reserved by the unmerged DR-0004 draft
  ([#166](https://github.com/2AMLogic/sg13g2-comparator/pull/166)) and 0008
  is taken by the merged DR-0008 (issue #178), so this record takes 0009.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, issue
  [#181](https://github.com/2AMLogic/sg13g2-comparator/issues/181).
  Reviewers judge the rationale as well as the numbers. The operator reviews
  the raise as a governance item at merge.
- **Related**:
  [`0008-harness-bound-validation-evidence-size-exception.md`](0008-harness-bound-validation-evidence-size-exception.md)
  (the previous `sim/` total raise; still stands),
  [`0007-repeated-measurement-harness-evidence-size-exception.md`](0007-repeated-measurement-harness-evidence-size-exception.md),
  [`0006-offset-significance-evidence-size-exception.md`](0006-offset-significance-evidence-size-exception.md),
  [`0005-offset-n200-evidence-size-exception.md`](0005-offset-n200-evidence-size-exception.md)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #181 makes `sim/comparator-pex/make_delta_table.py` importable and
separates klt's raw row status (measurement availability) from a mapped
circuit interpretation: logic rows as states, `td_a`/`td_c` against the
DR-0002 Row 3 absolute bounds, every other key ungraded. Its acceptance
criteria require offline tests for logic reversal, timing failure,
missing/error rows, unknown keys, multiple corners, malformed and non-finite
input, and overwrite refusal. The renderer and its tests live next to the
generators they belong to, under `sim/comparator-pex/`, which CI already
lints and tests. The budget counts every tracked blob under `sim/`, so this
code counts against the evidence ceiling even though it is not evidence.

On `main` (b780e9db1, after DR-0008 merged), `sim/` measures 554552834 B
against a total ceiling of 554552834 B, so there are 0 B of headroom.
Measured with `git ls-tree -rl`, this change adds 14615 B to `sim/`:

| Path | Bytes added |
|---|---|
| `sim/comparator-pex/tests/test_delta_table.py` (new: committed-envelope, mapping-vs-request, synthetic, malformed, CLI tests) | 8043 |
| `sim/comparator-pex/make_delta_table.py` (validation, mapped interpretation, scope) | 5960 |
| `sim/comparator-pex/README.md` (renderer semantics note) | 530 |
| `sim/evidence-size-budget.json` (this exception entry) | 55 |
| `sim/README.md` (sparse-cone audit row: `layout/comparator/pex_report.json`) | 27 |
| **Total** | **14615** |

No new evidence unit is added, so only the total needs a raise.

## Decision

1. Raise the `sim/` total ceiling by exactly **14615 B**, the measured
   overage.
2. The checker rejects duplicate exception paths, so the single `sim` entry
   now carries the cumulative figure 15593933 + 14615 = **15608548 B** and
   cites this record. The 15571193 B (DR-0005), 14103 B (DR-0006), 2806 B
   (DR-0007) and 5831 B (DR-0008) parts carry over unchanged. The only new
   allowance here is the 14615 B increment.

The change was trimmed before this record was written (the first draft
added 15062 B). Placing the renderer outside `sim/` was considered and
rejected: it would split the post-layout adapter from its generators, tests
and README, and move code to dodge the budget rather than account for it.
`sim/` is append-only, so no existing evidence may be shrunk to make room.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15608548}
```

(Cumulative: 15571193 B from DR-0005, 14103 B from DR-0006, 2806 B from
DR-0007, 5831 B from DR-0008 and 14615 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- This is an exact raise, not a standing allowance. Future growth needs its
  own record.
- No claim changes. Every ratified number stays the same, and no `sim/`
  evidence file (including `reports/delta-nominal-20261009.*`) is modified.

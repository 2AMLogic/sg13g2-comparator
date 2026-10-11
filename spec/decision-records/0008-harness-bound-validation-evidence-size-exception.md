# 0008: Evidence-size exception for harness check-bound validation code (issue #178)

- **Status**: proposed. **This record covers the evidence budget only, and
  the growth it covers is harness code, not evidence.** It ratifies no bound
  and relaxes no Target or Stretch number. It changes nothing in `spec/`
  target tables or in `README.md`'s target table. It authorizes one raise of
  the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  [#132](https://github.com/2AMLogic/sg13g2-comparator/issues/132)'s
  contract). The raise is exactly the measured overage of 5831 B. The record
  takes effect with the reviewed merge of the PR that lands it, as for
  DR-0005, DR-0006 and DR-0007. The drafting agent does not merge it. 0004
  is still reserved by the unmerged DR-0004 draft
  ([#166](https://github.com/2AMLogic/sg13g2-comparator/pull/166)) and 0007
  is taken by the merged DR-0007 (issue #177), so this record takes the next
  free number, 0008.
- **Date**: 2026-10-11
- **Decided by**: Doctor agent, PR
  [#182](https://github.com/2AMLogic/sg13g2-comparator/pull/182) for issue
  [#178](https://github.com/2AMLogic/sg13g2-comparator/issues/178).
  Reviewers judge the rationale as well as the numbers. The operator reviews
  the raise as a governance item at merge.
- **Related**:
  [`0007-repeated-measurement-harness-evidence-size-exception.md`](0007-repeated-measurement-harness-evidence-size-exception.md)
  (the previous `sim/` total raise; still stands),
  [`0006-offset-significance-evidence-size-exception.md`](0006-offset-significance-evidence-size-exception.md),
  [`0005-offset-n200-evidence-size-exception.md`](0005-offset-n200-evidence-size-exception.md)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #178 makes `harness.testbench.load()` reject malformed check bounds
when it loads a manifest. The rejected cases are non-finite or non-numeric
`min`/`max`/spread values (scalar and per-axis), `min > max`, and negative
spreads. Before this change they could crash grading after a simulation, or
a NaN bound could make a check pass without testing anything. The fix is
stdlib Python under `sim/harness/`. The budget counts every tracked blob
under `sim/`, so this code counts against the evidence ceiling even though
it is not evidence.

On `main` (67635dd9e, after DR-0007 merged), `sim/` measures 554547003 B
against a total ceiling of 554547003 B, so there are 0 B of headroom.
Measured with `git ls-tree -rl`, this change adds 5831 B to `sim/`:

| Path | Bytes added |
|---|---|
| `sim/harness/tests/test_testbench.py` (bound-rejection matrix, CLI negative control) | 3887 |
| `sim/harness/testbench.py` (load-time bound validation) | 1728 |
| `sim/harness/cli.py` (clean exit on an invalid manifest) | 150 |
| `sim/evidence-size-budget.json` (this exception entry) | 66 |
| **Total** | **5831** |

No new evidence unit is added, so only the total needs a raise.

## Decision

1. Raise the `sim/` total ceiling by exactly **5831 B**, the measured
   overage.
2. The checker rejects duplicate exception paths, so the single `sim` entry
   now carries the cumulative figure 15588102 + 5831 = **15593933 B** and
   cites this record. The 15571193 B (DR-0005), 14103 B (DR-0006) and
   2806 B (DR-0007) parts carry over unchanged. The only new allowance here
   is the 5831 B increment.

Trimming the change instead was tried first. The PR originally added
8079 B. Removing an unused test helper, duplicate mid-file imports and
verbose validation code brought it down to 5765 B of code. With 0 B of
headroom, though, any non-empty fix overflows the ceiling. The rest is the
fix itself and the tests that issue #178's acceptance criteria require.
Those tests cover every bound type for scalar and per-axis keys, `min > max`,
negative spreads, the CLI negative control, and loading of the shipped
manifests. `sim/` is append-only, so no existing evidence may be shrunk to
make room.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15593933}
```

(Cumulative: 15571193 B from DR-0005, 14103 B from DR-0006, 2806 B from
DR-0007 and 5831 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- This is an exact raise, not a standing allowance. Future growth needs its
  own record.
- No claim changes. Every ratified number stays the same, and no `sim/`
  evidence file is modified.

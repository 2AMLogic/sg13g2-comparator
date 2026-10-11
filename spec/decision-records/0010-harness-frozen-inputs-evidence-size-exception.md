# 0010: Evidence-size exception for harness frozen-input capture code (issue #179)

- **Status**: proposed. **This record covers the evidence budget only, and
  the growth it covers is harness code, not evidence.** It ratifies no bound
  and relaxes no Target or Stretch number. It changes nothing in `spec/`
  target tables or in `README.md`'s target table. It authorizes one raise of
  the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  [#132](https://github.com/2AMLogic/sg13g2-comparator/issues/132)'s
  contract). The raise is exactly the measured overage of 6513 B. The record
  takes effect with the reviewed merge of the PR that lands it, as for
  DR-0005 to DR-0009. The drafting agent does not merge it. 0004 is still
  reserved by the unmerged DR-0004 draft
  ([#166](https://github.com/2AMLogic/sg13g2-comparator/pull/166)), 0008 is
  taken by the merged DR-0008 (issue #178) and 0009 by the merged DR-0009
  (issue #181), so this record takes the next free number, 0010.
- **Date**: 2026-10-11
- **Decided by**: Builder agent, PR for issue
  [#179](https://github.com/2AMLogic/sg13g2-comparator/issues/179).
  Reviewers judge the rationale as well as the numbers. The operator reviews
  the raise as a governance item at merge.
- **Related**:
  [`0009-pex-delta-table-evidence-size-exception.md`](0009-pex-delta-table-evidence-size-exception.md)
  (the previous `sim/` total raise; still stands),
  [`0008-harness-bound-validation-evidence-size-exception.md`](0008-harness-bound-validation-evidence-size-exception.md)
  (earlier raise; still stands),
  [`0007-repeated-measurement-harness-evidence-size-exception.md`](0007-repeated-measurement-harness-evidence-size-exception.md),
  [`0006-offset-significance-evidence-size-exception.md`](0006-offset-significance-evidence-size-exception.md),
  [`0005-offset-n200-evidence-size-exception.md`](0005-offset-n200-evidence-size-exception.md)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #179 binds every point of a local PVT run, and the record it writes,
to one set of input bytes. `harness.dut.load()` and `harness.testbench.load()`
now read the DUT netlist, DUT config, testbench fragment and manifest once.
They validate and hash those bytes. The CLI writes private copies into the
reserved run directory before the grid starts, and every simulator include
and the internal-noise hook use those copies. Before this change, an edit to
a live file during a long grid could mix circuit revisions across points or
stamp the record with hashes of files that earlier points never used. The
fix is stdlib Python under `sim/harness/`. The budget counts every tracked
blob under `sim/`, so this code counts against the evidence ceiling even
though it is not evidence.

On `main` (76e0ec7eb, after DR-0009 merged), `sim/` measures exactly its
total ceiling of 554567449 B (538958901 B base plus 15608548 B of
exceptions), so there are 0 B of headroom. Measured with `git ls-tree -rl`
against that commit, this change adds 6513 B to `sim/`:

| Path | Bytes added |
|---|---|
| `sim/harness/tests/test_runner.py` (mid-grid mutation, unchanged run, capture-failure tests) | 5193 |
| `sim/harness/cli.py` (private input copies, abort on capture failure) | 830 |
| `sim/harness/dut.py` (capture netlist/config bytes once, `dut_config_sha256`) | 305 |
| `sim/harness/testbench.py` (capture fragment/manifest bytes once) | 115 |
| `sim/evidence-size-budget.json` (this exception entry) | 70 |
| **Total** | **6513** |

No new evidence unit is added, so only the total needs a raise. The private
input copies live in the run's scratch directory (`sim/.work/`, untracked)
and are deleted with it; the retained netlist snapshot keeps its existing
shape and size.

## Decision

1. Raise the `sim/` total ceiling by exactly **6513 B**, the measured
   overage.
2. The checker rejects duplicate exception paths, so the single `sim` entry
   now carries the cumulative figure 15608548 + 6513 = **15615061 B** and
   cites this record. The 15571193 B (DR-0005), 14103 B (DR-0006), 2806 B
   (DR-0007), 5831 B (DR-0008) and 14615 B (DR-0009) parts carry over unchanged. The only new
   allowance here is the 6513 B increment.

Trimming came first. The first working version added 7449 B. Shortening
comments and compacting the test fixtures brought it to 6443 B of code.
With 0 B of headroom, any non-empty fix overflows the ceiling. What remains
is the fix and the tests that issue #179's acceptance criteria ask for: a
synthetic mid-grid mutation of the live DUT, config, fragment and manifest;
an unchanged successful run; and a capture failure that aborts before the
simulator starts and leaves existing evidence untouched. `sim/` is
append-only, so no existing evidence may be shrunk to make room.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15615061}
```

(Cumulative: 15571193 B from DR-0005, 14103 B from DR-0006, 2806 B from
DR-0007, 5831 B from DR-0008, 14615 B from DR-0009 and 6513 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- This is an exact raise, not a standing allowance. Future growth needs its
  own record.
- No claim changes. Every ratified number stays the same, and no `sim/`
  evidence file is modified.

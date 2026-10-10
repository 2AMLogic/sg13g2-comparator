# 0006: Evidence-size exception for the klt-vs-record offset significance analysis (issue #82)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It changes
  nothing in `spec/` target tables or in `README.md`'s target table. It
  authorizes one raise of the `sim/` total ceiling in
  `sim/evidence-size-budget.json` (issue
  [#132](https://github.com/2AMLogic/sg13g2-comparator/issues/132)'s
  contract). The raise is exactly the measured overage of 14103 B, so one
  pure-analysis unit can be committed. The record takes effect with the
  reviewed merge of the PR that lands it. That merge commit is the record of
  acceptance, as for DR-0001 to DR-0003 and DR-0005. The drafting agent does
  not merge it. Number 0006 is used for two reasons. 0004 is reserved by
  the in-flight, unmerged DR-0004 draft
  ([#166](https://github.com/2AMLogic/sg13g2-comparator/pull/166)), and 0005
  is taken.
- **Date**: 2026-10-10
- **Decided by**: Doctor agent, PR for issue
  [#82](https://github.com/2AMLogic/sg13g2-comparator/issues/82). Reviewers
  judge the rationale below as well as the numbers. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0005-offset-n200-evidence-size-exception.md`](0005-offset-n200-evidence-size-exception.md)
  (the earlier `sim/` total raise of 15571193 B; it is unchanged and still
  stands),
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  (Row 1, unchanged)
- **Supersedes**: none. **Superseded by**: none

## Context

Issue #82 asks whether the +13 % shift between the `klt sim` offset_mc grid
mean and the in-process record is significant. The answer is a numpy-only
re-analysis of evidence that is already committed. It needs no SPICE run.
It adds `sim/klt-vs-record-offset-significance/` (`analyze.py`,
`analysis_output.txt`, `README.md`). It also appends a 13-line addendum to
`sim/klt-corner-verification/README.md`, and the existing notes in that
file are left unchanged.

On `main`, `sim/` measures 554530015 B against a total ceiling of
554530094 B (538958901 B plus DR-0005's 15571193 B). That leaves 79 B of
headroom. Measured with `git ls-tree -rl`, this change adds 14182 B to
`sim/`:

| Path | Bytes added |
|---|---|
| `sim/klt-vs-record-offset-significance/analyze.py` | 8624 |
| `sim/klt-vs-record-offset-significance/README.md` | 2975 |
| `sim/klt-vs-record-offset-significance/analysis_output.txt` | 1825 |
| `sim/klt-corner-verification/README.md` (append-only addendum) | 750 |
| `sim/evidence-size-budget.json` (this exception entry) | 8 |
| **Total** | **14182** |

That puts `sim/` at 554544197 B, which is over the ceiling by exactly
14103 B. No new evidence unit exceeds its own ceiling, so only the total
needs a raise.

## Decision

1. Raise the `sim/` total ceiling by exactly **14103 B**, the measured
   overage.
2. The checker rejects duplicate exception paths, and DR-0005 already holds
   the only `sim` entry. So the single `sim` entry in
   `sim/evidence-size-budget.json` now carries the cumulative figure
   15571193 + 14103 = **15585296 B**, and it now cites this record. The
   15571193 B part is DR-0005's authorization, and this record carries it
   over unchanged. The only new allowance here is the 14103 B increment.
   DR-0005's per-unit entry for
   `sim/klt-corner-verification/campaigns/20261010-n200` is not touched.

Reducing the unit instead was considered and rejected. Even a 0-byte
analysis unit would not fit: the 750 B addendum alone exceeds the 79 B of
headroom. Each committed file is needed:

- `analyze.py` is the reproduction.
- `analysis_output.txt` is the byte-checkable result that reviewers
  regenerate with `python3 -I analyze.py --out <file>`.
- `README.md` states the statistical basis (PVT grid, N = 60 per point,
  grid means rather than single-corner sigmas).

Trimming any of them would remove reproducibility or acceptance-criteria
content. `sim/` is append-only, so no existing evidence may be shrunk to
make room. The raise equals the measured overage exactly, so no further
growth is silently allowed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 15585296}
```

(Cumulative: 15571193 B from DR-0005 plus 14103 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- This is an exact raise, not a standing allowance. Future growth needs its
  own record, which updates the cumulative `sim` figure the same way.
- No claim changes. The 15 mV Row 1 bound and every ratified number stay
  untouched.

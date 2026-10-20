# 0033: Evidence-size exception for report-writer consolidation (issue #302)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 3300 B. It takes effect
  only with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0032. The drafting agent does not merge it, and drafting it is not agents
  relaxing the ratified spec.
- **Date**: 2026-10-19
- **Decided by**: Builder agent for issue #302, following the DR-0030
  pattern. The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0032-population-validation-evidence-size-exception.md`](0032-population-validation-evidence-size-exception.md)
  (previous `sim/` total raise, on main; still stands)
- **Supersedes**: none. **Superseded by**: none
- **Numbering**: this record chains its cumulative `sim` entry on DR-0032, the
  latest raise on main (renumbered from 0031 on rebase). Whichever open PR merges first keeps its number
  and cumulative figure; the others are renumbered on rebase with their
  cumulative `sim` entry re-measured. This record's own 3300 B does not change
  unless this PR's `sim/` diff changes.

## Context

Issue #302 routes the remaining hand-rolled report writers (`compare` in
`run_offset_cm_band.py` and `run_decision_cm_band.py`, and `kltsim ibsweep`)
through the shared append-only `artifacts.publish`, adding `--check` and
`--report-dir`. On main, `sim/` was 851 B under its ceiling, so the added
options, tests and README text need this exception. The growth is code, tests
and docs. No committed evidence file is modified and no report is regenerated.

| Path | Nature | Bytes |
|---|---|---|
| `sim/kltsim/cli.py`, `sim/kltsim/ibsweep.py`, `sim/run_offset_cm_band.py`, `sim/run_decision_cm_band.py` | publish through `artifacts.publish`, `--check`, `--report-dir` | net of removed `write_text` writers |
| `sim/kltsim/tests/test_report_preserve.py` | three more producers in the shared conflict / rerun / check matrix | |
| `sim/README.md` | "Derived report pairs" lists the new producers | |
| `sim/evidence-size-budget.json` | extended cumulative entry | +118 |

The total is the measured overage, 3182 B of code, tests and docs plus 118 B
of budget file = 3300 B. This record lives under `spec/` and adds nothing to
`sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **3300 B**. The single `sim` entry
carries the cumulative 28381771 + 3300 = **28385071 B** and cites this record.
The baseline, the 10 % allowance and all existing evidence are unchanged. No
ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28385071}
```

(Cumulative: 28381771 B from DR-0005 to DR-0032 and 3300 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance: the next `sim/` growth needs its own
  record.

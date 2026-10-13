# 0027: Evidence-size exception for yield index re-derivation check (issue #255)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 12773 B. It takes effect
  only with the reviewed merge of the PR that lands it, as for DR-0005 to
  DR-0026. The drafting agent does not merge it, and drafting it is not agents
  relaxing the ratified spec.
- **Date**: 2026-10-12
- **Decided by**: Builder agent for issue #255, following the DR-0026 pattern.
  The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0026-cm-band-empty-reproduction-evidence-size-exception.md`](0026-cm-band-empty-reproduction-evidence-size-exception.md)
  (previous `sim/` total raise; still stands)
- **Supersedes**: none. **Superseded by**: none
- **Numbering**: DR-0024 remains double-booked by open, unmerged PRs (#249,
  #243), as DR-0026 already records; whichever merges first keeps it and the
  other is renumbered on rebase with its cumulative `sim` entry re-measured.
  This record's own 12773 B does not change unless this PR's `sim/` diff
  changes.

## Context

Issue #255 extends the engine-free yield consistency check
(`sim/kltsim/yield_reports.py`) to re-derive the whole campaign index from the
validated source populations, the committed engine reports and the grader, so
a newly filed index cannot carry contradictory statistics while its samples
and report hashes stay intact:

- `check()` rebuilds the index with `build_index()` and diffs it against the
  saved one field by field (JSON paths); `index.md` is compared against
  `render_index_md` of the saved index and `index.json` against the canonical
  re-derivation.
- The `tool` block is read back as recorded provenance (only `--rerun`
  re-executes the engine), keeping superseded campaigns generated under an
  older pin re-derivable.

On main, `sim/` was exactly at its ceiling, so any addition needs this
exception. The growth is code, tests and documentation, not evidence. No
existing evidence file is modified and no report is regenerated:

| Path | Nature | Bytes |
|---|---|---|
| `sim/kltsim/yield_reports.py` | index re-derivation in `check()`, JSON-path diff helper, recorded-provenance reader | +4476 |
| `sim/kltsim/tests/test_yield_reports.py` | temp-copy index mutation tests (both campaigns) | +7148 |
| `sim/klt-yield/README.md` | Reproduce section: what engine-free `check` re-derives vs what only `--rerun` verifies | +992 |
| `sim/README.md` | harness cone table: the n200 preflight smoke envelope as a job input | +71 |
| `sim/evidence-size-budget.json` | extended cumulative entry | +86 |

The total is the measured overage, 12616 + 71 + 86 = 12773 B. This record lives
under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **12773 B**. The single `sim` entry
carries the cumulative 28215932 + 12773 = **28228705 B** and cites this
record. The baseline, the 10 % allowance and all existing evidence are
unchanged. No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28228705}
```

(Cumulative: 28215932 B from DR-0005 to DR-0026 and 12773 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance: the next `sim/` growth needs its own
  record.

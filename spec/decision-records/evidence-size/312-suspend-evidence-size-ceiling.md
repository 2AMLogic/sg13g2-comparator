# Evidence-size ceiling suspended (report-only) — issue #312

- **Status**: ratified by operator ruling, 2026-10-20 (rjwalters, attended `/fleet:decide`)
- **Scope**: `scripts/check_evidence_size.py`, `sim/evidence-size-budget.json`

## Decision

The `sim/` evidence-size ceiling is lifted until the fleet's common S3
artifact store lands (2AMLogic/2am#5553). Operator ruling: "on 276 itself I
think we should lift the cap while we set up the long term large sim storage
solution."

## Reason

Per-PR size exceptions have become a standing cost (the budget's cumulative
`sim` exception plus per-PR records) while the real fix, moving evidence to
the shared S3 store and committing only manifests and summaries, is a
fleet-level piece of work outside this repository.

## What changes

- `sim/evidence-size-budget.json` gains `"suspended": {"by": "operator",
  "date": "2026-10-20", "until": "2AMLogic/2am#5553"}`. The baseline, ceilings,
  unit sizes and exceptions are kept unchanged.
- While `suspended` is present, `scripts/check_evidence_size.py` still
  measures and prints the sizes and growth, and prints each ceiling breach as
  `would-fail (not enforced)`, but exits 0. The `append-only-evidence` CI job
  therefore passes on a size breach and its log states the measured size and
  that the ceiling is suspended.

## What does not change

- The append-only rule (`scripts/check_append_only_evidence.py`): modifying,
  deleting, moving or mode-changing an existing evidence unit still fails.
  Lifting the cap does not let committed evidence be rewritten.
- Measurement errors still exit 2 (partial clone, git failure, missing or
  non-numeric size), and an invalid budget file (including a malformed
  `suspended` block) still exits 1.
- Existing exceptions and their records stay valid.

## Restore condition

Restore when the 2am#5553 store is live and evidence is committed as
manifests and summaries. Restoring is a one-line change: delete the
`suspended` block from `sim/evidence-size-budget.json`. The ceiling then
returns, measured against manifests only (a re-baselined budget to be set by a
follow-up decision record at that time).

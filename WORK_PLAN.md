# Work plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#445**: make_delta_table.py cannot read the batch envelope shape (rows[] vs delta[]), the last gap before a 45-corner grid table renders
- **#447**: sizesweep finalist roll-up cannot report Row 5a, hiding a PASS->INCOMPLETE regression

## In Progress

Issues currently being built (`loom:building`).

- **#428**: Remove the repo-root package.json stub: its last script invokes a Loom script deleted in v0.19.1244
- **#440**: --check regeneration drift: six committed report pairs no longer reproduce byte-identically on main

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#448**: ibsweep: grade swept-bias campaigns against the declared BIAS_PROBES superset
- **#450**: chore: remove dead repo-root package.json stub

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#160**: Draft decision record: input common-mode range row for the ratified spec *(curated)*
- **#440**: --check regeneration drift: six committed report pairs no longer reproduce byte-identically on main *(curated)*
- **#445**: make_delta_table.py cannot read the batch envelope shape (rows[] vs delta[]), the last gap before a 45-corner grid table renders *(curated)*
- **#447**: sizesweep finalist roll-up cannot report Row 5a, hiding a PASS->INCOMPLETE regression *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#3**: Gap-to-T1 tracker: sg13g2-comparator artifact-presence survey

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 3 |
| Curated | 5 |
| Architect / Hermit proposals | 0 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

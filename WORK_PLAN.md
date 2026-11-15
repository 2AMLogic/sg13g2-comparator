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

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#428**: Remove the repo-root package.json stub: its last script invokes a Loom script deleted in v0.19.1244
- **#438**: Decide whether to chase the klayout-tools 0.9.2 pin (0.9.1 landed in #430 as the measured candidate)
- **#440**: --check regeneration drift: six committed report pairs no longer reproduce byte-identically on main

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#448**: ibsweep: grade swept-bias campaigns against the declared BIAS_PROBES superset
- **#450**: chore: remove dead repo-root package.json stub

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#449**: pin: move klayout-tools 0.9.1 -> 0.9.2, re-freeze layout evidence

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#160**: Draft decision record: input common-mode range row for the ratified spec *(curated)*
- **#438**: Decide whether to chase the klayout-tools 0.9.2 pin (0.9.1 landed in #430 as the measured candidate) *(curated)*
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
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 2 |
| Approved PRs awaiting merge | 2 |
| Curated | 6 |
| Architect / Hermit proposals | 0 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

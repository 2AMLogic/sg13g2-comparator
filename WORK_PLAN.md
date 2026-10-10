# Work plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Operator Priority

Issues the operator starred (`loom:operator-priority`); land these first.

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7)

## In Progress

Issues currently being built (`loom:building`).

- **#63**: Monte Carlo: mint a klt yield report for the statistical spec rows (offset sigma) and cite it (T1 item 6)
- **#117**: Unit tests for the CI-gating scripts: signoff parity, ERC judge, netlist generator

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#63**: Monte Carlo: mint a klt yield report for the statistical spec rows (offset sigma) and cite it (T1 item 6) *(curated)*
- **#65**: Cite artifact-anchored evidence for T1 items 1, 9 and 10 (design sources, testbenches, repo hygiene) *(curated)*

## Proposed (Architect / Hermit)

- **#142**: Capture verified Git provenance before PVT simulation *(architect)*

## Epics

- **#3**: Gap-to-T1 tracker: sg13g2-comparator artifact-presence survey

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Operator priority | 0 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 0 |
| Curated | 3 |
| Architect / Hermit proposals | 1 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

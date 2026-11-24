# Work plan

<!-- guide:plan-body:start -->
_Generated: 2026-11-23T10:45:00Z (snapshot; compare against live labels)_
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

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#476**: Draft the decision record on adopting the 8 µm input pair for Row 4a kickback
- **#487**: test_item5_spec_rows: pinned-klt skip guard uses a substring match, so a 0.9.2.dev build passes as the pin
- **#497**: Measure the integration-node capacitance tradeoff between Row 2 noise and Row 3c delay

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified) — closes #160
- **#492**: fix: require exact klt version match to run item 5 spec-row tests — closes #487

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#160**: Draft decision record: input common-mode range row for the ratified spec *(curated)*
- **#470**: Merge queue: add the merge_group trigger and adapt the PR-metadata gates *(curated)* *(held)*
- **#476**: Draft the decision record on adopting the 8 µm input pair for Row 4a kickback *(curated)*
- **#487**: test_item5_spec_rows: pinned-klt skip guard uses a substring match, so a 0.9.2.dev build passes as the pin *(curated)*
- **#497**: Measure the integration-node capacitance tradeoff between Row 2 noise and Row 3c delay *(curated)*

## Proposed (Architect / Hermit)

- **#546**: Consolidate nine derived-report publish epilogues onto cli.publish_report_pair *(hermit)*

## Epics

- **#3**: Gap-to-T1 tracker: sg13g2-comparator artifact-presence survey *(held)*

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 2 |
| Curated | 6 |
| Architect / Hermit proposals | 1 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

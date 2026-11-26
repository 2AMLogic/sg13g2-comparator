# Work plan

<!-- guide:plan-body:start -->
_Generated: 2026-11-26T10:52:47Z (snapshot; compare against live labels)_
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs with an active hold (`loom:blocked` or `loom:operator`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#490**: spec: draft DR-0033 input-pair kickback adoption record (unratified, held for operator)

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7)

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

- **#479**: Row 2 noise, Phase 2: compare integration-node capacitance and PMOS load sizing against the 8 µm baseline

## In Progress

Issues currently being built (`loom:building`).

- **#476**: Draft the decision record on adopting the 8 µm input pair for Row 4a kickback
- **#552**: Measure strobe-qualified kickback residue at the two DR-0004 cold edge corners

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#554**: sim: measure strobe-qualified kickback residue at the DR-0004 cold edges *(held)*

## Approved (Awaiting Merge)

PRs that passed Judge review (`loom:pr`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#490**: spec: draft DR-0033 input-pair kickback adoption record (unratified, held for operator)

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#160**: Draft decision record: input common-mode range row for the ratified spec *(curated)*
- **#470**: Merge queue: add the merge_group trigger and adapt the PR-metadata gates *(curated)* *(held)*
- **#476**: Draft the decision record on adopting the 8 µm input pair for Row 4a kickback *(curated)*
- **#552**: Measure strobe-qualified kickback residue at the two DR-0004 cold edge corners *(curated)*
- **#556**: Collect and publish the four corrected cold-edge fleet results for PR #554 *(curated)* *(held)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#3**: Gap-to-T1 tracker: sg13g2-comparator artifact-presence survey *(held)*

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 2 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 2 |
| Curated | 6 |
| Architect / Hermit proposals | 0 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

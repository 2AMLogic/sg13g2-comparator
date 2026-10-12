# Work plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

- **#199**: PEX diagnostic: extracted-device-only leg to separate device geometry from routing RC
- **#200**: noise-full: label grid-mean uncertainty, add correlated bound and shared-draw disclosure (#192)
- **#212**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (#165)

## Operator Priority

Issues the operator starred (`loom:operator-priority`); land these first.

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#89**: sim: complete the two vcm-m050 CM-band offset points that abort (timestep too small) with a uniform tighter max step
- **#159**: Memory / hysteresis characterization bench: does the previous decision bias the next?

## In Progress

Issues currently being built (`loom:building`).

- **#235**: Validate clock-supply probes and reject ambiguous sample identities
- **#237**: Preserve derived campaign report pairs before regeneration

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#199**: PEX diagnostic: extracted-device-only leg to separate device geometry from routing RC
- **#200**: noise-full: label grid-mean uncertainty, add correlated bound and shared-draw disclosure (#192)
- **#212**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (#165)
- **#243**: Preserve derived campaign report pairs before regeneration (#237)

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#89**: sim: complete the two vcm-m050 CM-band offset points that abort (timestep too small) with a uniform tighter max step *(curated)*
- **#159**: Memory / hysteresis characterization bench: does the previous decision bias the next? *(curated)*
- **#160**: Draft decision record: input common-mode range row for the ratified spec *(curated)*
- **#165**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (evidence for DR-0004 CM-range row) *(curated)*
- **#191**: PEX diagnostic: separate extracted device geometry from routing RC delay *(curated)*
- **#235**: Validate clock-supply probes and reject ambiguous sample identities *(curated)*
- **#237**: Preserve derived campaign report pairs before regeneration *(curated)*
- **#242**: Verify public noise compliance verdict statements *(curated)*

## Proposed (Architect / Hermit)

- **#242**: Verify public noise compliance verdict statements *(architect)*

## Epics

- **#3**: Gap-to-T1 tracker: sg13g2-comparator artifact-presence survey

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 3 |
| Operator priority | 0 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 5 |
| Curated | 9 |
| Architect / Hermit proposals | 1 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

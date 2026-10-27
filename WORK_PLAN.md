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

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#89**: sim: complete the two vcm-m050 CM-band offset points that abort (timestep too small) with a uniform tighter max step
- **#159**: Memory / hysteresis characterization bench: does the previous decision bias the next?
- **#160**: Draft decision record: input common-mode range row for the ratified spec
- **#165**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (evidence for DR-0004 CM-range row)
- **#191**: PEX diagnostic: separate extracted device geometry from routing RC delay
- **#308**: Remove dead _spec_meas left behind by closed #295

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#171**: sim: memory/hysteresis characterization bench (paired-history switching boundary over PVT) (Closes #159)

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#199**: PEX diagnostic: extracted-device-only leg to separate device geometry from routing RC
- **#218**: sim: max-step supplement workflow for aborted CM-band offset points (#89, partial: batch run failed)

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#89**: sim: complete the two vcm-m050 CM-band offset points that abort (timestep too small) with a uniform tighter max step *(curated)*
- **#92**: Joint input-pair sizing study to close the failing Target rows (Row 4 Q_kick, Row 2 noise) *(curated)*
- **#159**: Memory / hysteresis characterization bench: does the previous decision bias the next? *(curated)*
- **#160**: Draft decision record: input common-mode range row for the ratified spec *(curated)*
- **#165**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (evidence for DR-0004 CM-range row) *(curated)*
- **#191**: PEX diagnostic: separate extracted device geometry from routing RC delay *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#3**: Gap-to-T1 tracker: sg13g2-comparator artifact-presence survey

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 0 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 6 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 3 |
| Curated | 7 |
| Architect / Hermit proposals | 0 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

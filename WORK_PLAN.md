# Work plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#199**: PEX diagnostic: extracted-device-only leg to separate device geometry from routing RC
- **#212**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (#165)
- **#265**: Validate timestep smoke evidence before computing noise convergence (#263)
- **#276**: Mirror gf180's supplemental reverse-polarity ladder fragment (#274)
- **#281**: feat: read per-PR evidence-size exception files so open PRs stop conflicting

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#278**: Every evidence PR rewrites the same total-ceiling line in sim/evidence-size-budget.json

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#89**: sim: complete the two vcm-m050 CM-band offset points that abort (timestep too small) with a uniform tighter max step
- **#159**: Memory / hysteresis characterization bench: does the previous decision bias the next?
- **#235**: Validate clock-supply probes and reject ambiguous sample identities
- **#245**: Validate actual Monte Carlo populations before compliance grading
- **#247**: Derive evidence-size estimate denominators from selected reference campaigns
- **#264**: Reject invalid local PVT grid inputs before simulation
- **#266**: Validate CM decision timing dimensions and physical domains

## In Progress

Issues currently being built (`loom:building`).

- **#92**: Joint input-pair sizing study to close the failing Target rows (Row 4 Q_kick, Row 2 noise)
- **#278**: Every evidence PR rewrites the same total-ceiling line in sim/evidence-size-budget.json

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#166**: spec: draft DR-0004 input common-mode range row (evidence-gated, unratified)
- **#199**: PEX diagnostic: extracted-device-only leg to separate device geometry from routing RC
- **#212**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (#165)
- **#265**: Validate timestep smoke evidence before computing noise convergence (#263)
- **#276**: Mirror gf180's supplemental reverse-polarity ladder fragment (#274)
- **#281**: feat: read per-PR evidence-size exception files so open PRs stop conflicting

## Proposed

Issues carrying `loom:curated`.

- **#61**: Post-layout: klt pex extraction and spec re-run on the extracted netlist (T1 item 7) *(curated)*
- **#89**: sim: complete the two vcm-m050 CM-band offset points that abort (timestep too small) with a uniform tighter max step *(curated)*
- **#92**: Joint input-pair sizing study to close the failing Target rows (Row 4 Q_kick, Row 2 noise) *(curated)*
- **#159**: Memory / hysteresis characterization bench: does the previous decision bias the next? *(curated)*
- **#160**: Draft decision record: input common-mode range row for the ratified spec *(curated)*
- **#165**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (evidence for DR-0004 CM-range row) *(curated)*
- **#191**: PEX diagnostic: separate extracted device geometry from routing RC delay *(curated)*
- **#235**: Validate clock-supply probes and reject ambiguous sample identities *(curated)*
- **#245**: Validate actual Monte Carlo populations before compliance grading *(curated)*
- **#247**: Derive evidence-size estimate denominators from selected reference campaigns *(curated)*
- **#263**: Validate timestep smoke evidence before computing noise convergence *(curated)*
- **#264**: Reject invalid local PVT grid inputs before simulation *(curated)*
- **#266**: Validate CM decision timing dimensions and physical domains *(curated)*
- **#274**: Mirror gf180's supplemental reverse-polarity ladder fragment (bench-structure parity, gf180-comparator#158/#166) *(curated)*
- **#278**: Every evidence PR rewrites the same total-ceiling line in sim/evidence-size-budget.json *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#3**: Gap-to-T1 tracker: sg13g2-comparator artifact-presence survey

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 6 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 7 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 6 |
| Curated | 15 |
| Architect / Hermit proposals | 0 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

# 0033: Adopt the 8 µm / 0.34 µm input pair for Row 4a kickback — proposed, unratified

- **Status**: proposed, **unratified**. This record ratifies nothing, relaxes
  nothing and edits no row of `README.md`'s ratified table. It proposes that
  the comparator's input pair `XM1`/`XM2` move from the committed
  `w=12u l=0.34u` to `w=8u l=0.34u` (geometry override `XM1.w=8u XM2.w=8u`,
  everything else — including the 20 µA tail-bias reference `dut_ib` and
  `dut_vcm = 0.6 V` in [`sim/dut.json`](../../sim/dut.json) — unchanged),
  because the measured candidate closes the Row 4a kickback Target that the
  committed pair fails. Adoption was expressly reserved to a separate
  decision record by the operator's 2026-10-15 ruling on
  [#92](https://github.com/2AMLogic/sg13g2-comparator/issues/92) ("Adoption
  and changes to ratified bounds or DR-0001 require a separate decision
  record"); this is that record. The ratification act is the two-key merge
  of the PR that lands it, exactly as
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  "How this record gets ratified" describes, and the PR is additionally
  **held for the operator** on the open question below, per the precedent of
  held PR
  [#166](https://github.com/2AMLogic/sg13g2-comparator/pull/166). **The
  drafting agent holds neither key, this PR must not be hand-merged, and
  until it is ratified no file under `design/`, `layout/`, `sim/` or
  `manifests/` changes** — the build is
  [#481](https://github.com/2AMLogic/sg13g2-comparator/issues/481), parked
  pending exactly this record.
- **Date**: 2026-11-21
- **Decided by**: Builder agent, issue
  [#476](https://github.com/2AMLogic/sg13g2-comparator/issues/476),
  drafting only. The adoption decision itself is the operator's (see "The
  question this record puts to the operator").
- **Related**:
  [`0001-comparator-topology.md`](0001-comparator-topology.md) (the
  DR-0001 topology this sizes; unchanged by this record),
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  (every Target and Stretch cited below is its ratified bound, unchanged),
  [`0003-evidence-state-update-rows-1-4-5.md`](0003-evidence-state-update-rows-1-4-5.md)
  (the baseline Row 4a NOT MET finding this proposal answers),
  [#92](https://github.com/2AMLogic/sg13g2-comparator/issues/92) /
  PR [#121](https://github.com/2AMLogic/sg13g2-comparator/pull/121) (the
  sizing study and its operator ruling) /
  PR [#446](https://github.com/2AMLogic/sg13g2-comparator/pull/446) (the
  bias/latch study),
  [#3](https://github.com/2AMLogic/sg13g2-comparator/issues/3) (gap-to-T1
  tracker),
  [#477](https://github.com/2AMLogic/sg13g2-comparator/issues/477),
  [#479](https://github.com/2AMLogic/sg13g2-comparator/issues/479),
  [#480](https://github.com/2AMLogic/sg13g2-comparator/issues/480) (the
  Row 2 noise workstream),
  [#481](https://github.com/2AMLogic/sg13g2-comparator/issues/481) (the
  parked implementation),
  [#61](https://github.com/2AMLogic/sg13g2-comparator/issues/61) (post-layout
  verification whose evidence the layout hash ties down),
  [#447](https://github.com/2AMLogic/sg13g2-comparator/issues/447) (why
  Row 5a is cited from the per-candidate grade, not the sizesweep roll-up)
- **Supersedes**: none. No earlier record is edited or overridden; every
  DR-0002 bound stays exactly as ratified.
- **Superseded by**: none

## Context

DR-0003 recorded the baseline's Row 4a state: direct Q_kick measurement on
the committed 12 µm pair reads **23.58 … 31.46 fC per side** across the
45-point PVT grid, binding at `ff_125c_1.32v` (31.46 fC), so **39 of 45
corners exceed the ratified ≤ 25 fC/side Target** (and 45/45 exceed the
8 fC Stretch). That miss is T1 item 5's `sim__corner__failed_count = 39`
blocker and one of item 8's two blocking rows.

Two measured studies exist on top of that baseline, and neither was adopted:

1. **Geometry sweep** (#92 / PR #121, campaign
   [`20261009-issue92`](../../sim/klt-corner-verification/campaigns/20261009-issue92/sizesweep.md)):
   a 9-candidate screen on a reduced 18-point grid (tt/ff/ss × 1.08/1.32 V ×
   −40/27/125 °C, deterministic, mismatch off — **not a 45-point verdict**),
   then three finalists on the full 45-point grid with Monte-Carlo Rows 1 and
   2 (N = 60 per point, N = 80 per rung, seeds committed in each request).
   The finalist `w8_l034` met every bounded Target row it reports except
   Row 2.
2. **Bias/latch study** (#92 / PR #446, campaigns
   [`20261115-issue92-bias`](../../sim/klt-corner-verification/campaigns/20261115-issue92-bias/sizesweep-final.md)
   and the stored MC evidence
   [`20261115-issue92-bias-mc.md`](../../sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc.md)):
   three finalists on the 8 µm base at lower bias / larger latch devices.
   All three keep Row 4a inside its Target; none closes Row 2; each has at
   least one aborted mismatch draw leaving Row 1 incomplete (1, 2 and 1
   affected points respectively; see the finalist paragraph below).

The operator's 2026-10-15 ruling on #92 chose the further-study option and
left adoption open. `ROADMAP.md` still lists "Adopt a resized input pair"
under *Later*, gated on exactly the question below.

Every number in this record was re-read from the cited committed artifact,
not copied from the issue text.

## The question this record puts to the operator

**Adopt the 8 µm / 0.34 µm input pair at the existing 20 µA bias now, for
kickback alone, while Row 2 (input-referred noise) remains open — or keep
the 12 µm pair until the Row 2 direction (#477 → #479 → #480) lands?**

None of the candidates tested so far closes Row 2: the 8 µm pair and the
three bias/latch finalists all miss it. That does not rule out every
option within the DR-0001 topology, for example the integration-node
capacitance option that #479 still plans to investigate. Adopting now is
therefore deliberately adopting a design that still fails one ratified
Target row. That trade is the operator's to make; this
record only frames it with the measured evidence and both costs.

## The measured evidence

Baseline grade: campaign
[`20261009-d73a9ac/grading.md`](../../sim/klt-corner-verification/campaigns/20261009-d73a9ac/grading.md)
(committed 12 µm pair). Candidate grade: campaign
[`20261009-issue92/full_w8_l034/grading.md`](../../sim/klt-corner-verification/campaigns/20261009-issue92/full_w8_l034/grading.md)
(exactly the override `XM1.w=8u XM2.w=8u` applied to it; `l` stays 0.34 µm).
Both are full 45-point `klt sim` grids, graded by `kltsim.grade` against the
DR-0002 bounds.

| Row (DR-0002 bound, unchanged) | Baseline, 12 µm pair | Candidate, 8 µm pair (`full_w8_l034`) |
|---|---|---|
| 4a Q_kick, Target ≤ 25 fC/side | **FAIL** — 23.58 … 31.46 fC, binding `ff_125c_1.32v` (31.46); **39/45 corners over** (envelope 6 pass / 39 fail / 0 error) | **PASS** — 15.65 … 21.2 fC, same binding corner (21.2); **45/45 under** (envelope 45 pass / 0 fail / 0 error). Margin 3.8 fC at the binding corner. Stretch ≤ 8 fC still FAIL both. |
| 1 offset 3σ, Target ≤ 15 mV (MC N = 60/point, shipped mismatch models) | PASS — 6.913 … 12.09 mV, binding `ff_125c_1.08v` | **PASS but thinner** — 8.955 … 13.93 mV, binding moves to `tt_125c_1.08v`; **45/45 points valid**, 1.07 mV under the Target. Stretch ≤ 8 mV FAIL both. |
| 2 noise, Target ≤ 1 mV rms grid mean (probit, N = 80/rung) | FAIL — grid mean 1.289 mV rms (same injected 36.27 nV/√Hz density, `vn_na=5.735e-3`, `vn_ts=2e-11`) | **FAIL, slightly worse** — grid mean 1.338 mV rms at the same injected 36.27 nV/√Hz density (`vn_na=5.735e-3`, `vn_ts=2e-11` in both committed bodies; worst point `ff_125c_1.08v`, 1.764). The grade's shared-draw caveat (1669/3600 samples repeat a raw draw at another grid point) applies as documented. |
| 3a / 3b / 3c decision time, τ, 0.1 mV overdrive | PASS | PASS — 0.8664 ns / 168.7 ps / 1.705 ns worst (`ss_125c_1.32v`, `ss_-40c_1.08v`, `ss_-40c_1.08v`); all 45/45 valid |
| 4b residue, Target ≤ 100 µV | PASS | PASS — worst 10.29 µV (`ss_-40c_1.20v`), 45/45 valid |
| 4c input excursion (reporting only, unbounded) | 87.66 … 143.3 mV | 62.74 … 96.03 mV (improved) |
| 5a PVT coverage | PASS | **PASS** — regeneration, kickback, offset_mc and transient_noise all exercised over the full grid, per the candidate's own grade (the sizesweep roll-up cannot report Row 5a; #447) |
| 5b average power, Stretch ≤ 20 µW (no Target) | FAIL — worst 38.78 µW | FAIL — worst 37.61 µW (unchanged in meaning) |

**Why this candidate and not the others.** Of the three 45-point geometry
finalists, `w8_l034` is the only one that keeps Row 1 passing:
`w6_l034` fails Row 1 outright (worst 15.79 mV at `ff_125c_1.08v`, 9 of 45
points over the Target, 45/45 valid) and `w8_l020` fails it worse (worst
17.98 mV at `sf_27c_1.32v`, 19 points over, 44/45 valid). The bias/latch
finalists — `ib10_sw20`, `ib10_sw20lat6`, `ib12p5_sw20` — cannot be
proposed now because each has aborted mismatch draws
(`timestep_too_small` → `analysis_aborted` at a fixed committed seed), so
Row 1 is **INCOMPLETE** on all three (44/45, 43/45 and 44/45 valid points,
i.e. 1, 2 and 1 points with 59 usable draws and one error each, per
`.rows[0].target.points_missing_or_invalid` in each candidate's
`grading.json`: `ib10_sw20` at `sf_125c_1.08v`; `ib10_sw20lat6` at
`ff_-40c_1.20v` and `sf_27c_1.32v`; `ib12p5_sw20` at `sf_27c_1.32v`;
worst valid 13.69 / 13.37 / 13.78 mV), and none closes Row 2 either
(1.192 / 1.096 / 1.255 mV rms, all FAIL). Proposing one of them would first
require re-running every errored unit (two for `ib10_sw20lat6`) with the
recorded seeds and showing the incomplete rows complete.

The 18-point screen numbers (e.g. `w8_l020` at 15.1 fC, `w6_l034` at
15.97 fC at the binding corner) are screening only, mismatch off, and carry
no Row 1/2 verdict; no number above rests on them.

## Cost of each answer

**Adopt now (ratify this record).**

- Row 4a's Target is met at 45/45 on schematic evidence; T1 item 5 loses its
  `sim__corner__failed_count = 39` Row 4a blocker. Item 5 still grades
  `unmet` while Row 2 fails, and item 8 stays blocked on Row 2 — adopting
  does not unblock T1 by itself.
- Row 1 margin thins from 2.91 mV to **1.07 mV** under the 15 mV Target, and
  Row 2's grid mean worsens 1.289 → 1.338 mV rms against the unchanged
  1.0 mV Target. Both are grid means measured with the same injected
  36.27 nV/√Hz density, so the change does not reflect the resized pair's
  own front-end noise density, which #477 investigates. Both bounds stay as
  ratified.
- The GDS hash changes. #61's extracted evidence is tied to the current
  layout hash: its remaining extracted PVT and Monte-Carlo grids are
  superseded and must re-run on the adopted layout (earlier records stay
  committed, marked superseded — append-only evidence is not deleted).
  #481 then owns: schematic + netlist regeneration, layout regeneration,
  DRC/LVS/ERC/PEX re-run, a fresh 45-point campaign on Rows 1–5, a new
  N = 200 offset population and `klt yield` report (the cited
  [`20261010-n200`](../../sim/klt-yield/campaigns/20261010-n200/index.md)
  population was measured on the 12 µm pair), a re-minted characterization
  report, and the manifest repins.
- If the Row 2 direction (#477 → #479 → #480) later re-opens DR-0001 — a
  topology change — the regenerated layout, grids, yield and
  characterization are redone again. That is the risk of adopting before
  the noise question is settled.

**Wait (defer; keep the 12 µm pair).**

- The 39 failing Row 4a corners stay as they are; item 5 keeps
  `sim__corner__failed_count = 39` and item 8 stays blocked, on Row 4a and
  Row 2 alike.
- No layout churn: #61's extracted evidence stays valid, and no
  layout/DRC/LVS/yield/characterization work is spent on a geometry that a
  later noise decision might change.
- The Row 2 workstream (#477, very-important and open, then #479, #480) may
  deliver a direction that changes the input pair anyway, or re-opens the
  topology — the bias/latch finalists measured on the 8 µm base remain
  available if it instead confirms this sizing.

A decision to defer keeps #481 parked.

## What this record does not do

It changes no Target, Stretch or spec row; `README.md` is untouched. It
changes no file under `design/`, `layout/`, `sim/` or `manifests/` — the
earlier campaigns and reports it cites stay unedited (append-only). It does
not decide the Row 2 question, relax any bound to make results pass, or
start any Phase B work: #481's own gate is a merged record that explicitly
authorizes adoption, and it stays parked until this record is ratified.

## How this record gets ratified

Per [`spec/README.md`](../README.md) and DR-0002: ratification is the
**two-key merge** of the PR landing this record — an EE-key review and a
market-key review, neither held by the author, posted with their
`RATIFY-KEY:` markers — and **the merge commit is the ratification record**.
The drafting agent holds neither key and must not hand-merge. Because the
adoption question is the operator's (reserved by the 2026-10-15 ruling on
#92), the PR is additionally **held for the operator** on the question
above, on the precedent of held PR #166: merging ratifies adoption and
unparks #481; a decision to defer closes this PR unmerged and leaves the
12 µm pair, and #481, in place.

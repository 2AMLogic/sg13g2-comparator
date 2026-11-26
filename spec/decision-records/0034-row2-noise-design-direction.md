# 0034: Row 2 noise — design direction after the Phase 1 / Phase 2 study: keep DR-0001, no measured candidate closes Row 2 — proposed, unratified

- **Status**: proposed, **unratified**. This record ratifies nothing,
  relaxes nothing and edits no row of `README.md`'s ratified table. It is
  the Phase 3, drafting-only record that
  [#477](https://github.com/2AMLogic/sg13g2-comparator/issues/477) split
  out: it proposes the design direction for Row 2 (input-referred noise)
  that the Phase 1 report (PR
  [#494](https://github.com/2AMLogic/sg13g2-comparator/pull/494)) and the
  Phase 2 comparison (PR
  [#569](https://github.com/2AMLogic/sg13g2-comparator/pull/569)) support,
  and it puts one measurement-method question to the ratifier. **No measured
  candidate closes Row 2.** The ratification act is the two-key merge of the
  PR that lands it, per [`spec/README.md`](../README.md) and
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  ("How this record gets ratified"). **The drafting agent holds neither key
  and this PR must not be hand-merged.** The record changes no file under
  `design/`, `layout/`, `sim/` or `manifests/`, and it authorizes no change
  to any of them: every measurement or build it names is follow-on work
  under its own issue.
- **Date**: 2026-11-26
- **Decided by**: Builder agent, issue
  [#480](https://github.com/2AMLogic/sg13g2-comparator/issues/480),
  drafting only. The direction is decided at ratification.
- **Related**:
  [`0001-comparator-topology.md`](0001-comparator-topology.md) ("DR-0001",
  the topology this record proposes to keep; its "Alternatives considered"
  and "Open items" name the two escalation paths discussed below),
  [`0002-target-spec-ratification.md`](0002-target-spec-ratification.md)
  ("DR-0002": every Target and Stretch quoted below is its ratified bound,
  unchanged),
  [`0003-evidence-state-update-rows-1-4-5.md`](0003-evidence-state-update-rows-1-4-5.md)
  (the Row 4a NOT MET finding the DR-0033 draft answers),
  [#3](https://github.com/2AMLogic/sg13g2-comparator/issues/3) (gap-to-T1
  tracker, waiting on this workstream),
  [#92](https://github.com/2AMLogic/sg13g2-comparator/issues/92) and its
  2026-10-15 operator ruling (the study this record closes out, and the two
  options that ruling left open),
  [#477](https://github.com/2AMLogic/sg13g2-comparator/issues/477) / PR
  [#494](https://github.com/2AMLogic/sg13g2-comparator/pull/494) (Phase 1),
  [#479](https://github.com/2AMLogic/sg13g2-comparator/issues/479) / PRs
  [#504](https://github.com/2AMLogic/sg13g2-comparator/pull/504),
  [#501](https://github.com/2AMLogic/sg13g2-comparator/pull/501),
  [#569](https://github.com/2AMLogic/sg13g2-comparator/pull/569) (Phase 2:
  [#497](https://github.com/2AMLogic/sg13g2-comparator/issues/497) and
  [#498](https://github.com/2AMLogic/sg13g2-comparator/issues/498)),
  [#81](https://github.com/2AMLogic/sg13g2-comparator/issues/81) (the
  front-end / internal noise split, cited and not re-run),
  [#476](https://github.com/2AMLogic/sg13g2-comparator/issues/476) / PR
  [#490](https://github.com/2AMLogic/sg13g2-comparator/pull/490) (the
  DR-0033 draft this record must compose with) and
  [#481](https://github.com/2AMLogic/sg13g2-comparator/issues/481) (its
  parked implementation),
  [klayout-tools#2963](https://github.com/2AMLogic/klayout-tools/issues/2963)
  and
  [klayout-tools#5772](https://github.com/2AMLogic/klayout-tools/issues/5772)
  (the transient-noise seed limitation every Row 2 figure carries)
- **Supersedes**: none. DR-0001 is not superseded; this record proposes
  keeping it, and no earlier record is edited.
- **Superseded by**: none

## Context

Row 2 has failed on every design measured against the ratified Target since
DR-0002 set it: 1.335 mV rms on DR-0002's own compliance record, 1.289 mV rms
on the committed 12 µm / 0.34 µm design's 45-point grade
([`20261009-d73a9ac`](../../sim/klt-corner-verification/campaigns/20261009-d73a9ac/grading.md)),
and 1.096 mV rms at best in the #92 bias / latch study. All three are
45-point grid means at the bench's injected 36.27 nV/√Hz.

The operator's 2026-10-15 ruling on #92 authorized "a bounded
bias/latch-device study within the existing topology and 1.0 mV noise
target" and directed "Preserve the measured input-pair result and do not
adopt relaxed targets". It left the other two options put to it, re-open
DR-0001 and relax Row 2, unruled. That study is now complete in two phases,
and this is the drafting-only decision record it was run for.

Three findings shape the answer:

- **The Row 2 bench cannot see a design's own noise.** Phase 1 showed it
  injects one fixed density at every PVT point, so cross-design differences
  in its numbers are differences in effective decision bandwidth, not in
  front-end noise.
- **Phase 2 did not study the two topology alternatives.** Its candidates
  were the integration-node capacitance #477 expected and a load-width
  family added from Phase 1's per-device finding. Both stay inside the
  DR-0001 topology.
- **The best measured candidate sits close to the Target, on either side of
  it depending on the density used.** `w10` measures 0.04143 mV rms over the
  Target at the unchanged bench and projects to 0.96930 mV rms at its own TT
  density. The projection is not a measurement.

Every value below was re-read from the committed artifact while drafting
this record, not copied from issue text. Nothing was simulated for it.

## The evidence this record rests on

All of it is merged on `main` at `249e2e198`. The Phase 2 comparison states
that its values were copied from evidence on `main` at `a720d8b4a`.

| Phase | What it measured | Committed report | Merged |
|---|---|---|---|
| 1 | Per-corner front-end density with per-device power shares, effective decision bandwidth, Row 2 as density × bandwidth, and a nominal recalibration of the six #92 finalists | [`pvt-batch.md`](../../sim/comparator-preamp-noise/reports/20261120-issue477/pvt-batch.md), stored evidence [`20261121-issue477-pvt.md`](../../sim/comparator-preamp-noise/reports/20261121-issue477-pvt.md) | PR #494, `ce3bd3f9ac65` |
| 2, capacitance | Integration-node capacitance screen, 1, 2 and 4 fF per side | [`capacitance-r2.md`](../../sim/klt-corner-verification/campaigns/20261121-issue497/capacitance-r2.md), [dated analysis](../../sim/comparator-integration-capacitance/reports/20261121-issue497.md) | PR #504, `6e33080ac369` |
| 2, load width | Matched PMOS load-width screen and the `w10` finalist, with four-point densities | [`loadwidth-final.md`](../../sim/klt-corner-verification/campaigns/20261121-issue498/loadwidth-final.md), [`sizesweep-final.md`](../../sim/klt-corner-verification/campaigns/20261121-issue498/sizesweep-final.md), [`density.json`](../../sim/comparator-preamp-noise/reports/20261121-issue498/density.json) | PR #501, `28c5d18582dd` |
| 2, combined | Both families and the finalist against the 8 µm baseline | [`20261126-issue479-comparison.md`](../../sim/klt-corner-verification/campaigns/20261126-issue479-comparison.md) | PR #569, `249e2e1980b0` |

The full-grid verdicts come from three 45-point grades, each produced by
`sim/kltsim/grade.py` against the DR-0002 bounds copied in
[`rows.json`](../../sim/klt-corner-verification/rows.json): the 8 µm
baseline ([`full_w8_l034`](../../sim/klt-corner-verification/campaigns/20261009-issue92/full_w8_l034/grading.md)),
`w10`
([`full_w10`](../../sim/klt-corner-verification/campaigns/20261121-issue498/full_w10/grading.md))
and the screening control
([`full_ib10_sw20lat6`](../../sim/klt-corner-verification/campaigns/20261115-issue92-bias/full_ib10_sw20lat6/grading.md)).

Phase 2 keeps three designs distinct, and so does this record:

| Role | Name | Input pair XM1/XM2 | Latch devices | Switch XMSW | Bias `dut_ib` |
|---|---|---|---|---|---|
| Screening control | `ib10_sw20lat6` | 8 µm / 0.34 µm | XM3–XM6 6 µm | 20 µm | 10 µA |
| Preservation baseline | `w8_l034` | 8 µm / 0.34 µm | 3 µm (default) | 40 µm (default) | 20 µA (default) |
| Finalist | `w10` | 8 µm / 0.34 µm | XM3/XM4 6 µm, XM5/XM6 10 µm | 20 µm | 10 µA |

The baseline is the committed schematic with only the input pair narrowed to
8 µm. The control is the reference both screens were judged against. It is
not the preservation baseline.

## Decision (proposed)

Four questions, each with the answer the evidence supports. The ratifier may
take the first three and reject the fourth without affecting them.

| # | Question | Proposed answer |
|---|---|---|
| 1 | Keep DR-0001, or supersede it with a named topology? | Keep DR-0001. Neither named alternative has been measured. |
| 2 | Adopt the integration-node capacitance change? | No, for 1, 2 and 4 fF per side: all three settings were eliminated at the screen. |
| 3 | Which in-topology path carries Row 2 forward? | The load-width / bias axis, with `w10` as the measured reference point. No sizing adoption is proposed. |
| 4 | Score Row 2 at each candidate's own density? | Accept the per-candidate, per-PVT-point density derivation, reported beside the unchanged-bench figure. |

**1. Topology: keep DR-0001; supersede nothing.** The comparator stays
DR-0001's single-tail (bottom-tail) StrongARM dynamic latch with no
continuous-time preamp. Phase 2's two candidate families are both inside
that topology. Neither alternative DR-0001 names, the double-tail
(two-stage) dynamic latch and a static preamp ahead of the latch, has been
simulated as a candidate in this repo: no candidate netlist for either is
bound in any campaign, and no screen or grade exists for either. The
evidence therefore does not support re-opening DR-0001. That is a statement
about the evidence, not a finding that either alternative would fail. They
remain unmeasured (see Alternatives considered).

**2. Integration-node capacitance: not adopted.** Matched capacitance at the
input-pair drains, 1, 2 and 4 fF per side, is not adopted. All three settings
stayed inside the Row 3c bound and missed the noise screen. The conclusion
covers only the three measured settings.

**3. In-topology Row 2 path: the load-width / bias axis.** Of the seven
settings screened, only the matched PMOS load-width family produced a
setting that lowers Row 2 on the full grid while holding every Target the
8 µm baseline passes: `w10`. Row 2 still FAILs for `w10`, so this record
proposes no sizing adoption. It records `w10` as the reference point that
further in-topology Row 2 work starts from. It does not claim the axis is
exhausted, and it does not claim `w10` is the best width; the study shows
neither.

**4. Measurement-method item, to accept or reject.** Phase 1 shows the
fixed 36.27 nV/√Hz injection misstates every candidate whose front end
differs from the committed 12 µm design's. The proposal is derived in its
own section below. In one line: measure each candidate's own input-referred
white density at every PVT point of the Row 2 grid, inject that density at
that point, and report the resulting grid mean beside the unchanged-bench
figure. It moves no bound, and the unchanged-bench figure stays, because it
is the only measured quantity that isolates the latch's decision bandwidth.

**5. No bound moves.** No Target or Stretch bound is relaxed, tightened or
reworded. Row 2's Target (≤ 1.0 mV rms) and Stretch (≤ 0.6 mV rms) stay
exactly as DR-0002 ratified them, and Row 2 stays NOT MET for every design
measured. Bounds in the tables below are quoted in short form from DR-0002;
the full condition text is DR-0002's and is not restated here.

## Phase 1: what the fixed injection hides

### The injection is the committed design's own nominal density

The Row 2 compliance bench injects one input-referred white density at the
DUT's input pins and lets the latch set its own aperture. The density is
36.27 nV/√Hz at every PVT point (`vn_na = 5.735e-3`, `vn_ts = 20 ps`;
`trnoise(5.735e-3 2e-11 0 0)`). It was derived once, from the reduced
loop-broken sub-model's `.noise` record at `tt_27c_1.20v`
([`20260916-113303-180cca7`](../../sim/comparator-preamp-noise/records/20260916-113303-180cca7.md)),
and is deliberately not re-derived per corner
([`comparator-transient-noise/README.md`](../../sim/comparator-transient-noise/README.md),
"Calibration").

Phase 1 confirmed from the 30 committed `transient_noise` request bodies of
the two #92 campaigns that every #92 candidate, including all six finalists,
ran at that unchanged density. **Every #92 Row 2 number is a measurement of
effective decision bandwidth at the committed 12 µm design's nominal
density.** It is each other design's own density only by coincidence.

### Front-end's own input-referred white density, S (nV/√Hz)

`S` is the reduced model's differential output noise density at 1 MHz
divided by its gain magnitude at 1 Hz, from one `.noise` run per design per
point on the loop-broken `comparator_dut_analog` sub-model:

| PVT point | 12 µm committed | 8 µm baseline | control | `w10` |
|---|---:|---:|---:|---:|
| `sf_-40c_1.32v` | 29.02 | 33.98 | 29.72 | 27.4183 |
| `tt_27c_1.20v` | 36.27 | 42.16 | 36.78 | 33.758 |
| `ff_125c_1.08v` | 47.13 | 54.53 | 45.61 | 41.3512 |
| `fs_-40c_1.20v` | 29.53 | 34.50 | 30.52 | 28.223 |

The first three columns are Phase 1's four-point batch, 12 of 12 cells
pass. The committed design's four values reproduce the ratified calibration
record to the printed digits, so the measurement convention is unchanged.
The `w10` column is the #498 four-point batch, 20 of 20 cells pass, by the
same method
([`20261121-issue498-pvt.md`](../../sim/comparator-preamp-noise/reports/20261121-issue498-pvt.md)).

Three readings follow:

- **Narrowing the input pair raises the density.** Going from 12 µm to 8 µm
  raises the input-referred density 16–17 % at each of the four points. At
  TT the gain falls from 1.639 to 1.434 V/V while the output density rises
  from 59.46 to 60.45 nV/√Hz.
- **The fixed injection cuts both ways.** It overstates the noise of a
  design whose own density is below 36.27 nV/√Hz and understates one whose
  density is above it. The 8 µm baseline's own density is above the
  injection at all four points. `w10`'s is below it at `sf`, `tt` and `fs`
  and above it at `ff`.
- **Widening the loads lowers the density monotonically, at the cost of DC
  gain.** From 6 µm to 12 µm the TT density falls from 36.78 to 32.74
  nV/√Hz and the TT gain from 1.085 to 0.871 V/V.

### Where the density comes from

In Phase 1's 12 cells the PMOS pair XM5A/XM6A, which stands for the
cross-coupled XM5/XM6 and is diode-connected in the loop-broken model,
carries **85.4–92.4 %** of the differential output noise power. The input
pair carries 7.6–14.6 %. The tail device, the tail switch and the bias
mirror carry 0.0000 % at every cell: their noise reaches both outputs in
phase and cancels. Measured power closure is 100.00 % at every cell.

The input pair's share cannot bound what resizing it does, because resizing
changes the gain as well as the pair's own noise. That is why the pair's
7.6–14.6 % share coexists with a 16–17 % density rise.

### What the unchanged bench measures, and what each design would read at its own density

Each cell is **bench σ (mV rms) / ENBW (GHz) / σ_char (mV rms)**. Bench σ is
measured at the injected 36.27 nV/√Hz. `ENBW = (σ / 36.27 nV/√Hz)²`.
`σ_char = S_own × √ENBW` is **characterization, not a compliance figure**:
it assumes the decision response scales linearly with the injected
amplitude.

| PVT point | 12 µm committed | 8 µm baseline | control |
|---|---|---|---|
| `sf_-40c_1.32v` | 0.846 / 0.544 / 0.677 | 1.024 / 0.796 / 0.959 | 1.059 / 0.852 / 0.867 |
| `tt_27c_1.20v` | 1.361 / 1.408 / 1.361 | 1.107 / 0.932 / 1.287 | 1.157 / 1.017 / 1.173 |
| `ff_125c_1.08v` | 1.843 / 2.582 / 2.395 | 1.764 / 2.366 / 2.653 | 1.065 / 0.862 / 1.339 |
| `fs_-40c_1.20v` | 1.069 / 0.868 / 0.870 | 1.673 / 2.127 / 1.591 | 1.438 / 1.571 / 1.210 |
| **45-point bench grid mean σ** | **1.289** | **1.338** | **1.096** |
| **four-point mean σ_char** | **1.326** | **1.622** | **1.147** |

The committed-design column reproduces the projection derived from the
published record's densities, an independent cross-check since this batch
measured them again. The 8 µm baseline is no better than the committed
design on either reading: its 45-point bench mean, 1.338, sits above the
committed design's 1.289, and at its own density its four-point mean, 1.622,
sits further above the committed design's 1.326. The four-point means
characterize the selected bounding points; the ratified Target uses the
45-point grid mean.

### Nominal recalibration of the six #92 finalists

The projected mean is the design's 45-point bench mean times its TT density
over 36.27 nV/√Hz, holding that one density across all 45 decision
bandwidths. **These are projections, not verdicts.**

| Design | S(TT) (nV/√Hz) | 45-point bench mean (mV rms) | Nominally recalibrated mean (mV rms) |
|---|---:|---:|---:|
| 12 µm committed | 36.27 | 1.289 | 1.289 |
| `w8_l034` (the baseline) | 42.16 | 1.338 | 1.555 |
| `ib10_sw20lat6` (the control) | 36.78 | 1.096 | 1.112 |
| `w6_l034` | 47.10 | 1.333 | 1.731 |
| `w8_l020` | 38.94 | 1.265 | 1.358 |
| `ib10_sw20` | 41.45 | 1.192 | 1.363 |
| `ib12p5_sw20` | 41.58 | 1.255 | 1.439 |

The control retains the lowest projected mean of the six finalists.

### What Phase 1 put to Phase 2

Reaching 1.0 mV from the control's starting mean requires a uniform
reduction in σ. Phase 1 expressed it two ways, either of which gives the
same result:

| Starting mean and density reference | Starting σ (mV) | Density reduction at fixed bandwidth | Bandwidth reduction at fixed density |
|---|---:|---:|---:|
| 45-point bench, fixed 36.27 nV/√Hz injection | 1.096 | 8.8 % (to 33.09 nV/√Hz) | 16.8 % |
| 45-point nominal recalibration, 36.78 nV/√Hz at TT | 1.112 | 10.1 % | 19.1 % |
| Four bounding points, each at its measured density | 1.147 | 12.8 % at each point | 24.0 % |

Phase 1's conclusion for #479: "either lower input-referred density,
narrower effective decision bandwidth, or a combination can lower Row 2",
with the load share identifying the largest direct noise source.

## Phase 2, screening: 18 points, not a verdict

The screening grid is 18 of the 45 PVT points: tt/ff/ss × 1.08/1.32 V ×
−40/27/125 °C. The screen statistic is the mean of the per-point two-rung
probit-slope σ over those 18 points, N = 80 trials per rung, at the
unchanged compliance-bench injection of **36.27 nV/√Hz**. Every setting
below has all 18 points valid on each of its benches. **A screen row is not
a 45-point verdict.**

The control at zero added capacitance screens at 1.053 mV rms (unrounded
1.05259), with a worst Row 3c decision time at 0.1 mV of 1.862 ns at
`ss_-40c_1.08v`. Its 18-point mean is the 18 screening points of its own
45-point grade, not a re-run.

### Integration-node capacitance (#497)

Matched capacitance at the input-pair drains, each capacitor node-to-`vss`,
equal per side, added to the control geometry. Sources:
[revised screen](../../sim/klt-corner-verification/campaigns/20261121-issue497/capacitance-r2.md),
[addendum](../../sim/klt-corner-verification/campaigns/20261121-issue497-mc-addendum.md),
[dated analysis](../../sim/comparator-integration-capacitance/reports/20261121-issue497.md).

| Setting | C per side | Row 2 screen mean (mV rms) | vs control | Worst t_d at 0.1 mV (ns) | Outcome | Reason | Full-grid Rows 1–5 |
|---|---:|---:|---:|---:|---|---|---|
| `cadd1f` | 1 fF | 1.041 | −1.09 % | 1.88 | eliminated | noise: 1.09 % deficit against the 5.00 % reduction 1.0 mV requires | **unmeasured** |
| `cadd2f` | 2 fF | 1.022 | −2.92 % | 1.899 | eliminated | noise: 2.92 % deficit against the 5.00 % reduction | **unmeasured** |
| `cadd4f` | 4 fF | 1.025 | −2.63 % | 1.936 | eliminated | noise: 2.63 % deficit against the 5.00 % reduction | **unmeasured** |

All three stayed inside the 2.0 ns Row 3c bound. The unrounded means are
1.0411 / 1.0218 / 1.0249 mV rms, with paired standard errors of 29–36 µV
against the control. The #497 calibration found that 1–4 fF leaves the
reduced model's differential output density at 1 MHz and its gain at 1 Hz
unchanged, so these deficits are at most a decision-bandwidth effect, and
they sit at the screen's own sampling floor. The dated analysis puts that
floor at about 3 % standard error for one 18-point mean. Its delay-axis
extrapolation, which is not a measurement, puts the capacitance needed for
the noise reduction at 5–8 fF or more, with Row 3c at 1.99–2.01 ns against
the 2.0 ns Target. Capacitances between or beyond these settings were not
simulated.

### Matched PMOS load width (#498)

XM5/XM6 varied, with XM3/XM4, the input pair, the switch and the 10 µA bias
at the control's settings. Phase 1's load share motivated this family.
Sources: [corrected screen](../../sim/klt-corner-verification/campaigns/20261121-issue498/loadwidth-final.md),
[fast-bench table](../../sim/klt-corner-verification/campaigns/20261121-issue498/sizesweep-final.md).

| Candidate | XM5/XM6 | Row 2 screen mean (mV rms) | vs control | Worst t_d at 0.1 mV (ns) | Outcome | Reason | Full-grid Rows 1–5 |
|---|---:|---:|---:|---:|---|---|---|
| `w4` | 4 µm | 1.076 | ×1.022 | 1.83 | eliminated | Row 2: does not improve on the control's 1.053 mV at the same injection | **unmeasured** |
| `w8` | 8 µm | 1.065 | ×1.012 | 1.915 | eliminated | Row 2: does not improve on the control's 1.053 mV at the same injection | **unmeasured** |
| `w10` | 10 µm | 1.008 | ×0.958 | 1.977 | advanced | lowest eligible 18-point mean | measured, next section |
| `w12` | 12 µm | 1.032 | ×0.980 | 2.044 | eliminated | Row 3c: 2.044 ns exceeds the 2.0 ns Target at `ss_-40c_1.08v` | **unmeasured** |

No setting measured at or below 1.0 mV rms on the screen. `w10`'s 1.008 is
above it.

`w12` exceeds Row 3c at two of the 18 screened points: 2.044 ns at
`ss_-40c_1.08v`, the worst and the recorded reason, and 2.031 ns at
`ss_125c_1.32v`
([screen envelope](../../sim/klt-corner-verification/campaigns/20261121-issue498/scr_w12/regeneration.envelope.json)).
That envelope's status is therefore `fail` (16 pass, 2 fail of 18 units).
All 18 units are still valid measurements: the decision gates passed at
every unit and only the 0.1 mV decision-time bound failed, at two. Every
other committed envelope in these campaigns has status `pass`.

The two families fall short in opposite ways. The capacitance settings keep
Row 3c and miss the noise screen. `w12` lowers the control's noise mean and
misses Row 3c. No setting combining the two families was measured.

## Phase 2, finalist: 45 points

Both grades cover 45 PVT points (tt/ff/ss/fs/sf × 1.08/1.20/1.32 V ×
−40/27/125 °C). Row 1 has 60 offset draws per point and Row 2 has 80 draws
per rung at every point, in both designs. Rows 3, 4 and 5b are
deterministic. Row 5a is the coverage check across all four benches. Neither
grade has a missing draw or an INCOMPLETE row. Sources:
[baseline grade](../../sim/klt-corner-verification/campaigns/20261009-issue92/full_w8_l034/grading.md),
[`w10` grade](../../sim/klt-corner-verification/campaigns/20261121-issue498/full_w10/grading.md).
The Row 2 figures are at the injected **36.27 nV/√Hz**. Graded NOT
SPECIFIED is never PASS.

| Row | Measurement | Target bound | Stretch bound | 8 µm baseline | `w10` | Target verdict (baseline / `w10`) | Stretch verdict (baseline / `w10`) |
|---|---|---|---|---:|---:|---|---|
| 1 | Offset, worst 3σ | ≤ 15 mV | ≤ 8 mV | 13.93 `tt_125c_1.08v` | 13.37 `ff_125c_1.08v` | PASS / PASS | FAIL / FAIL |
| 2 | Decision noise, grid mean | ≤ 1.0 mV rms | ≤ 0.6 mV rms | 1.33778 | 1.04143 | FAIL / FAIL | FAIL / FAIL |
| 3a | Decision time at 50 mV, worst | ≤ 1.5 ns | ≤ 0.8 ns | 0.8664 `ss_125c_1.32v` | 1.188 `ss_125c_1.32v` | PASS / PASS | FAIL / FAIL |
| 3b | Regeneration time constant, worst | ≤ 250 ps | — | 168.7 `ss_-40c_1.08v` | 135.6 `ss_-40c_1.08v` | PASS / PASS | — |
| 3c | Decision time at 0.1 mV, worst | ≤ 2.0 ns | — | 1.705 `ss_-40c_1.08v` | 1.977 `ss_-40c_1.08v` | PASS / PASS | — |
| 4a | Injected charge per side, worst | ≤ 25 fC | ≤ 8 fC | 21.2 `ff_125c_1.32v` | 19.76 `ff_125c_1.32v` | PASS / PASS | FAIL / FAIL |
| 4b | Signal-dependent residue, worst | ≤ 100 µV | ≤ 30 µV | 10.29 `ss_-40c_1.20v` | 10.42 `ss_-40c_1.08v` | PASS / PASS | PASS / PASS |
| 4c | Single-ended excursion, worst (reporting only) | — | — | 96.03 `ff_27c_1.32v` | 97.95 `ff_125c_1.32v` | REPORTED | — |
| 5a | PVT coverage, all four benches | full grid | — | 45/45 per bench | 45/45 per bench | PASS / PASS | — |
| 5b | Average power at 33.3 MHz, worst | — | ≤ 20 µW | 37.61 `ff_125c_1.32v` | 25.67 `ff_125c_1.32v` | — | FAIL / FAIL |

A dash marks a bound DR-0002 does not specify.

**Preservation.** The baseline passes Targets 1, 3a, 3b, 3c, 4a, 4b and 5a
and fails Row 2. `w10` returns the same verdict on every row, so it
preserves every Target the baseline passed. It also returns the same
Stretch verdict on every row: of the six specified Stretch bounds, both
designs meet only the Row 4b Stretch.

**Why Row 2 fails.** The DR-designated statistic is the grid-wide mean of
the per-point two-rung probit-slope σ at the 36.27 nV/√Hz bench injection.
The baseline's mean is 1.33778 mV rms (per point 0.9733 at `ss_-40c_1.32v`
to 1.764 at `ff_125c_1.08v`). `w10`'s is 1.04143 mV rms (per point 0.7902 at
`ss_125c_1.08v` to 1.323 at `tt_-40c_1.20v`). `w10`'s mean is 22.2 % below
the baseline's and 5.0 % below the control's 45-point mean, and it misses
the Target by 4.1 %.

**Margins that narrowed under `w10`.** Three preserved Targets sit closer
to their bound. Row 3a moves from 0.8664 to 1.188 ns against ≤ 1.5 ns. Row 3c
moves from 1.705 to 1.977 ns against ≤ 2.0 ns, which leaves 0.023 ns at the
binding corner `ss_-40c_1.08v`. Row 4b residue rises from 10.29 to 10.42 µV
against ≤ 100 µV and still meets its 30 µV Stretch.

**Margins that widened.** Target headroom grows on Row 1 (13.93 to 13.37 mV
against ≤ 15 mV), Row 3b (168.7 to 135.6 ps against ≤ 250 ps) and Row 4a
(21.2 to 19.76 fC against ≤ 25 fC). Row 5b has no Target; its power falls
from 37.61 to 25.67 µW, so its excess over the 20 µW Stretch shrinks from
17.61 to 5.67 µW and still fails.

**The control's own grade is incomplete and is a reference only.** Row 1 is
INCOMPLETE (43/45 points valid; two points have 59 usable offset draws
against the ratified N = 60, the first `ff_-40c_1.20v`) and so is Row 5a
(offset Monte Carlo not validly exercised at 2/45 points:
`analysis_aborted, measurement, timestep_too_small`). Its Row 2 is FAIL at
1.096 mV rms. Its Stretch verdicts are FAIL on Rows 1, 3a, 4a and 5b and
PASS on Row 4b.

### Limits of the comparison, in the Phase 2 report's own terms

- **Capacitance.** Only 1, 2 and 4 fF per side were measured. Saturation
  and the behaviour at other capacitances remain undetermined.
- **Load width.** Widths between 10 and 12 µm have no timing grade. Only
  `w10` has a 45-point grade, and nothing shows it is the best width. The
  screen places `w10` (1.008 mV rms) below `w12` (1.032 mV rms), a 2.3 %
  difference on the unrounded means, smaller than the ≈ 3 % standard error
  the #497 analysis derives for one 18-point mean at N = 80 per rung.
- **Not an ablation.** `w10` against the baseline differs in bias, latch
  devices and switch. The two grades also came from different toolchains:
  the baseline from klt `0.5.0+ge8ca621a6961` and ngspice 46, `w10` from klt
  `0.9.3.dev2575+g6bd18bbc8637` and ngspice 47.
- **Sampling.** 1669 of 3600 samples (baseline) and 3584 of 3600 (`w10`)
  repeat a raw noise draw also seen at another grid point, never within one
  point. Each point's estimate is valid and unbiased, but the points are
  not mutually independent, so each grid mean's sampling error is wider
  than an independent-points estimate.
- **Seeds.** ngspice's TRNOISE generator ignores klt's per-sample
  `.options seed=`. Draws are independent within a point but not
  reproducible, and separate batch jobs can share noise streams. Run counts
  are the bench defaults committed in each request: transient noise N = 80
  per rung, offset Monte Carlo N = 60 per point, base seed 20260916.

## Does any finalist meet Row 2 while preserving the baseline's rows?

**No.** `w10` is the only setting with a 45-point grade. It preserves every
Target the baseline passes and it FAILs Row 2 at 1.04143 mV rms against the
≤ 1.0 mV rms Target. No other setting was measured on the 45-point grid,
and none of the six eliminated settings measured at or below 1.0 mV rms on
the 18-point screen. Neither family demonstrated closure of Row 2.

**Measured** values below are the whole-latch transient-noise decision
statistic of DR-0002 Row 2: three rungs per point (0 and ±1.0 mV overdrive),
N = 80 trials per rung, a two-rung probit-slope σ per point, averaged over
the named grid. **Projections** rescale a measured 45-point mean by an
own-density ratio, mean × S / 36.27. They assume the decision response
scales linearly with the injected amplitude, so that each point's decision
bandwidth is unchanged when the density changes, and they apply one density
to all 45 points.

| Value (mV rms) | Design | Grid | Density (nV/√Hz) | Basis |
|---|---|---|---|---|
| 1.289 | 12 µm committed | 45 points | injected 36.27 | measured |
| 1.33778 | baseline `w8_l034` | 45 points | injected 36.27 | measured |
| 1.04143 | `w10` | 45 points | injected 36.27 | measured |
| 1.096 (1.09627632) | control | 45 points | injected 36.27 | measured |
| 1.053 | control | 18 points | injected 36.27 | measured, screen |
| 1.041 / 1.022 / 1.025 | `cadd1f` / `cadd2f` / `cadd4f` | 18 points | injected 36.27 | measured, screen |
| 1.076 / 1.065 / 1.008 / 1.032 | `w4` / `w8` / `w10` / `w12` | 18 points | injected 36.27 | measured, screen |
| **0.96930** | `w10` | 45 points | own TT 33.758 | **projection** at `w10`'s measured bandwidth |
| 1.02035 | `w10` | 45 points | own TT 33.758 | projection at the control's bandwidth, held fixed |
| 1.19114 / 1.05919 / 0.989644 | `w4` / `w8` / `w12` | 45 points | own TT 39.4084 / 35.0431 / 32.7421 | projection at the control's bandwidth, held fixed |
| 1.555 | baseline `w8_l034` | 45 points | own TT 42.16 | projection at the baseline's measured bandwidth |

The four projections and the bandwidth each assumes:

- **0.96930** = 1.04143154 × 33.758 / 36.27. The bandwidth is `w10`'s own, as
  measured in its 45-point grade.
- **1.02035** = 1.09627632 × 33.758 / 36.27. The bandwidth is the
  control's, substituted for `w10`'s.
- **1.19114 / 1.05919 / 0.989644** = 1.09627632 × S / 36.27, with S each
  candidate's unrounded TT density. The bandwidth is the control's, held
  fixed, so these three are not comparable with 0.96930.
- **1.555** = 1.338 × 42.16 / 36.27. The bandwidth is the baseline's own.

**0.96930 is not a verdict.** The ratified statistic is the measured grid
mean, 1.04143 mV rms, which fails. The projection applies the single TT
density to all 45 points, while `w10`'s measured density at the four
characterized points spans 27.42 nV/√Hz (`sf`, −40 °C / 1.32 V) to 41.35
nV/√Hz (`ff`, 125 °C / 1.08 V), so at `ff` it is above the injection. And
the reduced model's density is a reportable lower bound, never a compliance
figure.

Two further readings the table supports, neither a verdict:

- `w12` projects below the Target at the control's bandwidth (0.989644) and
  is the setting that exceeds Row 3c. Along the load-width axis, the width
  whose projection falls under 1.0 mV is a width the delay row does not
  admit.
- The 8 µm baseline's projection (1.555) is above its unchanged-bench mean
  (1.338), and the control's two numbers nearly agree (1.096 and 1.112).
  How much the fixed injection misstates a design depends on how far its
  front end sits from the committed design's.

## Expected layout cost

Expected, not measured: no candidate has been placed or routed. The
committed cell is one flat top cell, `comparator`, 31.46 × 76.00 µm
([`layout/README.md`](../../layout/README.md)). No area estimate is
committed for any candidate.

| Candidate | Schematic change | Expected layout cost |
|---|---|---|
| `cadd1f`, `cadd2f`, `cadd4f` | Two capacitor pairs added: `C497P`/`C497N` at `np`/`nn` to `vss` inside `.subckt comparator`, and the loop-broken twins. Bound as structural candidate netlists because the geometry override cannot express them ([`cadd1f.spice`](../../sim/comparator-integration-capacitance/candidates/cadd1f.spice)). | **The largest of the study, and none of it exists.** The generator has no capacitor primitive. Its reference parser reads only `X` instances inside `.subckt comparator`, so a capacitor line would neither be drawn nor make the self-check refuse. LVS compares against that block cut verbatim, so a layout without the capacitors would not match. The ERC request declares no device carve-out, on the stated ground that the cell has no MiM or similar device. Adopting a capacitance needs generator, self-check, LVS and ERC work before the standard re-runs below. None is proposed: all three settings were eliminated. |
| `w4`, `w8`, `w10`, `w12` | Geometry only: `XM5.w`/`XM6.w` on the control's settings, which are themselves overrides of `design/comparator.spice`. `dut_ib` at 10 µA is an operating condition carried by [`sim/dut.json`](../../sim/dut.json), not geometry. | **The same class of change the DR-0033 draft discloses for the 8 µm pair.** [`generate.py`](../../layout/comparator/generate.py) draws from a hand-written device table and refuses to draw unless drawn W equals schematic W × m for all 24 instances, so each width is a device-table edit followed by regeneration. The GDS hash changes; DRC, LVS, ERC and nominal PEX re-run; #61's extracted evidence, tied to the current hash, is superseded; a fresh 45-point campaign, an N = 200 offset population and yield report, a characterization report and the manifest repins follow, as #481 lists for the 8 µm pair. |

Relative to the committed schematic, `w10` changes four widths: XM1/XM2
12 → 8 µm, XM3/XM4 3 → 6 µm, XM5/XM6 3 → 10 µm and XMSW 40 → 20 µm. The
generator's matched-pair rule, identical unit cells placed A B B A, can be
kept at the new widths. It is a larger change than the DR-0033 draft's,
which touches the input pair only.

For the two topology alternatives no layout statement can be made beyond
what DR-0001 recorded: a double-tail "adds device count, area, and a second
dynamic current pulse". No netlist exists to estimate from.

## Measurement-method item: per-candidate density, for the ratifier to accept or reject

**What Phase 1 shows.** The fixed 36.27 nV/√Hz injection is the committed
12 µm design's own nominal-corner density. For every other design measured
it is not that design's density, and the gap is not small: 16–17 % for the
8 µm pair at all four characterized points, and of opposite sign from point
to point for `w10`, below the injection at `sf`, `tt` and `fs` and above it
at `ff`. A Row 2 figure taken at the fixed
injection therefore answers "how wide is this latch's decision aperture at
the committed design's noise density", not "how noisy is this comparator".
As #477 put it of the #92 sweep, "'Input-pair W/L is not the lever' may
therefore be a property of the bench, not of the design".

**Proposed method.** For each candidate design and each of the 45 PVT
points of the Row 2 grid:

1. Derive S(PVT), the candidate's own input-referred white density, by the
   Phase 1 method: one `.noise` run on that candidate's loop-broken
   `comparator_dut_analog` sub-model, differential output density at 1 MHz
   divided by gain magnitude at 1 Hz. For the committed design at
   `tt_27c_1.20v` this returns 36.27 nV/√Hz, the ratified calibration.
2. Inject S(PVT) at that point's Row 2 run, scaling `vn_na` by S(PVT)/36.27.
   Keep `vn_ts`, the three rungs, N = 80, the statistic and the grader as
   they are.
3. Report the resulting grid-wide mean **beside** the unchanged-bench
   figure, each labelled with the density it was run with.
4. For a candidate that adds or changes front-end devices, include those
   devices in the sub-model, as #477 required of its topology candidates.

The drafting view is for the per-PVT-point form rather than a single
per-candidate density: `w10`'s own density straddles the injection, so one
number cannot stand for its grid.

**What accepting it concedes.** The limits are the reduced model's and the
bench's. The first and third below understate the design's noise, the second
is a difference of unestablished sign, and the fourth bounds precision:

- The sub-model's density is a **reportable lower bound** on the front
  end's own noise. It excludes the regenerative pair and the reset devices.
  On the committed design, issue #81 measured the internal term alone at
  ≈ 0.177 mV at 1×, about 2 % of the power, with front end alone 1.356 mV
  and complete injection 1.305 mV
  ([`comparator-transient-noise-full/README.md`](../../sim/comparator-transient-noise-full/README.md)).
- The sub-model is a different operating point from the strobed latch:
  loop-broken, with the PMOS pair diode-connected.
- Only a white density is injected. 1/f, gate-resistance and substrate
  noise are not in the model.
- Injection still enters at the DUT's input pins, and the TRNOISE seed
  limitation above still applies.

**What it costs.** 45 `.noise` runs per candidate on the reduced model, on
the batch fleet, plus a re-run of that candidate's Row 2 grid with a
per-point density; today's bench body sets one `vn_na` for every corner.
**No such Row 2 run is committed for any candidate.** That is why this
record quotes projections and four-point characterizations, and no
own-density grid mean.

**If rejected.** The fixed calibration stays the only Row 2 figure, the
unchanged-bench grades stand as they are, and candidate-own-density numbers
remain projections, labelled as such.

**In either case** the Row 2 bound is untouched, and so is the
unchanged-bench figure's role as the measurement that isolates decision
bandwidth.

## What is left, per Phase 1

**No candidate closes Row 2.** Phase 1 split the distance into two factors,
and Phase 2 measured how far each in-topology lever moves them:

- **Density.** Row 2 falls in proportion to the injected density at fixed
  bandwidth. Widening the PMOS loads lowers the density monotonically: TT
  36.78 nV/√Hz at 6 µm, 33.758 at 10 µm, 32.7421 at 12 µm. The width that
  lowers it most, 12 µm, exceeds Row 3c. The input pair moves the density
  the other way when narrowed.
- **Bandwidth.** Row 2 falls with the square root of effective decision
  bandwidth at fixed density. `w10` lowers the 45-point bench mean 5.0 %
  below the control's. 1–4 fF of integration-node capacitance lowers the
  18-point mean 1.09–2.92 %, against the 5.00 % the screen required.

What remains for `w10` at the unchanged bench is 0.04143 mV rms, 4.1 % of
the Target. Whether its own density closes that gap is the open question
the method item decides, and the committed data do not answer it: the
projection says yes at TT and the measured `ff` density says the injection
understates it there.

The study leaves these ranges and questions open, and none is started by
this record:

1. **Own-density Row 2 figures** for the committed design, the baseline,
   the control and `w10` on the 45-point grid, if the method item is
   accepted.
2. **Load widths between 10 and 12 µm**, which have no timing grade.
3. **Capacitances between or beyond 1, 2 and 4 fF**, and any setting that
   combines the two families.
4. **The two topology alternatives**, which have no measurement at all.
5. **How much weight a 4.1 % gap carries.** The verdict as measured is
   FAIL. No grid-mean uncertainty figure is committed for `w10`. The only
   committed numeric one for Row 2 is the issue #81 campaign's, 0.029 mV rms
   assuming independent points and up to 0.19 mV rms for a fully correlated
   grid, and it was measured on the committed design.

Phase 1's own closing holds: establishing compliance requires the grid-wide
statistic specified for Row 2.

## Relationship to #476 and the DR-0033 draft

The DR-0033 draft (PR #490, open and unmerged when this record was drafted)
proposes adopting the 8 µm / 0.34 µm input pair at the existing 20 µA bias,
everything else at schematic defaults, for Row 4a kickback. **The direction
proposed here composes with it.**

- **Same topology, same input pair.** `w10` carries exactly the DR-0033
  draft's input pair, `XM1`/`XM2` at 8 µm / 0.34 µm. It differs from that
  candidate in the bias (10 µA against 20 µA), all four latch devices (XM3
  and XM4 at 6 µm and XM5 and XM6 at 10 µm, against 3 µm) and the switch
  (20 µm against 40 µm). Ratifying DR-0033 would not take the design away
  from the Row 2 direction; the pair carries into it unchanged.
- **`w10` passes every row the DR-0033 candidate passes**, with more Target
  headroom on Row 1 (13.37 against 13.93 mV) and Row 4a (19.76 against
  21.2 fC).
- **One cost the DR-0033 draft names is retired, if this record is ratified
  as drafted.** It gives "a later topology change from the Row 2 work" as
  the risk that would force #481's regenerated layout and evidence to be
  redone. The proposed direction keeps DR-0001, so no topology change comes
  from it.
- **A sizing risk remains.** If further in-topology Row 2 work lands on a
  `w10`-like sizing, the bias, latch and switch change and that work is
  redone once more. That is the cost of adopting the pair before Row 2 is
  settled. It is the DR-0033 draft's question to weigh, not this record's.
- **Phase 1 quantifies the Row 2 cost of the 8 µm pair** that the DR-0033
  draft disclosed qualitatively. Narrowing the pair from 12 µm to 8 µm
  raises the input-referred density 16–17 % at each of the four
  characterized points, and the baseline's Row 2 mean goes from 1.338 mV rms
  at the unchanged bench to a 1.555 mV rms projection at its own TT
  density. The projection is characterization, not a verdict.

This record proposes neither answer to the DR-0033 draft's question. It
states only that the two do not conflict, and that on the Row 2 direction
proposed here the topology-change risk the draft named does not arise.

## Alternatives considered

- **Supersede DR-0001 with a double-tail (two-stage) dynamic latch.** Not
  proposed. No measurement exists, and a direction record should not pick a
  topology on none. DR-0001 named it "a real, not-pursued alternative" for
  kickback isolation, at the cost of device count, area and a second
  dynamic current pulse. It stays the escalation path if in-topology work
  fails. A study of it has a route: the structural DUT binding #497 added
  lets the grader accept a named candidate netlist that is not a geometry
  override, and its density derivation would have to include the new
  first-stage devices.
- **Supersede DR-0001 with a continuous-time preamp ahead of the latch.**
  Not proposed. One of DR-0001's three reasons for rejecting a preamp has
  not held: it judged the noise target "not obviously out of reach for a
  bare latch", and the bare latch's noise is measured not to reach it.
  DR-0001 anticipated that and said a preamp "is not ruled out
  permanently". This record does not take that path yet because the path's
  benefit is unmeasured while its costs land on rows that are already
  failing or tight. DR-0001's other two reasons were decision time and
  power. The power Stretch fails for every design graded here (37.61 µW
  baseline, 25.67 µW `w10`, 24.67 µW control, against ≤ 20 µW), and `w10`
  leaves 0.023 ns on Row 3c.
- **Adopt `w10` now as a partial improvement.** Not proposed by this
  record. Row 2 FAILs for it, this is a direction record and not an
  adoption record, and its narrowed margins, 0.023 ns on Row 3c above all,
  belong in an adoption record of their own beside the DR-0033 question.
- **Keep the integration-node capacitance despite the screen.** Not
  proposed. Three settings were eliminated and the extrapolation to larger
  capacitance is not a measurement.
- **Relax the Row 2 Target.** Out of scope and not proposed. #477 excluded
  it, the 2026-10-15 ruling directed "do not adopt relaxed targets", and
  agents do not relax the spec to make results pass.
- **Record the negative result and state no direction.** Rejected. The
  study does say which in-topology axis moves Row 2 on the full grid and
  which does not, and leaving that unsaid would send the next study back to
  the axis the screen closed for the measured settings.

## What this record does not do

- It changes no Target, Stretch or spec row. `README.md` is untouched.
- It supersedes neither DR-0001 nor DR-0002, and edits no earlier record.
- It adopts no sizing, no capacitance and no topology, and it changes the
  compliance bench's density nowhere.
- It changes no file under `design/`, `layout/`, `sim/` or `manifests/`.
  The campaigns and reports it cites stay unedited, append-only.
- It runs nothing: no simulation, no layout, no campaign.
- It does not decide the DR-0033 draft's adopt-or-wait question.

## How this record gets ratified

Per [`spec/README.md`](../README.md), as #477 and #480 specified for this
record: the **normal ratification hold**. Ratification is the two-key merge
of the PR landing this record, an EE-key review and a market-key review,
neither held by the author, posted with their `RATIFY-KEY:` markers. The
merge commit is the ratification record. The drafting agent holds neither
key and must not hand-merge. As #480 requires, the PR carries
`Part of #480` and not a closing reference, so the issue stays open until
the direction is ratified.

Merging ratifies the direction as proposed, as amended by the keys. Question
4 is separable: a review that accepts the direction and rejects the
measurement-method item leaves items 1 to 3 in force.

## Consequences

If ratified as proposed:

1. **DR-0001 stands.** No topology study is started by this record, and
   none is foreclosed: the alternatives stay named, with their evidence gap
   on the record.
2. **The integration-node direction is closed for 1, 2 and 4 fF per side**,
   and only for those settings.
3. **Row 2 stays NOT MET for every design measured**, and T1 items 5 and 8
   stay as they are: item 5 stays unmet while Row 2 fails.
4. **Further in-topology Row 2 work starts from `w10`**, and anyone
   proposing a `w10` adoption does so in an adoption record that weighs its
   0.023 ns Row 3c margin.
5. **The measurement-method question is settled one way or the other**, and
   Row 2 candidate figures are either reported at two densities or at the
   fixed one, by rule rather than by choice of the report.

## Open items

- **Own-density Row 2 grid means** for the reference designs, pending
  question 4.
- **Timing grade for load widths between 10 and 12 µm**, and noise and
  timing for capacitances outside 1, 2 and 4 fF, if the in-topology search
  is to be completed.
- **A grid-mean uncertainty statement for `w10`'s 45-point mean.** The
  issue #81 campaign's statement covers the committed design only.
- **A bounded study of a topology alternative**, if the in-topology path
  and the own-density measurement do not close Row 2. That is the point at
  which DR-0001's escalation paths come up for a decision.
- **The DR-0033 draft's adopt-or-wait question**, which stays with its own
  PR.

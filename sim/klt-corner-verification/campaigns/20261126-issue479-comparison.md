# Row 2 noise, Phase 2: combined comparison against the 8 µm input-pair baseline (issue #479)

**Report date 2026-11-26.** This is the dated Phase 2 comparison that
[#480](https://github.com/2AMLogic/sg13g2-comparator/issues/480) waits on. It
brings together the two Phase 2 studies of
[#479](https://github.com/2AMLogic/sg13g2-comparator/issues/479), the
integration-node capacitance screen
([#497](https://github.com/2AMLogic/sg13g2-comparator/issues/497), PR #504) and
the matched PMOS load-width screen with its `w10` finalist
([#498](https://github.com/2AMLogic/sg13g2-comparator/issues/498), PR #501),
and sets them against the archived 8 µm input-pair baseline. The densities and
the density-times-bandwidth reading of Row 2 come from the Phase 1 analysis
([#477](https://github.com/2AMLogic/sg13g2-comparator/issues/477), PR #494).
Every value is copied from evidence merged on `main` at `a720d8b4a`; nothing
was re-simulated, re-graded or regenerated. The report proposes no bound and
changes no spec row, no DUT and not `sim/dut.json`.

## Answer

**No measured candidate closes Row 2 while preserving every Target the
baseline passed.**

- Seven settings were screened on the 18-point grid across the two families.
  Six were eliminated. The 10 µm PMOS load `w10` advanced and is the only
  setting with a 45-point grade.
- `w10` preserves every Target the 8 µm baseline passed (Rows 1, 3a, 3b, 3c,
  4a, 4b and 5a) and changes no Stretch verdict.
- Row 2 FAILs for `w10`. Its measured 45-point grid mean is
  **1.04143 mV rms** against the ≤ 1.0 mV rms Target. The baseline's is
  1.33778 mV rms.
- `w10`'s **0.96930 mV rms** is a TT-density **projection**. It is not a
  measurement and not a Target verdict.
- Neither family demonstrated closure of Row 2.

## Three designs, kept distinct

| Role in this report | Name | Input pair XM1/XM2 | Latch devices | Switch XMSW | Bias `dut_ib` | Evidence |
|---|---|---|---|---|---|---|
| Screening control | `ib10_sw20lat6` | 8 µm / 0.34 µm | XM3–XM6 6 µm | 20 µm | 10 µA | [grade](20261115-issue92-bias/full_ib10_sw20lat6/grading.md), [geometry](20261115-issue92-bias/sizesweep-final.md) |
| Preservation baseline | `w8_l034` | 8 µm / 0.34 µm | 3 µm (default) | 40 µm (default) | 20 µA (default) | [grade](20261009-issue92/full_w8_l034/grading.md), [geometry](20261009-issue92/sizesweep.md) |
| Finalist | `w10` | 8 µm / 0.34 µm | XM3/XM4 6 µm, XM5/XM6 10 µm | 20 µm | 10 µA | [grade](20261121-issue498/full_w10/grading.md), [geometry](20261121-issue498/sizesweep-final.md) |

The control is the reference both screens were judged against. It is not the
preservation baseline.

The baseline `w8_l034` is the committed schematic with only the input pair
narrowed to 8 µm (override `XM1.w=8u XM2.w=8u`). Its 0.34 µm length and every
other device are the [schematic](../../../design/comparator.spice) defaults,
and its bias is the `sim/dut.json` default. The control adds the issue #92
bias, latch and switch changes, and `w10` is the control with XM5/XM6 at
10 µm. `w10` and the baseline therefore differ in the bias, all four latch
devices and the switch, not only in the PMOS load width. The load-width-only
comparison is `w10` against the control.

The control's own 45-point grade is not complete. Row 1 is INCOMPLETE (43/45
points; two have 59 usable offset draws against the ratified N = 60) and so is
Row 5a. Its 45-point Row 2 mean is used here as a bandwidth reference only.

## Screening outcomes on the 18-point grid

The screening grid is 18 of the 45 PVT points: tt/ff/ss × 1.08/1.32 V ×
−40/27/125 °C. The Row 2 screen statistic is the mean of the per-point
two-rung probit-slope σ over those 18 points, N = 80 trials per rung, at the
unchanged compliance-bench injection of 36.27 nV/√Hz. Every setting below has
all 18 points valid on each of its benches. A screen row is not a 45-point
verdict.

Control `ib10_sw20lat6` (0 fF per side, 6 µm loads): Row 2 screen mean
1.053 mV rms, worst Row 3c decision time at 0.1 mV 1.862 ns at
`ss_-40c_1.08v`. Both screens used this archived control. Its 18-point mean
is the 18 screening points of its own 45-point grade, not a re-run.

### Integration-node capacitance (#497)

Matched capacitance at the input-pair drains (`np`/`nn`), each capacitor
node-to-`vss`, equal per side, added to the control geometry. Sources:
[revised screen](20261121-issue497/capacitance-r2.md),
[addendum](20261121-issue497-mc-addendum.md),
[dated analysis](../../comparator-integration-capacitance/reports/20261121-issue497.md).

| Setting | C per side | Row 2 screen mean (mV rms) | vs control | Worst t_d at 0.1 mV (ns) | Outcome | Reason | Full-grid Rows 1–5 |
|---|---:|---:|---:|---:|---|---|---|
| `cadd1f` | 1 fF | 1.041 | −1.09 % | 1.88 | eliminated | noise: 1.09 % deficit against the 5.00 % reduction 1.0 mV requires | unmeasured |
| `cadd2f` | 2 fF | 1.022 | −2.92 % | 1.899 | eliminated | noise: 2.92 % deficit against the 5.00 % reduction | unmeasured |
| `cadd4f` | 4 fF | 1.025 | −2.63 % | 1.936 | eliminated | noise: 2.63 % deficit against the 5.00 % reduction | unmeasured |

All three settings stayed inside the 2.0 ns Row 3c limit and missed the
1.0 mV noise screen, so none advanced. The unrounded means are
1.0411 / 1.0218 / 1.0249 mV rms and the unrounded delays 1.8804 / 1.8988 /
1.9364 ns, with paired standard errors of 29–36 µV against the control on the
noise mean. The #497 calibration found that 1–4 fF leaves the
reduced model's differential output density at 1 MHz and its gain at 1 Hz
unchanged, so the 1–3 % screen deficits are at most a decision-bandwidth
effect, and they sit at the screen's own sampling floor.

The capacitance conclusion covers only 1, 2 and 4 fF per side. Capacitances
between or beyond these settings were not simulated.

### Matched PMOS load width (#498)

XM5/XM6 varied, with XM3/XM4, the input pair, the switch and the 10 µA bias
at the control's settings. Phase 1 attributed 85.4–92.4 % of the differential
output noise power to the diode-connected loads, which motivated this family.
Sources: [corrected screen](20261121-issue498/loadwidth-final.md),
[fast-bench table](20261121-issue498/sizesweep-final.md).

| Candidate | XM5/XM6 | Row 2 screen mean (mV rms) | vs control | Worst t_d at 0.1 mV (ns) | Outcome | Reason | Full-grid Rows 1–5 |
|---|---:|---:|---:|---:|---|---|---|
| `w4` | 4 µm | 1.076 | ×1.022 | 1.83 | eliminated | Row 2: does not improve on the control's 1.053 mV at the same injection | unmeasured |
| `w8` | 8 µm | 1.065 | ×1.012 | 1.915 | eliminated | Row 2: does not improve on the control's 1.053 mV at the same injection | unmeasured |
| `w10` | 10 µm | 1.008 | ×0.958 | 1.977 | advanced | lowest eligible 18-point mean | measured, next section |
| `w12` | 12 µm | 1.032 | ×0.980 | 2.044 | eliminated | Row 3c: 2.044 ns exceeds the 2.0 ns Target at `ss_-40c_1.08v` | unmeasured |

Only `w10` advanced. `w4` and `w8` are above the control on Row 2. `w12`
lowers the control's Row 2 mean but stays above 1.0 mV and exceeds the Row 3c
Target. The two families fall short in opposite ways: the capacitance
settings keep Row 3c and miss the noise screen, while `w12` lowers the
control's noise mean and misses Row 3c.

`w12` exceeds Row 3c at two of the 18 screened points: 2.044 ns at
`ss_-40c_1.08v`, the worst and the recorded reason, and 2.031 ns at
`ss_125c_1.32v`
([screen envelope](20261121-issue498/scr_w12/regeneration.envelope.json)).
That envelope's own status is therefore `fail` (16 pass, 2 fail of 18 units)
and its invocation exited 3. All 18 units are still valid measurements: the
decision gates passed at every unit, and only the `td_od01_ns` bound failed at
two. Every other committed envelope in these campaigns has status `pass`.

## Finalist versus baseline on the 45-point grid

Both grades cover 45 PVT points (tt/ff/ss/fs/sf × 1.08/1.20/1.32 V ×
−40/27/125 °C). Row 1 has 60 offset draws per point and Row 2 has 80 draws per
rung at every point, in both designs. Rows 3–5 are deterministic. Neither
grade has a missing draw or an INCOMPLETE row. Bounds are the DR-0002 values in
[rows.json](../rows.json). A dash marks a bound DR-0002 does not specify.
Graded NOT SPECIFIED is never PASS. The PVT point of each worst-case value
follows it. Sources:
[baseline grade](20261009-issue92/full_w8_l034/grading.md),
[w10 grade](20261121-issue498/full_w10/grading.md).

| Row | Measurement | Target bound | Stretch bound | 8 µm baseline | w10 | Target verdict (baseline / w10) | Stretch verdict (baseline / w10) |
|---|---|---|---|---|---|---|---|
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

**Preservation.** The baseline passes Targets 1, 3a, 3b, 3c, 4a, 4b and 5a
and fails Row 2. `w10` returns the same verdict on every row, so it preserves
every Target the baseline passed. It also returns the same Stretch verdict on
every row: of the six specified Stretch bounds, both designs meet only the
Row 4b Stretch.

**Why Row 2 fails.** The DR-designated statistic is the grid-wide mean of the
per-point two-rung probit-slope σ at the 36.27 nV/√Hz bench injection. The
baseline's mean is 1.33778 mV rms (0.33778 mV over the Target; per point
0.9733 at `ss_-40c_1.32v` to 1.764 at `ff_125c_1.08v`). `w10`'s is
1.04143 mV rms (0.04143 mV over; per point 0.7902 at `ss_125c_1.08v` to 1.323
at `tt_-40c_1.20v`). `w10`'s mean is 22.2 % below the baseline's and 5.0 %
below the control's 45-point mean, and it misses the Target by 4.1 %.

**Reporting-only and unspecified.** Row 4c is a reporting requirement with no
bound; both grades report it. DR-0002 specifies no Stretch for Rows 3b, 3c
and 5a and no Target for Row 5b.

**Margins that narrowed.** Two preserved Targets sit closer to their bound
under `w10`. Row 3a moves from 0.8664 to 1.188 ns against ≤ 1.5 ns. Row 3c
moves from 1.705 to 1.977 ns against ≤ 2.0 ns, which leaves 0.023 ns at the
binding corner `ss_-40c_1.08v`. Row 4b is nearly unchanged. Rows 1, 3b, 4a
and 5b move away from their bounds.

## Basis of every Row 2 value

**Measured** values are the whole-latch transient-noise decision statistic of
DR-0002 Row 2: three rungs per point (0 and ±1.0 mV overdrive), N = 80 trials
per rung, a two-rung probit-slope σ per point, averaged over the named grid.
They carry the injected density, 36.27 nV/√Hz, not the design's own.

**Projections** rescale a measured 45-point mean by an own-density ratio,
mean × S / 36.27. They assume the decision response scales linearly with the
injected amplitude, so that each point's decision bandwidth is unchanged when
the density changes, and they apply one density to all 45 points.

| Value (mV rms) | Design | Grid | Density (nV/√Hz) | Basis |
|---|---|---|---|---|
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
- **1.02035** = 1.09627632 × 33.758 / 36.27. The bandwidth is the control's,
  substituted for `w10`'s. This is the last column of the corrected screen,
  which used the control's 45-point mean for every candidate; only the
  finalist has a measured 45-point mean of its own.
- **1.19114 / 1.05919 / 0.989644** = 1.09627632 × S / 36.27, with S each
  candidate's unrounded TT density in the density table. The bandwidth is the
  control's, held fixed, so these three are not comparable with 0.96930.
- **1.555** = 1.338 × 42.16 / 36.27, from the Phase 1 report. The bandwidth is
  the baseline's own, as measured in its 45-point grade.

**Density derivation.** Each own density S is the reduced model's
input-referred white density, by the Phase 1 method the #498 child used:
ngspice's differential output noise density at 1 MHz divided by the gain
magnitude at 1 Hz. For `w10` at TT (27 °C, 1.20 V), 31.05675 nV/√Hz divided by
0.9199826 V/V gives 33.758 nV/√Hz. The control's TT value is 36.7779 nV/√Hz.
Source: [density table](../../comparator-preamp-noise/reports/20261121-issue498/density.json),
measured at four PVT points with 20 of 20 cells passing
([stored batch](../../comparator-preamp-noise/reports/20261121-issue498-pvt.md)).

**0.96930 is not a verdict.** The ratified statistic is the measured grid
mean, 1.04143 mV rms, which fails. The projection applies the single TT
density to all 45 points, while `w10`'s measured reduced-model density at the
four characterized points spans 27.42 nV/√Hz (sf, −40 °C / 1.32 V) to
41.35 nV/√Hz (ff, 125 °C / 1.08 V), so at ff it is above the 36.27 nV/√Hz
injection. And the reduced model's density is a reportable lower bound, never
a compliance figure.

## Limits of this comparison

- **Capacitance.** Only 1, 2 and 4 fF per side were measured. Saturation and
  the behaviour at other capacitances remain undetermined.
- **Load width.** Widths between 10 and 12 µm have no timing grade. Only
  `w10` has a 45-point grade, and nothing here shows it is the best width.
  The screen places `w10` (1.008 mV rms) below `w12` (1.032 mV rms), a 2.3 %
  difference on the unrounded means, smaller than the ≈ 3 % standard error
  the #497 analysis derives for one 18-point mean at N = 80 per rung.
- **Not an ablation.** `w10` against the baseline differs in bias, latch
  devices and switch. The two grades also came from different toolchains: the
  baseline from klt `0.5.0+ge8ca621a6961` and ngspice 46, `w10` from klt
  `0.9.3.dev2575+g6bd18bbc8637` and ngspice 47, as each grade's Evidence
  section records.
- **Sampling.** 1669 of 3600 samples (baseline) and 3584 of 3600 (`w10`)
  repeat a raw noise draw also seen at another grid point, never within one
  point. Each point's estimate is valid and unbiased, but the points are not
  mutually independent, so each grid mean's sampling error is wider than an
  independent-points estimate.
- **No adoption.** This report makes no recommendation for the Phase 3
  decision record. #476, PR #490 and #481 own the Row 4a adoption and
  implementation path. Any sized candidate implies a layout regeneration and
  a DRC/LVS re-run.

## Provenance

- **Candidate binding.** #497 bound structural candidate netlists,
  [`cadd1f`](../../comparator-integration-capacitance/candidates/cadd1f.spice),
  [`cadd2f`](../../comparator-integration-capacitance/candidates/cadd2f.spice)
  and [`cadd4f`](../../comparator-integration-capacitance/candidates/cadd4f.spice),
  sha256 `e7362662210f…`, `b7782d6f7c2a…` and `f8a53301035e…`. Each is the
  control geometry plus the declared per-side capacitance. Every bench body
  declares the name, path and sha256, and the grader re-reads and re-hashes
  the file. #498 bound geometry overrides on `design/comparator.spice` (sha256
  `b31b936dd78634b2…`): `XM5.w` and `XM6.w` at 4, 8, 10 or 12 µm, with every
  other device at the control's settings, declared in each bench body. The
  baseline and control grades bind the same schematic with the overrides in
  the table above.
- **Batch requests.** Every request ran on the batch fleet
  (`backend: batch`). All Phase 2 requests used `--wait-for-capacity 600`.
  The archived baseline's requests carry no such flag, and the control's
  carry it on every bench except `offset_mc`. Each screen candidate's Row 2
  evidence is three transient-noise requests (TT, FF, SS) whose union covers
  the 18 points exactly once. Each 45-point grade has five per-process
  requests for each Monte-Carlo bench and one for each deterministic bench.
  Batch job ids are in each grade's Evidence section and in each envelope's
  `environment.remote`.
- **Seeds and run counts.** Bench defaults, committed in each request:
  transient noise N = 80 per rung, offset Monte Carlo N = 60 per point, base
  seed 20260916. The seed is recorded only.
- **TRNOISE seed limitation.** ngspice's TRNOISE generator ignores klt's
  per-sample `.options seed=`. Draws are independent within a point but not
  reproducible, and separate batch jobs can share noise streams
  ([klayout-tools#2963](https://github.com/2AMLogic/klayout-tools/issues/2963),
  [klayout-tools#5772](https://github.com/2AMLogic/klayout-tools/issues/5772)).
  The grader's per-point independence checks passed on every screen (18/18)
  and on both grades (45/45).
- **Stored Monte-Carlo evidence.** The Monte-Carlo envelopes are in the
  fleet artifact store, not in git, under hash manifests:
  [#497](../../../manifests/artifacts/klt-corner-verification-20261121-issue497-mc.manifest.json)
  holds the three settings' transient-noise screen envelopes (12 objects,
  28,601,648 B; [summary](20261121-issue497-mc.md)), and
  [#498](../../../manifests/artifacts/klt-corner-verification-20261121-issue498-mc.manifest.json)
  holds the four candidates' screen envelopes and the finalist's offset and
  transient-noise envelopes (27 objects, 69,689,537 B;
  [summary](20261121-issue498-mc.md)). The requests, invocation records and
  bench bodies of every bench, and the deterministic envelopes and the
  finalist's grade, are committed in the campaign directories.

# `sim/comparator-transient-noise-full/`

**Whole-latch transient noise with the regenerative pair's own noise
injected** (issue
[#81](https://github.com/2AMLogic/sg13g2-comparator/issues/81)). This
directory holds the density calibration, its reducer, and the write-up of the
appended record. The runs themselves are the `tn_full_*` benches of the
`klt sim` campaign
[`../klt-corner-verification/campaigns/20261009-issue81/`](../klt-corner-verification/campaigns/20261009-issue81/)
(analysis: `noise_full.md` / `noise_full.json` there, produced by
`python3 sim/run_klt_corner_verification.py noise-full --campaign 20261009-issue81`).

It is **appended evidence**: the earlier record
(`../comparator-transient-noise/records/20260921-154729-41cbc7f`, whose bench
states it injects noise only at the DUT's input pins and is therefore a lower
bound), the DR-0002 Row 2 bound (1.0 mV Target, 0.6 mV Stretch) and the issue
#62 campaign grading are untouched. The result below is reported as
measured against the unchanged bound.

## Where the evidence is

Campaign `20261009-issue81`, client `klt 0.5.0+ge8ca621a6961` (the CI pin),
batch fleet, ngspice-46 on the runner, models `cornerMOSlv.lib` as in the
issue #62 campaign. Per configuration: the body, five per-process requests,
invocations (with the sha256 of the envelope as printed), `attempts.jsonl`.
To keep the repository small the envelopes are committed gzip-compressed
(`<tag>.envelope.json.gz`; decompress to get the exact bytes whose sha256 the
invocation records) and the per-sample `corner.cir` / `ngspice.log` trees as
one `artifacts/<tag>.tar.gz` per request (720 samples each). Nothing was
dropped; `python3 sim/run_klt_corner_verification.py noise-full --campaign
20261009-issue81` reads the `.gz` envelopes directly.

## Result

Row 2 statistic, as DR-0002 defines it: grid-wide mean of the per-point
two-rung probit-slope sigma, 45 points (5 process x 3 supply x 3 temperature),
N = 80 trials per rung, od_x = 1 mV.

| configuration | what is injected | valid points | grid mean sigma | +/- SE of the mean |
|---|---|---|---|---|
| `fe` | input-referred source only (the issue #62 bench, re-run in this campaign) | 45/45 | 1.356 mV | 0.032 |
| `both` | input-referred **plus** regenerative-pair and reset-device sources (complete injection) | 45/45 | **1.305 mV** | 0.029 |
| `int` (1x, internal only) | internal sources only | 0/45 valid: every point saturated (+od_x rung 80/80 high, -od_x rung 0/80) | 95 % upper bound **<= 0.56 mV** per point | n/a |
| `int_x8` (sensitivity) | internal sources only, every density x8 | 45/45 | 1.414 mV | 0.043 |
| `int_x4` (sensitivity) | internal sources only, every density x4 | 42/45 (3 saturated) | 0.730 mV | 0.014 |
| `zero` (negative control) | both source sets present, internal density scaled to 0 | 45/45 | 1.379 mV | 0.034 |

**As measured against the unchanged DR-0002 Row 2 bound: complete injection,
1.305 mV rms: Target (<= 1.0 mV) NOT MET; Stretch (<= 0.6 mV) NOT MET.** The
verdict does not change; the lower-bound caveat on the earlier record is
largely retired (see the split below).

### Regenerative-pair term vs front-end term

At 1x the internal term is too small to produce a probit slope at od_x = 1 mV
(the rungs saturate), so it cannot be read directly. It is measured through
the scaled run instead: every internal density x8 puts the rungs back in the
informative band, and the 1x term is `sigma(8x)/8`.

* **Internal (regenerative pair + reset devices) alone, 1x: 0.177 mV rms**
  (grid mean of 45 points, from `int_x8`). It is a **model-based estimate**:
  scaling a calibrated parallel-current-noise model (see "Density
  calibration"), not a transistor-level noise analysis.
* Linearity of that read-out: `sigma(8x) / (2 sigma(4x))` has grid mean 1.000
  over 42 points (min 0.66, max 1.56, point-level scatter only), so the term
  does scale linearly with the injected amplitude in this range.
* Front end alone: 1.356 mV (`fe`).
* Quadrature prediction of the complete injection,
  `sqrt(fe^2 + int^2)`, grid mean **1.368 mV**, versus **1.305 mV** measured
  (`both`). The difference, 0.06 mV, is about 1.5 standard errors of the
  difference and `both` is not systematically above `fe` (23 of 45 points
  have `both` <= `fe`): the internal term adds roughly
  `sqrt(1.356^2 + 0.177^2) - 1.356 = 0.012 mV` in quadrature, far below this
  campaign's per-point precision (+/- 0.19 mV) and its grid-mean precision
  (+/- 0.03 mV). Point-level "increments" `sqrt(both^2 - fe^2)` printed in
  `noise_full.md` are sampling scatter, not a measurement of the internal term.

In words: in this model the regenerative pair's own channel noise is about
13 % of the front-end sigma in amplitude (about 2 % in power), so the earlier
lower-bound figure was within about 1 % of the complete-injection one. That
conclusion is conditional on the calibration (next section). The verdict
itself does not depend on it: the front-end term alone (1.356 mV) already
exceeds the 1.0 mV Target, and any internal noise only adds to it, so no
calibration error can bring the complete-injection figure below 1.0 mV. What
the calibration does bear on is how much of the earlier lower bound was
missing; the x8 sensitivity run (internal alone 1.41 mV, comparable to the
whole front-end figure) shows that it would take a density error of several x
for the internal term to matter.

### Statistical basis and precision

* **N = 80 per rung** per PVT point (one trial per `klt sim` Monte-Carlo
  sample, mismatch off, so sample-to-sample variation is TRNOISE alone), 3
  rungs (-od_x, 0, +od_x).
* **Seeds: not controllable.** The request records `monte_carlo.seed =
  20260916`, inherited from the issue #62 convention, but ngspice-46's TRNOISE
  generator ignores `setseed` / `rndseed` / `.options seed`
  (`../comparator-transient-noise/README.md` "Seed reproducibility: recorded,
  not achieved"). The seed is recorded, not achieved; precision rests on N,
  not the seed. Raw-noise independence is checked by the Row 2 gate (three raw
  source values per sample, any repeat refuses the point). For `int*`
  configurations, where the front-end source is off and `v(vd0)` is identically
  zero, the probes read the injected internal sources (`v(inz_x0_xm3)`,
  `v(inz_x1_xm3)`) instead; see "Attempts" for why.
* **Per-point precision** (delta method): relative variance of sigma is
  `(var z+ + var z-)/(z+ - z-)^2` with `var z = p(1-p)/(N phi(z)^2)`. For
  `both` the per-point SE is 0.10 to 0.33 mV (mean 0.19 mV, about 15 %). The
  grid-mean SE (0.029 mV) assumes independent points. As for the issue #62
  campaign, samples in different per-process batch jobs may share raw draws
  (the pid-derived-seed fallback, klayout-tools#2963), so the worst case is a
  fully correlated grid, 1.305 +/- 0.19 mV, which is still above 1.0 mV.
* The saturated 1x internal-only points get a one-sided 95 % upper bound
  `sigma <= od_x / PhiInv(0.05^(1/80)) = 0.56 mV` per point, not a value.

### Negative control

`tn_full_zero` places both sets of sources but scales the internal densities
by 0 (`NA = 0`; the hook's own plumbing is in the deck). It must reproduce the
front-end-only configuration. Over the full grid (45 points, 3 rungs each,
135 two-proportion z comparisons against `fe`, same N): |z| > 2 in 5 (about
6.1 expected for identical populations), |z| > 3 in 0; grid mean sigma 1.379
vs 1.356 mV (SEs 0.034, 0.032). It also matches the original DR-0002 record
(1.335 mV) within these errors. The hook off-by-default property is separately
asserted in `sim/harness/tests/test_internal_noise.py` (byte-identical composed
deck when the `tb.json` key is absent).

### Timestep convergence

Nominal corner (tt, 1.20 V, 27 C), `both`, N = 160 per rung, identical
requests except the transient step and max step
(`smoke/timestep-{20p,10p,5p}.*` in the campaign). The TRNOISE source step is
held at `TS = 20 ps` so the density calibration `NA = S/sqrt(2 TS)` is
unchanged; only the solver's step changes. At 5 ps and 10 ps the solver
visits several points per TRNOISE sample interval, which is the situation
the existing deck's comments warn about for timestep-sensitive TRNOISE.

| tran step / max step | sigma (mV) | +/- SE | move vs 20 ps |
|---|---|---|---|
| 20 ps | 1.324 | 0.136 | n/a |
| 10 ps | 1.116 | 0.102 | -1.2 SE |
| 5 ps | 1.414 | 0.154 | +0.4 SE |

No monotonic trend and no move beyond 1.2 standard errors. This is a
convergence check at the stated precision (about 10 %), not a proof of
convergence below it: a drift of less than about 10 % per halving of the step
could hide here. All 480 samples passed klt's resolution gates.

## Density calibration

The hook (`sim/harness/internal_noise.py`, documented in
`sim/dut/README.md` "Optional internal-noise hook") adds, per instance and
device, a white TRNOISE voltage source and a behavioural current source across
the device's drain and source, giving the channel thermal density
`sqrt(4 k T gamma g)` A/rtHz (`NA = S/sqrt(2 TS)`, TS = 20 ps, temperature
tracks the corner via `temper`). White only (`NALPHA = NAMP = 0`), as in the
existing bench's "Why white only"; **1/f is not injected**.

PSP103 OSDI devices have no TRNOISE parameter, hence the parallel source. Each
device has **one stated conductance**, because a StrongARM's bias sweeps
through the whole decision, and is gated by the clock phase in which it
conducts (`evaluate`: x `v(clk)/v(vdd)`; `reset`: x `1 - v(clk)/v(vdd)`).

| devices | role | `g` used | phase | calibration quantity |
|---|---|---|---|---|
| XM3, XM4 | cross-coupled nmos | 0.35 mS | evaluate | time-weighted mean `|gm|`, regeneration-onset window (1 mV < `|v(ln)-v(lp)|` < 100 mV), noise-free transient, symmetrised per pair |
| XM5, XM6 | cross-coupled pmos | 0.063 mS | evaluate | same |
| XM7, XM8 | reset pmos (6 u) | 2.97 mS | reset | triode `gds` at t = 0.9 ns (end of reset) |
| XM9, XM10 | reset pmos (3 u) | 1.51 mS | reset | same |

`gamma = 1` (stated, not derived; long-channel thermal is 2/3, short-channel
devices are commonly 1 or above). The calibration probe is
`calibrate.py` (one noise-free ngspice-46 transient of the campaign's
`tn_full_fe` body with the front end off, +od_x instance; a single-corner
probe, not a grid). Its committed outputs
(`cal_mos_tt_1p20V_27C.json`, `cal_mos_ff_1p32V_125C.json`,
`cal_mos_ss_1p08V_n40C.json`) give the nominal values and two extreme corners:

| pair | nominal tt/1.20 V/27 C | ff/1.32 V/125 C | ss/1.08 V/-40 C |
|---|---|---|---|
| XM3/XM4 `gm` | 0.350 mS | 0.417 mS | 0.279 mS |
| XM5/XM6 `gm` | 0.067 mS | 0.149 mS | 0.007 mS |
| XM7/XM8 `gds` | 2.97 mS | 3.74 mS | 2.38 mS |
| XM9/XM10 `gds` | 1.51 mS | 1.90 mS | 1.21 mS |

The campaign values (0.35, 0.063, 2.97, 1.51 mS) were derived in the first,
interrupted pass of this work; `calibrate.py` reproduces them to the quoted
digits except XM5/XM6, where two otherwise identical probe runs gave 0.063 and
0.067 mS (the windowed pmos `gm` is sensitive to the solver's step sequence at
the 1 mV start-up condition, a 6 % move). The same `g` is used at every PVT
point, as the existing bench uses one input density at every point, instead
of re-calibrating per corner.

**Stated error.** Density is proportional to `sqrt(g)`. The nmos pair
dominates the regeneration noise (its `g` is 5x the pmos pair's). Across the
two extreme corners the nmos-pair `g` spans -20 % to +19 % of nominal
(density -11 % to +9 %); the reset pair spans -20 % to +26 %; the pmos pair
varies by 2x or more but contributes least. The time-weighting choice and
`gamma` are model choices that are not bounded by this table. The `x4` / `x8`
sensitivity runs are the bound on those: a x8 density, 8x the plausible
error, still gives only 1.41 mV with the front end off.

## Attempts, in order

Kept as part of the append-only trail (all in the campaign directory).

1. `tn_full_int` (internal only, 1x) was run for all 5 process sections (all
   45 points, N = 80 each). The Row 2 gates rejected every
   point: with the front-end source off, the raw-draw independence probes
   (`v(vd0)`) are identically 0 in every sample, so "79 samples repeat another
   sample's draw". The envelopes are kept untouched as the record of that
   attempt. The bench was re-defined as `tn_full_int_probed` (probes read the
   injected internal TRNOISE sources) and re-run in full. It is that
   configuration, labelled `int` above, which saturates at 1x.
2. A `tn_full_zero` submission for the `mos_fs` section hung on the batch
   fleet for more than an hour; the client was stopped and the same request
   resubmitted, which completed normally in minutes. No envelope from the
   stopped submission was written. Filed generically as
   [klayout-tools#2978](https://github.com/2AMLogic/klayout-tools/issues/2978).
3. A preflight (`smoke/preflight-both.*`, 1 corner x 4 samples) verified the
   batch path and hierarchical node naming (`x0.x1.ln`) before the grid.

## What this does not establish

* The internal noise is a **model**: white channel-thermal current noise with
  one calibrated conductance per device, gated by phase. It does not include
  1/f noise, gate-resistance or substrate noise, the isolation inverters /
  SR-latch devices (outside the regenerative stage), the tail and input pair
  (the input pair's noise is the front-end term's job), or the bias-dependent
  time variation of `g`.
* The comparison is at the ratified `od_x = 1 mV` and N = 80. The per-point
  precision (about 15 %) is what limits any conclusion about differences
  between configurations at the 1 % level.
* The quadrature split is an inference that independent sources add in power;
  the closure check (prediction 1.368 vs measured 1.305, ~1.5 SE) is
  consistent with it, not a proof.

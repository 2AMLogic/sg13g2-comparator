# Phase 1 completion: measured per-corner front-end density and the two factors of Row 2

**Row 2 characterization.** The four-point batch separates measured
front-end density from effective decision bandwidth for three designs.
The single-PVT run gives a nominal density for every #92 finalist.
Both use the archived Row 2 grades, whose injection was 36.27 nV/√Hz.
[Phase 1 scope](https://github.com/2AMLogic/sg13g2-comparator/issues/477)

**Provenance.** Submitted 2026-11-21 with `--wait-for-capacity 600` from a
dispatch worker with fleet credentials; four jobs (one per PVT point, first
three parameter rows of [`nominal.request.json`](nominal.request.json)):
`klt-sim-49cc30bd3ebd` (tt), `klt-sim-7b858f09cce5` (sf),
`klt-sim-c25da2cb106a` (ff), `klt-sim-2b341c088d53` (fs). Runner klt 0.9.0,
ngspice 47, PSP103 OSDI preloaded from the runner image. 12 of 12 cells
`pass`. All raw bytes — requests, decks, per-cell ngspice logs, engine
reports, receipts — are in the artifact store:
[`reports/20261121-issue477-pvt.md`](../20261121-issue477-pvt.md)
(manifest `manifests/artifacts/comparator-preamp-noise-20261121-issue477-pvt.manifest.json`,
63 objects, hash-verified).

**Spot-check against the published record (the Phase 1 test plan).** The
committed 12 µm/0.34 µm row reproduces
[`records/20260916-113303-180cca7`](../../records/20260916-113303-180cca7.md)
at all four points, to the printed digits: output density ÷ DC gain gives
36.27 / 29.02 / 47.13 / 29.53 nV/√Hz at tt / sf / ff / fs, against the
record's `white_nv_rthz / av_dc` of 36.27 / 29.02 / 47.13 / 29.53. The
measurement convention is unchanged, so the candidate rows below are on the
same footing as the ratified calibration.

## The audit answer, restated

All 30 `transient_noise.mos_*.request.json` files of
[`campaigns/20261009-issue92`](../../../klt-corner-verification/campaigns/20261009-issue92/)
and
[`campaigns/20261115-issue92-bias`](../../../klt-corner-verification/campaigns/20261115-issue92-bias/)
name an adjacent `transient_noise.body.spice`, and all six finalist bodies
drive the three rung sources with `trnoise(5.735e-3 2e-11 0 0)` — the
unchanged one-sided 36.27 nV/√Hz at every PVT point. **Every #92 Row 2
number, including the 1.096 mV best, is a pure bandwidth measurement at a
fixed injected density.** The existing front-end / internal split from
[`comparator-transient-noise-full`](../../../comparator-transient-noise-full/README.md)
is cited, not re-run: front end alone 1.356 mV, complete injection 1.305 mV,
internal-only ≈ 0.177 mV at 1× (≈ 2 % of the power).

## Front-end's own input-referred white density, S (nV/√Hz)

`S = white_out(1 MHz) / |Aᵥ(1 Hz)|` per design per point, from the stored
batch:

| PVT point | 12 µm committed | 8 µm baseline | `ib10_sw20lat6` |
|---|---:|---:|---:|
| `sf_-40c_1.32v` | 29.02 | 33.98 | 29.72 |
| `tt_27c_1.20v` | 36.27 | 42.16 | 36.78 |
| `ff_125c_1.08v` | 47.13 | 54.53 | 45.61 |
| `fs_-40c_1.20v` | 29.53 | 34.50 | 30.52 |

Narrowing only the input pair from 12 µm to 8 µm raises the input-referred
density by 16–17 % at each of these points. At TT the gain falls from 1.639
to 1.434 V/V while the output density rises from 59.46 to 60.45 nV/√Hz.
Dividing output density by gain gives 36.27 and 42.16 nV/√Hz at the
input, a 16.2 % increase.

## Per-device power shares (percent of output noise power at 1 MHz)

Each cell is **input pair (XM1A+XM2A) / diode-connected loads (XM5A+XM6A)**.
The tail device XMTA, the tail switch XMSWA and the bias mirror XMBA carry
**0.0000 %** at every cell — their noise reaches both outputs in phase and
cancels in `v(aop,aon)`. Measured power closure (sum of all seven device
powers ÷ `white_out²`) is 100.00 % at every cell, so these shares account
for the whole density:

| PVT point | 12 µm committed | 8 µm baseline | `ib10_sw20lat6` |
|---|---:|---:|---:|
| `sf_-40c_1.32v` | 10.3 / 89.7 | 11.3 / 88.7 | 14.6 / 85.4 |
| `tt_27c_1.20v` | 9.1 / 90.9 | 10.0 / 90.0 | 13.3 / 86.7 |
| `ff_125c_1.08v` | 7.6 / 92.4 | 8.3 / 91.7 | 12.3 / 87.7 |
| `fs_-40c_1.20v` | 9.6 / 90.4 | 10.4 / 89.6 | 13.5 / 86.5 |

**XM5A/XM6A contribute 85.4–92.4 % of differential output noise power** in
these 12 cells. The input pair contributes 7.6–14.6 %. If its noise alone
were removed with gain and every other contribution held fixed, the fractional
amplitude reduction would be `1 − √(1 − f)` for power fraction `f`, or
3.9–7.6 %. Resizing the pair also changes gain and can change how other
sources reach the output. Its output power share therefore cannot bound the
change in input-referred density from resizing.

## The bandwidth factor: sigma / ENBW from the committed #92 campaigns

Each cell is **bench σ (mV rms) / ENBW = (σ/S₀)² (GHz)** with S₀ =
36.27 nV/√Hz, recomputed for this report from the committed
`grading.json` `monte_carlo_per_point[].sigma` values (45 valid points per
design, N = 80 per rung; no new transient-noise grid was run):

| PVT point | 12 µm committed | 8 µm baseline | `ib10_sw20lat6` |
|---|---:|---:|---:|
| `sf_-40c_1.32v` | 0.846 / 0.544 | 1.024 / 0.796 | 1.059 / 0.852 |
| `tt_27c_1.20v` | 1.361 / 1.408 | 1.107 / 0.932 | 1.157 / 1.017 |
| `ff_125c_1.08v` | 1.843 / 2.582 | 1.764 / 2.366 | 1.065 / 0.862 |
| `fs_-40c_1.20v` | 1.069 / 0.868 | 1.673 / 2.127 | 1.438 / 1.571 |
| **45-point bench grid mean σ** | **1.289** | **1.338** | **1.096** |

## Row 2 as density × bandwidth (characterization)

σ_char = S_own × √ENBW per design per point, in mV rms — what the compliance
bench would have read had it injected each design's own measured density
instead of the fixed 36.27 nV/√Hz, assuming the decision response scales
linearly with source amplitude:

| PVT point | 12 µm committed | 8 µm baseline | `ib10_sw20lat6` |
|---|---:|---:|---:|
| `sf_-40c_1.32v` | 0.677 | 0.959 | 0.867 |
| `tt_27c_1.20v` | 1.361 | 1.287 | 1.173 |
| `ff_125c_1.08v` | 2.395 | 2.653 | 1.339 |
| `fs_-40c_1.20v` | 0.870 | 1.591 | 1.210 |
| **four-point mean** | **1.326** | **1.622** | **1.147** |

The committed-design column reproduces the projection in the README above
(0.677 / 1.361 / 2.395 / 0.870 mV), which was derived from the published
record's densities — an independent cross-check, since this batch measured
them again. These four-point means characterize the selected bounding points.
The ratified Target uses the 45-point grid mean.

## Nominal recalibration for the six #92 finalists

At TT, 27 °C, 1.20 V, the full nominal request measures the committed
control and all six finalists. Each design below links to its archived
Row 2 grade. The projected mean is `grid_mean × S(TT) / 36.27`, holding
that design's TT density constant across its 45 decision bandwidths.
Calculations use the unrounded measurements. The stored nominal report
contains `white_out` and `gain_dc` for all seven parameter rows in table
order. [Nominal run and stored evidence](../20261120-issue477-nominal.md)

| Design / grading record | S(TT) (nV/√Hz) | 45-point bench mean (mV) | Nominally recalibrated mean (mV) |
|---|---:|---:|---:|
| [12 µm committed](../../../klt-corner-verification/campaigns/20261009-d73a9ac/grading.json) | 36.27 | 1.289 | 1.289 |
| [`w8_l034`](../../../klt-corner-verification/campaigns/20261009-issue92/full_w8_l034/grading.json) | 42.16 | 1.338 | 1.555 |
| [`ib10_sw20lat6`](../../../klt-corner-verification/campaigns/20261115-issue92-bias/full_ib10_sw20lat6/grading.json) | 36.78 | 1.096 | 1.112 |
| [`w6_l034`](../../../klt-corner-verification/campaigns/20261009-issue92/full_w6_l034/grading.json) | 47.10 | 1.333 | 1.731 |
| [`w8_l020`](../../../klt-corner-verification/campaigns/20261009-issue92/full_w8_l020/grading.json) | 38.94 | 1.265 | 1.358 |
| [`ib10_sw20`](../../../klt-corner-verification/campaigns/20261115-issue92-bias/full_ib10_sw20/grading.json) | 41.45 | 1.192 | 1.363 |
| [`ib12p5_sw20`](../../../klt-corner-verification/campaigns/20261115-issue92-bias/full_ib12p5_sw20/grading.json) | 41.58 | 1.255 | 1.439 |

## Implications for the 1.0 mV Target

The #92 bench held the injection fixed, so its σ differences measure
differences in effective decision bandwidth. For example, at FF the
bandwidth falls from 2.582 GHz (committed) to 0.862 GHz (`ib10_sw20lat6`).
The finalist's own TT density of 36.78 nV/√Hz is 1.4 % above the fixed
36.27 nV/√Hz injection. Its FF density of 45.61 nV/√Hz is 25.8 % above
that injection and 3.2 % below the committed design's 47.13 nV/√Hz at FF.

`ib10_sw20lat6` retains the lowest projected mean of the six finalists
when each uses its own TT density (1.112 mV). The 8 µm baseline proposed
in #476 goes from 1.338 to 1.555 mV. For #479, either lower input-referred
density, narrower effective decision bandwidth, or a combination can lower
Row 2. The measured load share identifies the largest direct noise source.
The measured width dependence also makes gain relevant when comparing designs.

For `ib10_sw20lat6`, let `r = 1.0 mV / starting mean`. Reaching 1.0 mV
at fixed bandwidth requires multiplying every point's density by `r`.
At fixed density, scaling each bandwidth by `r²` gives the same uniform
reduction in σ. The table uses the displayed starting means.

| Starting mean and density reference | Starting σ (mV) | Density reduction at fixed bandwidth | Bandwidth multiplier at fixed density | Bandwidth reduction |
|---|---:|---:|---:|---:|
| 45-point bench, fixed 36.27 nV/√Hz injection | 1.096 | 8.8 % (to 33.09 nV/√Hz) | 0.832 | 16.8 % |
| 45-point nominal recalibration, 36.78 nV/√Hz at TT | 1.112 | 10.1 % | 0.809 | 19.1 % |
| Four bounding points, each at its measured density | 1.147 | 12.8 % at each point | 0.760 | 24.0 % |

The last row scales a four-point characterization mean. Establishing
compliance requires the grid-wide statistic specified for Row 2.

## Tooling note

ngspice's ranked contributor list prints duplicate PSP103 leaf names, filed
upstream as
[klayout-tools #6978](https://github.com/2AMLogic/klayout-tools/issues/6978).
This request reads ngspice's native device-total vectors
(`onoise_n.<instance>...`) instead, so the shares above do not depend on
that issue being fixed.

## Reproduce

For the 12 design/PVT cells, use the bounded batch invocation from this
directory on a worker with batch-submission credentials and artifact-broker
access. [Batch invocation](README.md#measuring-the-candidate-density) ·
[Four-point stored evidence](../20261121-issue477-pvt.md)

For the seven-row nominal table, use the full single-PVT request and the
linked grading records above. The stored nominal report gives the exact
parameter set and measurements for each row. [Nominal reproduction and stored evidence](../20261120-issue477-nominal.md)

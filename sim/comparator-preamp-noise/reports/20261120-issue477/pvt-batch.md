# Phase 1 completion: measured per-corner front-end density and the two factors of Row 2

**Characterization, not a compliance figure.** This addendum completes the
Phase 1 evidence for [#477](https://github.com/2AMLogic/sg13g2-comparator/issues/477)
by running the bounded four-point `klt sim` batch invocation documented above
("Measuring the candidate density") on the batch fleet and deriving the split
the issue asks for. The compliance bench, its injected 36.27 nV/√Hz density,
the DUT files and the grader are untouched; nothing already committed under
`sim/` was modified.

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

The 8 µm/0.34 µm baseline's own density is 16–17 % higher than the
committed design's at every point (narrowing the pair from 12 µm to 8 µm
costs transconductance faster than it cuts pair noise). `ib10_sw20lat6` —
same 8 µm pair — sits within ±3.4 % of the committed design at every point
(+1.4 % at tt, −3.2 % at ff): its 6 µm latch loads and halved bias leave the
front-end density it presents essentially the committed one.

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

**The load devices, not the input pair, own ~85–92 % of the front-end noise
power at every design and every point.** Even the doubled 6 µm loads of
`ib10_sw20lat6` leave the load share at 85–88 %. The input pair — the only
devices the #92 W/L study swept — holds 8–15 % of the power, i.e. at most a
±3 % amplitude lever even if eliminated outright.

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
them again. The equivalent nominal recalibration (grid mean ×
S_own(tt)/S₀) gives **1.289 mV** (committed, unchanged by construction),
**1.555 mV** (8 µm baseline) and **1.112 mV** (`ib10_sw20lat6`).

## What this says

**Which factor did #92 move, and which factor must a design change move?**

- The #92 geometry studies moved only the **bandwidth** factor.
  `ib10_sw20lat6` reached 1.096 mV by narrowing its effective decision
  bandwidth — ENBW at `ff_125c_1.08v` falls from 2.582 GHz (committed) to
  0.862 GHz — while its own density stayed within +1.4 % of the injected
  one. Its improvement survives the per-candidate correction (1.112 mV
  nominal recal): it is real, and it is a bandwidth effect.
- The 8 µm/0.34 µm baseline (the [#476](https://github.com/2AMLogic/sg13g2-comparator/issues/476)
  adoption candidate) is **worse than its bench number**: its own density is
  16–17 % higher, so a per-candidate calibration turns its 1.338 mV bench
  mean into ≈ 1.555 mV. Any Row 2 argument built on that baseline should
  carry its own density.
- The **density** factor cannot be moved by input-pair geometry: the pair
  holds 8–15 % of the front-end noise power (a ≤ ±3 % amplitude lever),
  which is exactly why the #92 W/L sweep spanned only 1.27–1.34 mV. The
  density term to attack is the load/reset device pair XM5A/XM6A — the
  reduced-model counterparts of the latch loads XM5/XM6 — with 85–92 % of
  the power at every measured cell. Candidate classes that change S at all
  must change those devices or add elements ahead of the latch (the #479
  candidates 1 and 3 both do).
- **Neither factor closes Row 2 as measured.** The best design's
  characterization mean (1.147 mV over the four bounding points, 1.112 mV
  nominal recal) still misses the 1.0 mV Target. Reaching 1.0 mV from
  `ib10_sw20lat6` needs either a further ~9 % bandwidth narrowing at fixed
  density (× 0.832 on every point) or ~10 % off the density at fixed
  bandwidth (33.09 nV/√Hz) — and the density route must find that 10 % in
  the load devices, since the pair and tail terms cannot supply it.

This is characterization evidence for the #479 candidate study and the #480
drafting-only record; it is not a compliance verdict and relaxes nothing.

## Tooling note

ngspice's ranked contributor list prints duplicate PSP103 leaf names, filed
upstream as
[klayout-tools #6978](https://github.com/2AMLogic/klayout-tools/issues/6978).
This request reads ngspice's native device-total vectors
(`onoise_n.<instance>...`) instead, so the shares above do not depend on
that issue being fixed.

## Reproduce

Run the invocation in [`README.md`](README.md) § "Measuring the candidate
density" from this directory on a worker with batch-submission credentials
and artifact-broker access; the stored run is
[`reports/20261121-issue477-pvt.md`](../20261121-issue477-pvt.md). Every
table above is arithmetic on those stored bytes plus the committed `#92`
grading files: S = `white_out/gain_dc`; shares = device power ÷
`white_out²`; ENBW = (σ/36.27 nV)²; σ_char = S·√ENBW; nominal recal =
grid mean × S(tt)/36.27.

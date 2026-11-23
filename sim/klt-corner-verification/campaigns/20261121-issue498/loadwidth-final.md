# Matched PMOS load-width screen -- campaign `20261121-issue498` (issue #498)

The study varies XM5/XM6 and their reduced-model counterparts XM5A/XM6A. XM3/XM4, the input pair, the switch and the 10 µA bias use the archived `ib10_sw20lat6` settings.

The 6 µm control (`20261115-issue92-bias/full_ib10_sw20lat6`) averages 1.053 mV rms across its 18 screening points (18/18 valid) and 1.096 mV rms across all 45 points at 36.27 nV/rtHz.

## Row 2 screen (transient noise, 18 points, N = 80 per rung, unchanged bench)

Each candidate has three requests (TT, FF, SS) covering 18 points. The screen averages the per-point probit-slope sigmas at 36.27 nV/rtHz. The last column projects each candidate's TT density using the 6 µm control's 45-point mean.

| candidate | loads | valid pts | 18-pt mean [mV rms] | vs control | own S(TT) [nV/rtHz] | 45-pt TT projection at fixed 6 µm control bandwidth [mV rms] |
|---|---|---|---|---|---|---|
| w4 | 4u | 18/18 | 1.076 | x1.022 | 39.41 | 1.19114 |
| w8 | 8u | 18/18 | 1.065 | x1.012 | 35.04 | 1.05919 |
| w10 | 10u | 18/18 | 1.008 | x0.958 | 33.76 | 1.02035 |
| w12 | 12u | 18/18 | 1.032 | x0.980 | 32.74 | 0.989644 |

## Screen decisions

| Candidate | Decision | Evidence |
|---|---|---|
| w4 | Eliminated | Row 2 screen mean 1.076 mV does not improve on the control's 1.053 mV at the same injection (36.27 nV/rtHz) |
| w8 | Eliminated | Row 2 screen mean 1.065 mV does not improve on the control's 1.053 mV at the same injection (36.27 nV/rtHz) |
| w10 | Advanced | Lowest eligible 18-point mean |
| w12 | Eliminated | Row 3c gate td01_worst = 2.044 > Target 2 (ss_-40c_1.08v) |

## Full-grid Row 2

- [w10 grade](full_w10/grading.json) — 45-point mean at 36.27 nV/rtHz **1.04143 mV rms** (Target **FAIL**). At the measured bandwidth and 33.758 nV/rtHz, the TT projection is **0.96930 mV rms**.
- w4: full-grid rows UNMEASURED.
- w8: full-grid rows UNMEASURED.
- w12: full-grid rows UNMEASURED.

## Disclosures

Monte-Carlo seeds and run counts are the bench defaults committed in each request (transient noise: N = 80 per rung, base seed 20260916; the seed is recorded only). ngspice's TRNOISE source seed limitation applies as in every campaign run: draws are independent within a point but not reproducible, and separate batch jobs can share noise streams ([klayout-tools#5772](https://github.com/2AMLogic/klayout-tools/issues/5772), [klayout-tools#2963](https://github.com/2AMLogic/klayout-tools/issues/2963)). Campaign requests target the batch fleet. Candidate densities come from the reduced-model characterization (Phase 1 method: output white density at 1 MHz divided by |Av(1 Hz)|). The screen table uses the control's 45-point mean and bandwidth. Each graded finalist's TT projection uses its own measured 45-point mean.

[Reduced-model densities and PVT coverage](../../../comparator-preamp-noise/reports/20261121-issue498/density.json)

[Stored Monte Carlo evidence](../20261121-issue498-mc.md)

[SHA-256 manifest](../../../../manifests/artifacts/klt-corner-verification-20261121-issue498-mc.manifest.json)

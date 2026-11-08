# Extracted whole-latch Monte Carlo roll-up, per point (issue #61)

Derived only from the committed per-point reports named in the last column; nothing was simulated for this file and nothing ran locally. Regenerate with `python3 sim/comparator-pex/make_mc_rollup.py --check sim/comparator-pex/reports/mc-rollup.20261101-c`.

## Reading rules

- Each row is a Monte Carlo sigma **at one PVT point**. It is not a corner-matrix result and not a sigma of the grid. 13 offset and 10 noise points have data, out of 45 grid points.
- Offset sigma is the sample (N-1) sigma over samples with a value on both sides, quantized by the 3 mV staircase, with about 9 % relative uncertainty at N = 60. A ratio near 1 establishes no difference.
- Noise is the probit-fit sigma of the committed report; a fit with a clamped rung is rough and is marked. About 13 % 1-sigma scatter at N = 80.
- The DR-0002 Targets are quoted unchanged (offset 3 sigma <= 15 mV, noise <= 1.0 mV rms). The `within` column only restates that comparison for this point; it is **not** a DR-0002 verdict, because the rows require every grid point (offset) or the ratified compliance statistic (noise) and neither is complete here.

## Offset (DR-0002 Row 1), N = 60 requested per point

| point | compared | sigma sch | sigma ext | ratio | 3 sigma sch | 3 sigma ext | both <= 15 mV | envelope | file |
|---|---|---|---|---|---|---|---|---|---|
| ff/-40C/1.32V | 57/60 | 2.86 | 3.34 | 1.16 | 8.59 | 10.01 | yes | error | `batch-mc-offset-ff-40c-n60.20261031.json` |
| ff/125C/1.32V | 45/60 | 3.11 | 3.42 | 1.10 | 9.33 | 10.25 | yes | error | `batch-mc-offset-ff-125c-132v-n60.20261101.json` |
| ff/27C/1.32V | 60/60 | 2.93 | 3.40 | 1.16 | 8.78 | 10.19 | yes | pass | `batch-mc-offset-ff-27c-132v-n60.20261101.json` |
| fs/27C/1.20V | 57/60 | 3.02 | 3.23 | 1.07 | 9.05 | 9.69 | yes | error | `batch-mc-offset-fs-27c-n60.20261031.json` |
| sf/27C/1.20V | 60/60 | 2.99 | 3.41 | 1.14 | 8.97 | 10.23 | yes | None | `batch-mc-offset-sf-27c-n60.20261031-b.json` |
| ss/-40C/1.08V | 60/60 | 3.29 | 3.36 | 1.02 | 9.87 | 10.09 | yes | pass | `batch-mc-offset-ss-m40c-108v-n60.20261101.json` |
| ss/125C/1.08V | 60/60 | 3.42 | 3.74 | 1.09 | 10.26 | 11.23 | yes | pass | `batch-mc-offset-ss125-n60.20261031.json` |
| ss/27C/1.08V | 60/60 | 3.23 | 3.36 | 1.04 | 9.70 | 10.09 | yes | pass | `batch-mc-offset-ss-27c-108v-n60.20261101.json` |
| tt/-40C/1.20V | 60/60 | 3.03 | 3.37 | 1.11 | 9.09 | 10.11 | yes | pass | `batch-mc-offset-tt-m40c-n60.20261101.json` |
| tt/125C/1.20V | 60/60 | 3.23 | 3.45 | 1.07 | 9.68 | 10.34 | yes | pass | `batch-mc-offset-tt-125c-n60.20261101.json` |
| tt/27C/1.08V | 57/60 | 3.29 | 3.50 | 1.06 | 9.88 | 10.49 | yes | error | `batch-mc-offset-tt-108v-n60.20261101.json` |
| tt/27C/1.20V | 60/60 | 3.03 | 3.41 | 1.13 | 9.09 | 10.24 | yes | pass | `batch-mc-offset-nominal-n60.20261031.json` |
| tt/27C/1.32V | 60/60 | 2.93 | 3.40 | 1.16 | 8.78 | 10.19 | yes | None | `batch-mc-offset-tt-132v-n60.20261031.json` |

## Transient noise (DR-0002 Row 2), N = 80 trials per rung requested

| point | trials compared | sigma sch | sigma ext | clamped rungs ext | both <= 1.0 mV | envelope | file |
|---|---|---|---|---|---|---|---|
| ff/-40C/1.32V | 80/80 | 0.89 | 0.65 | d_plus | yes | pass | `batch-mc-noise-ff-40c-n80.20261031.json` |
| ff/125C/1.32V | 77/80 | 0.79 | 1.19 | d_plus | NO | error | `batch-mc-noise-ff-125c-132v-n80.20261101.json` |
| fs/27C/1.20V | 77/80 | 0.86 | 0.58 | d_plus | yes | error | `batch-mc-noise-fs-27c-n80.20261031.json` |
| sf/27C/1.20V | 80/80 | 0.91 | 0.60 | d_plus | yes | pass | `batch-mc-noise-sf-27c-n80.20261031.json` |
| ss/-40C/1.08V | 80/80 | 0.97 | 0.62 | d_zero, d_minus | yes | pass | `batch-mc-noise-ss-m40c-108v-n80.20261101.json` |
| ss/125C/1.08V | 77/80 | - | - | - | no fit | - | `batch-mc-noise-ss125-n80.20261031.json` |
| ss/27C/1.08V | 76/80 | 1.03 | 0.51 | none | NO | error | `batch-mc-noise-ss-27c-108v-n80.20261101.json` |
| tt/-40C/1.20V | 80/80 | 0.78 | 0.70 | d_plus | yes | pass | `batch-mc-noise-tt-m40c-n80.20261101.json` |
| tt/125C/1.20V | 77/80 | 0.96 | 1.38 | d_plus | NO | error | `batch-mc-noise-tt-125c-n80.20261101.json` |
| tt/27C/1.08V | 78/80 | 0.89 | 0.88 | none | yes | error | `batch-mc-noise-tt-108v-n80.20261101.json` |
| tt/27C/1.20V | 80/80 | - | - | - | no fit | - | `batch-mc-noise-nominal-n80.20261031.json` |
| tt/27C/1.32V | 77/80 | 0.92 | 0.72 | none | yes | error | `batch-mc-noise-tt-132v-n80.20261101.json` |

Superseded offset files for a point that has a better record (kept, not edited): `batch-mc-offset-sf-27c-n60.20261031.json` (sf/27C/1.20V, 0 compared)

## Not established

The remaining grid points, any DR-0002 offset or noise verdict, `td_c` (no extracted value at any corner; see `batch-extracted-grid.regeneration.20261031.md`), and the item-7 citation: `klt signoff` accepts only a `klt pex` report for item 7, and the committed one is the single-corner run. Item 7 stays `unmet`.

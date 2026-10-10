# klt-vs-record whole-latch offset: significance of the +13 % shift (issue #82)

Outcome: **(a) consistent with sampling error.** No new simulation was run;
this is a re-analysis of committed per-draw evidence.

Compared (DR-0002 Row 1 statistic, quantization-corrected 3 sigma, N = 60 per
PVT point, 45-point grid = 5 process x 3 temperature x 3 supply, `mos_<p>_mismatch`
sections, DUT `comparator-dr0001`):

* record `sim/comparator-offset-transient-mc` `20260917-060858-ea40b57`
* klt campaign `sim/klt-corner-verification/campaigns/20261009-d73a9ac`

Reproduce: `python3 -I sim/klt-vs-record-offset-significance/analyze.py`
(numpy only; stdout is committed as `analysis_output.txt`).

## What it reproduces

Grid-mean 3 sigma 8.404 mV (record) vs 9.511 mV (klt), ratio of means 1.132,
per-point ratio 1.136 +/- 0.171. The issue's naive SE (0.171/sqrt(45) = 2.5 %,
5.4 sigma) assumes 45 independent ratios.

## Why the naive SE is wrong (measured from the per-draw values)

* Record: one `setseed 20260916` stream is used at every PVT point. The 60
  per-draw offsets are correlated 0.947 on average between points (min 0.856;
  44 points, see note). The 45 sigmas are one 60-draw realization seen 45 times:
  effective N = 60, relative SE of the grid mean ~ 9.2 % (bootstrap with a
  common resample index; analytic 1/sqrt(2(N-1)) = 9.2 %).
* klt: the per-sample `mismatch_seed` depends on (supply, temperature, sample
  index) but **not on the process section**. The 5 process sections at a given
  (temp, vdd) reuse the same 60 seeds (draw correlation 0.983 within such a
  group, -0.005 across groups; 540 unique seeds in 2700 corners). klt therefore
  has 9 independent seed streams, not 45, so its own grid-mean SE is ~ 3.3 %
  (not 1.4 %). This is a finding about klt's seed contract worth knowing: a
  klt process axis is not an independent-draw axis.

## Corrected significance

Difference of grid means 1.106 mV, combined SE 0.83 mV -> **1.33 sigma**
(log-ratio form: 1.25 sigma; analytic cross-check 1.27 sigma; two-sided
p ~ 0.21). Within the ~2 sigma threshold in the issue, so the shift is
consistent with sampling error; no mechanism (issue candidates 1 to 3) is
indicated and steps 2 and 3 (replicates, per-draw parameter spread) were not
run. They would only be warranted if an independent N = 200 pair at one corner
(DR-0005 form) later disagreed.

Caveats: one record point (`sf_mismatch_125c_1.32v`) has only 59 of 60 per-draw
`vos =` prints in its committed log (the log's own `m_n_samples` is 60); its
reported 3 sigma is used in the means and it is left out of the 44-point
per-draw matrices (correlation, bootstrap). A 1.3 sigma result does not prove
the two methods are identical: it says this comparison cannot distinguish a
0 % from a ~13 % method difference; the expected scatter of the ratio of grid
means is ~ 10 %. Verdicts (Target met 45/45, Stretch not met) are unchanged.
Neither basis is ratified or relaxed here; DR-0002 is untouched.

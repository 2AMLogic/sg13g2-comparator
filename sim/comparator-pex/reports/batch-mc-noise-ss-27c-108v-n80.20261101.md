# Whole-latch transient-noise Monte Carlo, N = 80 at ss / 27 C / 1.08 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1012+g31b24f439f3f` (development build, **not** a released client); fleet runner compatible (runner
`klt 0.8.0`). Same command shape as `batch-mc-noise-ss-m40c-108v-n80.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json --envelope-out`,
layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.json` with `monte_carlo.n` 80, process `ss` (plain `mos_ss`, **no mismatch models**, as the schematic
bench), 27 C, vdd 1.08 V, in an untracked throwaway copy (committed requests unchanged; the copy's `netlist` path was made
absolute). Extracted netlist sha256 `b313a02d...d51d47` (identical to the other points). Data:
`batch-mc-noise-ss-27c-108v-n80.20261101.json` (all 80 trials, both sides; the full envelope is not committed).

## What went wrong in the run

As for the offset point at the same corner (`batch-mc-offset-ss-27c-108v-n60.20261101.md`), earlier `--submit-only`
invocations were cut off by limits on my own session before a manifest was written. Shard jobs from those were already
submitted, were not identified or collected, and are not part of this result. Only the final complete submission is
reported.

In that submission **four extracted trials (`mc13`, `mc46`, `mc53`, `mc76`) have no value**: their batch jobs ended with
`timestep_too_small` ("ngspice aborted the transient: timestep too small at time = 1e-09 s ... `trnoise()` combined with
a non-DC control source", a documented ngspice limitation), so 12 rows are `error` (228 passed, 0 failed). Those trials
are excluded from both sides below, so the point is **76 of 80**, kept as a finding. I did not re-run them.

## Statistical basis

One PVT point (slow process, 27 C, **1.08 V**); **76 of 80** trials compared; rungs at differential overdrive 0 /
+1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded but **does not
govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible. One-point
result, not a corner-matrix or 45-point result, and not a DR-0002 verdict.

## Result (envelope `status: error`; 228 rows passed, 0 failed, 12 errored)

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 76:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 38 / 76 = 0.500 (0.390 .. 0.610) | 44 / 76 = 0.579 (0.467 .. 0.684) |
| +1.0 mV (`d_plus`) | 67 / 76 = 0.882 (0.790 .. 0.936) | 73 / 76 = 0.961 (0.890 .. 0.986) |
| -1.0 mV (`d_minus`) | 16 / 76 = 0.211 (0.134 .. 0.315) | 2 / 76 = 0.026 (0.007 .. 0.091) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs (grid search, theta step 1 uV, sigma
step 0.01 mV; same model as the other noise points; the fit script was a throwaway and is not committed). No rung is
clamped on either side.

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 1.03 mV | -0.08 mV |
| extracted | 0.51 mV | -0.09 mV |

- The **schematic** fit sigma at this point is 1.03 mV, slightly above the ratified 1.0 mV rms Target quoted in DR-0002
  Row 2. This restates a comparison at one point with about 13 % 1-sigma scatter at this N; it is not a Row 2 verdict,
  and nothing was relaxed.
- The extracted fit sigma (0.51 mV) is about half the schematic's. Static thresholds agree (about -0.1 mV). The Wilson
  intervals overlap on `d_zero` and `d_plus` and do not overlap on `d_minus`. With three rungs and two fitted
  parameters, I do not claim the extracted noise is lower.
- In 9 extracted trials the sampled output at 5 ns is intermediate (0.05 .. 0.95 of vdd): 7 in `d_zero` and 2 in
  `d_minus`; they are counted by the 0.5 threshold, so those rung counts depend on the sampling time. No schematic trial
  and no `d_plus` extracted trial is intermediate.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs: extracted 38 nmos / 26
  pmos instances vs 12 / 12 in the schematic).
- I have not established whether any difference is layout parasitics, the extraction model, or the plain-`mos_ss` bench.

## Not established / still open

The remaining noise and offset grid points, any DR-0002 offset or noise verdict, `td_c`, and the item-7 citation, hash
and regenerated signoff report. Item 7 stays `unmet`.

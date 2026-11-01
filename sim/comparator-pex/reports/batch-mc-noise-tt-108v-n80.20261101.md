# Whole-latch transient-noise Monte Carlo, N = 80 at tt / 27 C / 1.08 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev981+g83e562f043be` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-noise-tt-132v-n80.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and corners changed to process `tt` (plain `mos_tt`, **no
mismatch models**, as the schematic bench), 27 C, vdd 1.08 V, in an untracked throwaway copy (committed requests
unchanged). Extracted netlist sha256 `b313a02d...d51d47` (identical to the other points, same committed GDS). Data:
`batch-mc-noise-tt-108v-n80.20261101.json` (the 78 compared trials plus the 2 errored ones, both sides, three rungs; the
full envelope is not committed).

## What went wrong in the run

My first `--submit-only` was stopped by a 590 s `timeout` I put around it (my choice, not a fleet fault). A second
identical invocation into the same output directory completed (exit 0, 2 legs, manifest `complete: true`). Jobs from the
stopped invocation that were not recorded in the manifest were not identified or collected and are not part of this
result. The single `--attach` then ran about 50 min; the schematic-side shard `klt-sim-b46075ede4e5` (samples 78, 79)
**never started** (no `status.json` after 1800 s, code `batch_poll_timeout`), so those two trials have no schematic
value. Envelope `status: error` (234 rows passed, 0 failed, 6 errored); samples 78 and 79 are excluded from both sides so
the two sides use the same trials. The shard was not re-run. This is a fleet-capacity finding, not a simulation result.

## Statistical basis

One PVT point (typical process, 27 C, **low supply 1.08 V**); **78 of 80** trials compared; rungs at differential
overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded
but **does not govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible
and samples in different jobs may share a noise stream. One-point result, not a corner-matrix or 45-point result, and
not a DR-0002 verdict.

## Result

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 78:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 38 / 78 = 0.487 (0.379 .. 0.596) | 58 / 78 = 0.744 (0.637 .. 0.827) |
| +1.0 mV (`d_plus`) | 72 / 78 = 0.923 (0.842 .. 0.964) | 76 / 78 = 0.974 (0.911 .. 0.993) |
| -1.0 mV (`d_minus`) | 14 / 78 = 0.179 (0.110 .. 0.279) | 25 / 78 = 0.321 (0.227 .. 0.430) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs (no rung at 0 or n, nothing clamped),
the same routine as the other points (it reproduces the committed 1.32 V fit to 8 digits):

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.89 mV | -0.06 mV |
| extracted | 0.88 mV | -0.59 mV |

- The extracted static threshold is about -0.6 mV, the same sign and size as the other points (-0.4 mV at fs, -0.5 mV at
  ff / -40 C, sf and 1.32 V, -0.7 mV at tt / 1.20 V, -1.3 mV at ss / 125 C). It is a layout-induced systematic offset;
  it does not by itself say whether DR-0002's bound is met.
- The sigmas are **not** distinguishable (0.89 vs 0.88 mV): a three-rung fit from n = 78 per rung has per-rung binomial
  intervals 10 to 20 points wide.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The noise Monte Carlo now has tt (1.08 V, 1.20 V and 1.32 V), ss, ff, sf and fs points, the 1.08 V and 1.32 V ones
incomplete (78 and 77 of 80). The other grid points, the offset grid, any DR-0002 noise or offset verdict, `td_c`, and
the item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

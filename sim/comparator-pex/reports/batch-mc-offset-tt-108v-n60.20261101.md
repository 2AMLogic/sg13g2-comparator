# Whole-latch offset Monte Carlo, N = 60 at tt / 27 C / 1.08 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev981+g83e562f043be` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-offset-tt-132v-n60.20261031.md`: `klt pex --backend batch
--max-units-per-job 3` (20 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and vdd 1.08 V (process `tt`, `mos_tt_mismatch`, 27 C),
in an untracked throwaway copy (committed requests unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the
committed one). Data: `batch-mc-offset-tt-108v-n60.20261101.json` (all 180 rows, both sides, including the 9 errored
ones; the full envelope is not committed).

## What went wrong in the run

My first `--submit-only` was stopped by a 580 s `timeout` I put around it (my choice, not a fleet fault), leaving a
manifest with `complete: false`. A second identical invocation into the same output directory completed (exit 0, 2
legs). Jobs from the stopped invocation that were not recorded in the manifest were not identified or collected and are
not part of this result.

## Statistical basis

One PVT point (typical process, 27 C, **low supply 1.08 V**); `vary: mismatch`; N = 60 requested, 57 compared; seed
20260916. Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a 45-point
or corner-matrix result.

## Result (envelope `status: error`; 171 rows passed, 0 failed, 9 errored; 57 samples compared on both sides)

Samples 6, 7 and 8 (one 3-unit shard) **errored on the extracted side only** with `batch_poll_timeout`: shard job
`klt-sim-49b69a062f46` never started (no `status.json` after 1800 s; the client noted a `job.json` with no instance
booted). This is a fleet-capacity finding, not a simulation result. The shard was not re-run. The three samples are
excluded on both sides (paired); their schematic values are in the data file. The envelope is `error`, not `pass`,
because of them.

| `vos_mv` (57 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.66 mV | 3.29 mV | -7.50 .. +7.50 |
| extracted | -0.18 mV | 3.50 mV | -7.50 .. +7.50 |
| per-sample extracted - schematic | -0.84 mV | 4.90 mV | -12.0 .. +12.0 |

- Extracted sigma is about 6 % above schematic (ratio 1.06). Each sigma carries roughly 9 to 10 % relative uncertainty
  at N = 57 and the data are quantized at 3 mV, so a difference is not established.
- `pass`/`error` here only says whether both sides produced a value; no tolerance is applied. **Not a DR-0002
  verdict**: no ratified bound is compared or changed.
- `vbias_mv` agrees between sides to within 0.001 mV (print rounding); schematic mean 308.89 mV, sigma 1.36 mV.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Not established / still open

The remaining 38 points of the 45-point offset grid, the noise grid beyond the points already recorded, any DR-0002
offset or noise verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

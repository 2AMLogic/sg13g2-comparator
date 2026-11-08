# Whole-latch offset Monte Carlo, N = 60 at tt / -40 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev998+gf88962b89bd1` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-offset-tt-125c-n60.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (20 shard jobs per side), `--submit-only` then `--attach --envelope-out`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2
--pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and temperature 27 -> -40 C (process `tt`,
`mos_tt_mismatch`, vdd 1.20 V), in an untracked throwaway copy (committed requests unchanged). Extracted netlist sha256
`b313a02d...d51d47` (same as the other points). Data: `batch-mc-offset-tt-m40c-n60.20261101.json` (all 180 rows, both
sides; the full envelope is not committed).

## What went wrong in the run

My first submit was cut off by my own 120 s command timeout after 6 of 20 schematic shard jobs had been submitted, and
an immediate retry into the same output directory was refused by `--resume`/`--submit-only`. The whole request was then
submitted again into a fresh output directory; the first leg-submit also ended with the extracted leg incomplete, so
`--submit-only` was re-run once more to finish it before attaching. Only the final, complete submission is reported.
The 6 orphaned shard jobs from the first attempt (e.g. `klt-sim-914afaa7b79a`) are not part of this result.

## Statistical basis

One PVT point (typical process, **-40 C**, 1.20 V); `vary: mismatch`; N = 60 requested, 60 compared; seed 20260916.
Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a 45-point or
corner-matrix result.

## Result (envelope `status: pass`; 180 rows passed, 0 failed, 0 errored; 60 samples compared on both sides)

| `vos_mv` (60 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.65 mV | 3.03 mV | -7.50 .. +4.50 |
| extracted | -0.30 mV | 3.37 mV | -4.50 .. +7.50 |
| per-sample extracted - schematic | -0.95 mV | 4.74 mV | -9.0 .. +12.0 |

- Extracted sigma is about 11 % above schematic (ratio 1.11). Each sigma carries roughly 9 % relative uncertainty at
  N = 60 and the data are quantized at 3 mV, so a difference is not established.
- `pass` here only says both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no ratified
  bound is compared or changed.
- `vbias_mv` agrees between sides to within 0.001 mV; schematic mean 345.09 mV, sigma 1.40 mV.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Not established / still open

The remaining offset grid points, the noise grid beyond the points already recorded, any DR-0002 offset or noise
verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

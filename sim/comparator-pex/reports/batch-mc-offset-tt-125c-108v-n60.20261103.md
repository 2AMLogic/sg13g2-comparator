# Whole-latch offset Monte Carlo, N = 60 at tt / 125 C / 1.08 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1299+gc4a63955d6e2` (development build, **not** a released client). Same command shape as
`batch-mc-offset-tt-m40c-108v-n60.20261103.md`: `klt pex --backend batch --max-units-per-job 3` (20 shard jobs per side, 40
jobs total), `--submit-only` then `--attach <outdir>/pex-submit.json --envelope-out`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` `/home/ubuntu/share/pdk`. Nothing ran locally. Request:
`requests/offset_mc.mc.json` with `monte_carlo.n` 60, process `tt` (`mos_tt_mismatch`), 125 C, vdd 1.08 V, in an
untracked throwaway copy (committed requests unchanged; the copy's `netlist` path was made absolute). Extracted netlist
sha256 `b313a02d...d51d47` (same as the other points). Data: `batch-mc-offset-tt-125c-108v-n60.20261103.json` (all 180
rows, both sides, including the 9 errored ones; the full envelope is not committed).

## What went wrong in the run

- `--submit-only` hit my tool timeout twice (540 s, then 560 s) before finishing; the third invocation with the same
  `--outdir` completed (exit 0, 2 legs).
- The `--attach` pass ended at my 580 s tool timeout (exit 124) but had already written the envelope (`status: error`).
  Shard job `klt-sim-024f4ac6202c` (extracted side, samples 3, 4 and 5) is recorded as `lost_shard` ("interrupted by
  client before this shard finished"), although its fleet state in the envelope reads `done`, exit code 0. I do not
  know whether my timeout or the fleet caused the loss. A second `--attach` was refused because the first one had
  already consumed the shard maps, so the three samples were not recovered. Not re-run, and nothing was run locally in
  their place.

## Statistical basis

One PVT point (typical process, 125 C, **1.08 V**); `vary: mismatch`; N = 60 requested, **57 compared**; seed 20260916.
Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a 45-point or
corner-matrix result.

## Result (envelope `status: error`; 171 rows passed, 0 failed, 9 errored; 57 samples compared on both sides)

Samples 3, 4 and 5 are excluded on both sides (paired); the envelope is `error`, not `pass`, because of them.

| `vos_mv` (57 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.76 mV | 3.41 mV | -7.50 .. +7.50 |
| extracted | -0.39 mV | 3.74 mV | -7.50 .. +7.50 |
| per-sample extracted - schematic | -1.16 mV | 4.90 mV | -12.0 .. +9.0 |

- Extracted sigma is about 10 % above schematic (ratio 1.10); with roughly 9 to 10 % relative uncertainty per sigma at
  n = 57 and 3 mV quantization, **no difference is established**.
- Only 13 of 57 samples have the same `vos_mv` on both sides (within half a 3 mV step).
- `pass` on a row only says both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no ratified
  bound is compared or changed.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Not established / still open

The three unmeasured extracted samples, the remaining offset grid points, the noise grid beyond the points already
recorded, any DR-0002 offset or noise verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report.
Item 7 stays `unmet`.

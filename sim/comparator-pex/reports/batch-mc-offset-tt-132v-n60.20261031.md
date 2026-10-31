# Whole-latch offset Monte Carlo, N = 60 at tt / 27 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev981+g83e562f043be` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-offset-fs-27c-n60.20261031.md`: `klt pex --backend batch
--max-units-per-job 3` (20 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and vdd 1.32 V (process `tt`, `mos_tt_mismatch`, 27 C), in
an untracked throwaway copy (committed requests unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the committed
one). Data: `batch-mc-offset-tt-132v-n60.20261031.json` (all 180 rows, both sides; the full envelope is not committed).

## What went wrong in the run

Nothing. This is the point whose submit failed in the previous pass on the shared Spot vCPU quota
(`BATCH_MAX_VCPU=224`, shared with `ci-spot`); this pass the submit completed (exit 0) and the single `--attach`
finished (exit 0) inside the wait cap. The 30 shard jobs left running by the failed previous submit were not
identified or collected and are not part of this result.

## Statistical basis

One PVT point (typical process, 27 C, **high supply 1.32 V**); `vary: mismatch`; N = 60 requested, 60 compared; seed
20260916. Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a 45-point
or corner-matrix result.

## Result (envelope `status: pass`; 180 rows passed, 0 failed, 0 errored; 60 samples compared on both sides)

| `vos_mv` (60 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.65 mV | 2.93 mV | -7.50 .. +4.50 |
| extracted | -0.45 mV | 3.40 mV | -4.50 .. +7.50 |
| per-sample extracted - schematic | -1.10 mV | 4.69 mV | -9.0 .. +12.0 |

- Extracted/schematic sigma ratio is 1.16 here; across the other offset points it is 1.12 (tt, 1.20 V), 1.10 (ss),
  1.17 (ff), 1.14 (sf) and 1.07 (fs), always with the extracted side higher. Each sigma carries roughly 9 to 10 %
  relative uncertainty at N = 60 and the data are quantized at 3 mV, so a difference is not established.
- Only 16 of 60 samples have the same `vos_mv` on both sides.
- `pass`/`error` only says whether both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no
  ratified bound is compared or changed.
- `vbias_mv` agrees between sides to print rounding (max difference 0.001 mV); schematic mean 308.82 mV, sigma 1.38 mV.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The offset Monte Carlo now has tt (1.20 V and 1.32 V), ss, ff, sf and fs points. The other 39 points of the 45-point
offset grid, the rest of the noise grid, any DR-0002 offset or noise verdict, `td_c`, and the item-7 citation, hash and
regenerated signoff report. Item 7 stays `unmet`.

# Whole-latch offset Monte Carlo, N = 60 at fs / 125 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1045+g5a0786e13b63` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-offset-ss-27c-108v-n60.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (20 shard jobs per side, 40 jobs total), `--submit-only` then `--attach <outdir>/pex-submit.json
--envelope-out`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.json` with `monte_carlo.n` 60, process `fs` (`mos_fs_mismatch`), 125 C, vdd 1.20 V, in an untracked
throwaway copy (committed requests unchanged; the copy's `netlist` path was made absolute). Extracted netlist sha256
`b313a02d...d51d47` (same as the other points). Data: `batch-mc-offset-fs-125c-n60.20261102.json` (all 180 rows, both
sides; the full envelope is not committed).

## What went wrong in the run

A first `klt pex` invocation failed immediately on my own throwaway request (wrong relative `netlist` path,
`netlist not found`); no job was submitted. The request was corrected and submitted once; that single submission was
attached once and is the only one reported. No shard was lost.

## Statistical basis

One PVT point (fast-NMOS / slow-PMOS, 125 C, **1.20 V**); `vary: mismatch`; N = 60, **all 60 compared** on both sides;
seed 20260916. Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a
45-point or corner-matrix result.

## Result (envelope `status: pass`; 180 rows passed, 0 failed, 0 errored; 60 of 60 samples compared)

| `vos_mv` | n | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|---|
| schematic | 60 | +0.65 mV | 3.23 mV | -7.50 .. +7.50 |
| extracted | 60 | -0.50 mV | 3.57 mV | -7.50 .. +7.50 |
| per-sample extracted - schematic | 60 | -1.15 mV | 4.91 mV | -12.0 .. +12.0 |

- Extracted sigma is about 11 % above schematic (ratio 1.11); with roughly 9 % relative uncertainty per sigma at n = 60
  and 3 mV quantization, **no difference is established**.
- `pass` on a row only says both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no ratified
  bound is compared or changed.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Not established / still open

The remaining offset grid points, the noise grid beyond the points already recorded, any DR-0002 offset or noise
verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

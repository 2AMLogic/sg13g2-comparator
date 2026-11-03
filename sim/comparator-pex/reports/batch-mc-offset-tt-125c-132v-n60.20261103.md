# Whole-latch offset Monte Carlo, N = 60 at tt / 125 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1305+g87eb519d4723` (development build, **not** a released client). Same command shape as
`batch-mc-offset-tt-125c-108v-n60.20261103.md`: `klt pex --backend batch --max-units-per-job 3` (20 shard jobs per side, 40
jobs total), `--submit-only` then `--attach <outdir>/pex-submit.json --envelope-out`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` `/home/ubuntu/share/pdk`. Nothing ran locally. Request:
`requests/offset_mc.mc.json` with `monte_carlo.n` 60, process `tt` (`mos_tt_mismatch`), 125 C, vdd 1.32 V, in an
untracked throwaway copy (committed requests unchanged; the copy's `netlist` path was made absolute). Extracted netlist
sha256 `b313a02d...d51d47` (same as the other points). Data: `batch-mc-offset-tt-125c-132v-n60.20261103.json` (all 180
rows, both sides, including the 36 errored ones; the full envelope is not committed).

## What went wrong in the run

- `--submit-only` hit my 500 s tool timeout once; the second invocation with the same `--outdir` completed (exit 0,
  2 legs).
- The `--attach` pass ran to my 570 s tool timeout (exit 124) and had written the envelope (`status: error`). It
  reported three extracted shard jobs as `interrupted` (`klt-sim-cce043243287`, `klt-sim-02963a6badf9`,
  `klt-sim-6f253bf41f36`) and one (`klt-sim-9d1b52755328`) that never started (no `status.json` after 307 s). The
  client then marked those four shards `lost_shard` ("interrupted by client before this shard finished"): samples 0 to
  2, 33 to 38 and 48 to 50, extracted side only. I do not know whether my timeout or the fleet caused the loss. The
  lost samples were not re-run and nothing was run locally in their place (`--resume` was not used).

## Statistical basis

One PVT point (typical process, 125 C, **1.32 V**); `vary: mismatch`; N = 60 requested, **48 compared**; seed 20260916.
Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a 45-point or
corner-matrix result.

## Result (envelope `status: error`; 144 rows passed, 0 failed, 36 errored; 48 samples compared on both sides)

The 12 lost samples are excluded on both sides (paired); the envelope is `error`, not `pass`, because of them.

| `vos_mv` (48 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.69 mV | 3.26 mV | -7.50 .. +7.50 |
| extracted | -0.31 mV | 3.54 mV | -7.50 .. +7.49 |
| per-sample extracted - schematic | -1.00 mV | 5.00 mV | n/a |

- Extracted sigma is about 9 % above schematic (ratio 1.09); with roughly 10 % relative uncertainty per sigma at
  n = 48 and 3 mV quantization, **no difference is established**.
- Only 10 of 48 samples have the same `vos_mv` on both sides (within half a 3 mV step).
- `pass` on a row only says both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no ratified
  bound is compared or changed.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Not established / still open

The twelve unmeasured extracted samples, the remaining offset grid points, the noise grid beyond the points already
recorded, any DR-0002 offset or noise verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report.

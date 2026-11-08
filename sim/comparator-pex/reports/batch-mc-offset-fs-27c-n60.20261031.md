# Whole-latch offset Monte Carlo, N = 60 at fs / 27 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev962+ge3572a545d8b` (development build, **not** a released client). Same command shape as
`batch-mc-offset-sf-27c-n60.20261031-b.md`: `klt pex --backend batch --max-units-per-job 3` (20 shard jobs per side),
`--submit-only` then `--attach`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk
ihp-sg13g2 --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and the corner changed to process `fs`
(`mos_fs_mismatch`), 27 C, vdd 1.20 V, in an untracked throwaway copy (committed requests unchanged). Extracted netlist
sha256 `b313a02d...d51d47` (the committed one). Data: `batch-mc-offset-fs-27c-n60.20261031.json` (all 180 rows, both
sides, including the 9 errored ones; the full envelope is not committed).

## What went wrong in the run

The first `--submit-only` hit my 560 s tool cap after submitting part of the jobs; re-running the identical command into
the same output directory finished the submit (exit 0). The single `--attach` was then cut off by my own 580 s tool cap
(SIGTERM): the client reported `interrupted; reporting the shards that finished and marking the rest lost`, and shard job
`klt-sim-07d227ca757b` (extracted side, samples 9, 10 and 11) was marked lost after 308 s of running. A second `--attach`
failed because the first one had already removed the shard map, so the shard could not be recovered and was not re-run.
This is an infrastructure/client-wait failure, not a simulation result, and it is mine (the tool cap), not the fleet's.

## Statistical basis

One PVT point (skew corner: fast NMOS / slow PMOS, the mirror of `sf`); `vary: mismatch`; N = 60 requested, 57 compared;
seed 20260916. Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a
45-point or corner-matrix result.

## Result (envelope `status: error`; 171 rows passed, 0 failed, 9 errored; 57 samples compared on both sides)

Samples 9, 10 and 11 are excluded on both sides (paired); the envelope is `error`, not `pass`, because of them.

| `vos_mv` (57 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.76 mV | 3.02 mV | -7.50 .. +4.50 |
| extracted | -0.45 mV | 3.23 mV | -4.50 .. +4.50 |
| per-sample extracted - schematic | -1.21 mV | 4.60 mV | -9.0 .. +9.0 |

- Extracted/schematic sigma ratio is 1.07 here; across the offset points run so far it is 1.12 (tt), 1.10 (ss),
  1.17 (ff) and 1.14 (sf), always with the extracted side higher. Each sigma carries roughly 9 to 10 % relative
  uncertainty at N = 57 and the data are quantized at 3 mV, so a difference is not established.
- Only 14 of 57 samples have the same `vos_mv` on both sides.
- `pass`/`error` only says whether both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no
  ratified bound is compared or changed.
- `vbias_mv` agrees between sides to print rounding; schematic mean 286.83 mV, sigma 1.38 mV.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The offset Monte Carlo now has tt, ss, ff, sf and fs points (this one 57 of 60). The other 40 points of the 45-point
offset grid, `fs` transient noise, the rest of the noise grid, any DR-0002 offset or noise verdict, `td_c`, and the
item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

## Friction (generic, for `2AMLogic/klayout-tools`)

A client interrupted during `--attach` deletes the shard map, so the shards it marked `lost` cannot be recovered by a
second `--attach` (`--resume` is advised in the message but needs state the interrupted run removed).

# Whole-latch offset Monte Carlo, N = 60 at ff / -40 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev945+gc402def05eeb` (development build, **not** a released client); fleet runner `klt 0.8.0`,
`runner_compatibility: match`, ngspice-46. Same command shape as `batch-mc-offset-ss125-n60.20261031.md`
(`klt pex --backend batch --max-units-per-job 3`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top
comparator --pdk ihp-sg13g2 --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`). Nothing ran
locally. Request: `requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and corners changed to process `ff`
(`mos_ff_mismatch`), -40 C, vdd 1.32 V, in an untracked throwaway copy (the committed requests are unchanged).
Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data: `batch-mc-offset-ff-40c-n60.20261031.json`
(all 60 samples, both sides, 180 rows including the 9 errored ones; the full envelope is not committed).

## Statistical basis

One PVT point (the fast/cold/high-supply extreme, the opposite end from `ss/125C/1.08V`); `vary: mismatch`; N = 60
requested, 57 compared; seed 20260916. The sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV
`lowcount` staircase. It is not a 45-point or corner-matrix result.

## Result (envelope `status: error`; 171 rows passed, 0 failed, 9 errored; 57 samples compared on both sides)

Samples 12, 13 and 14 (one 3-unit shard) **errored on the extracted side only** with `batch_poll_timeout`: shard job
`klt-sim-67b058dad5e2` "never started: no status.json after 1800s". This is an infrastructure failure, not a
simulation result, and I believe it has a known cause: my first `--submit-only` was cut off by the client wait after 25
of 40 shard jobs, and this shard was one of those submitted by that interrupted attempt. The recovery (`--resume`,
without `--submit-only`, which the client refuses to combine) re-attached to it and it never produced a status. I did
not re-run the shard. The three samples are excluded on both sides (paired) and the envelope is `error`, not `pass`,
because of them. Their schematic values are in the data file.

| `vos_mv` (57 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.71 mV | 2.86 mV | -7.50 .. +4.50 |
| extracted | -0.40 mV | 3.34 mV | -4.50 .. +7.50 |
| per-sample extracted - schematic | -1.11 mV | 4.56 mV | -9.0 .. +12.0 |

- Extracted sigma is about 17 % above schematic. Each sigma carries roughly 9 to 10 % relative uncertainty at N = 57
  and the data are quantized at 3 mV, so a difference is not established. Across the three points run so far the
  extracted/schematic sigma ratio is 1.12 (tt), 1.10 (ss) and 1.17 (ff); all three have the extracted side higher.
- `pass`/`error` here only says whether both sides produced a value; no tolerance is applied. **Not a DR-0002
  verdict**: no ratified bound is compared or changed.
- `vbias_mv` agrees between sides to within 0.001 mV (print rounding); schematic mean 301.03 mV, sigma 1.42 mV.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The remaining 42 points of the 45-point offset grid, the noise grid beyond the two points already recorded, any
DR-0002 offset or noise verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7 stays
`unmet`.

## Friction (generic, for `2AMLogic/klayout-tools`)

`--submit-only` that is cut off by the client wait leaves a manifest with `complete: false`; `--submit-only --resume`
is refused (`pex_async_unsupported`), and a plain `--resume` waits on every recorded job, including one whose upload
was interrupted, for the full 1800 s `batch_poll_timeout` before reporting it as errored, with no way to resubmit only
that shard.

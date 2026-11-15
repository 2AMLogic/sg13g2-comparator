# Whole-latch offset Monte Carlo, N = 60 at sf / -40 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1281+g627bead48e64` (development build, **not** a released client). Same command shape as
`batch-mc-offset-sf-125c-n60.20261103.md`: `klt pex --backend batch --max-units-per-job 3` (20 shard jobs per side, 40
jobs total), `--submit-only` then `--attach <outdir>/pex-submit.json --envelope-out`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` `/home/ubuntu/share/pdk` (as `sim/env.sh` resolves it). Nothing ran
locally. Request: `requests/offset_mc.mc.json` with `monte_carlo.n` 60, process `sf` (`mos_sf_mismatch`), -40 C, vdd
1.20 V, in an untracked throwaway copy (committed requests unchanged; the copy's `netlist` path was made absolute).
Extracted netlist sha256 `b313a02d...d51d47` (same as the other points). Data:
`batch-mc-offset-sf-m40c-n60.20261103.json` (all 180 rows, both sides, including the 9 errored ones; the full envelope is
not committed).

## What went wrong in the run

- The first `--submit-only` hit my 480 s tool timeout after the schematic leg was submitted (`complete: false`). It was
  run without `PDK_ROOT` exported in my shell (the extracted netlist hash is unchanged). Re-running the same command with
  `PDK_ROOT` exported into the same output directory finished the extracted-leg submit (exit 0, `complete: true`, 40 jobs
  total).
- The single `--attach` then waited for the fleet. Shard job `klt-sim-924c73f17b2f` (**extracted** side, samples 0, 1 and
  2) never started: the client reported `no status.json` after 123 s and finally `batch_poll_timeout` after 1800 s (no
  instance ever booted for it). Its three samples are errored on the extracted side. This is a fleet launch failure, not a
  simulation result. It was not re-run and nothing was run locally in its place.
- The envelope exit status was 4 (`status: error`).

## Statistical basis

One PVT point (skew corner: slow NMOS / fast PMOS, -40 C, **1.20 V**); `vary: mismatch`; N = 60 requested, **57
compared**; seed 20260916. Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is
not a 45-point or corner-matrix result.

## Result (envelope `status: error`; 171 rows passed, 0 failed, 9 errored; 57 samples compared on both sides)

Samples 0, 1 and 2 are excluded on both sides (paired); the envelope is `error`, not `pass`, because of them.

| `vos_mv` (57 paired samples) | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.45 mV | 2.97 mV | -7.50 .. +4.50 |
| extracted | -0.18 mV | 3.31 mV | -4.50 .. +7.50 |
| per-sample extracted - schematic | -0.63 mV | 4.56 mV | -9.0 .. +12.0 |

- Extracted sigma is about 11 % above schematic (ratio 1.11); with roughly 9 to 10 % relative uncertainty per sigma at n
  = 57 and 3 mV quantization, **no difference is established**.
- Only 15 of 57 samples have the same `vos_mv` on both sides.
- `pass` on a row only says both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no ratified
  bound is compared or changed.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Not established / still open

The three unmeasured extracted samples, the remaining offset grid points, the noise grid beyond the points already
recorded, any DR-0002 offset or noise verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report.
Item 7 stays `unmet`.

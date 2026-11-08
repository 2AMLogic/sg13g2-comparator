# Whole-latch offset Monte Carlo, N = 60 at sf / 27 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial; re-run of the failed `batch-mc-offset-sf-27c-n60.20261031.md`)

Client `klt 0.8.1.dev957+g34a20645968b` (development build, **not** a released client). Same command shape as
`batch-mc-offset-ss125-n60.20261031.md`: `klt pex --backend batch --max-units-per-job 3` (20 shard jobs per side), layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and the corner changed to process `sf`
(`mos_sf_mismatch`), 27 C, vdd 1.20 V, in an untracked throwaway copy (committed requests unchanged). Extracted netlist
sha256 not re-measured for this run. Data: `batch-mc-offset-sf-27c-n60.20261031-b.json` (all 180 rows parsed from the
client's text output; see below).

## How this run differed from the failed attempt

Fresh output directory. The first `--submit-only` hit my 900 s cap after submitting the schematic leg only, and `--attach`
refused the manifest as incomplete (extracted leg missing). Re-running the identical `--submit-only` command finished the
submit (both legs), then a single uninterrupted `--attach` completed with exit 0. No `--resume`, no killed client.

## Statistical basis

One PVT point (skew corner: slow NMOS / fast PMOS); `vary: mismatch`; N = 60; seed 20260916. Sigma is a Monte-Carlo sigma
at that point, quantized by the 3 mV `lowcount` staircase, not a 45-point or corner-matrix result.

## Result (envelope `status: pass`; 60 corners, 180 rows passed, 0 failed, 0 errored; 60 samples compared)

| `vos_mv` | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.60 mV | 2.99 mV | -7.50 .. +4.50 |
| extracted | -0.35 mV | 3.41 mV | -4.50 .. +7.50 |

- Per-sample extracted-minus-schematic difference: mean -0.95 mV, sample sd 4.7 mV; only 17 of 60 samples have the same
  quantized level on both sides. The two benches do not share a sample-by-sample mismatch draw, so a per-sample delta is
  not a layout effect; compare the distributions, not paired samples.
- The sigmas differ by about 0.4 mV, less than one 3 mV quantization step, and no significance test was run: no
  difference is established. Together with nominal (3.03 / 3.41), `ss/125C` (3.42 / 3.75) and `ff/-40C` (2.86 / 3.34),
  extracted sigma is 0.3 to 0.5 mV higher at all four points, a consistent sign that this evidence does not turn into a
  DR-0002 claim.
- This leaves the offset Monte Carlo with extracted results at tt, ss, ff and sf; `fs` is not run.

## Not established / still open

The other 41 offset points and `fs`, the noise grid (43 points left), any DR-0002 offset or noise verdict, `td_c`, and the
item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

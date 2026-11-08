# Whole-latch offset Monte Carlo, N = 60 at the nominal point, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev909+gaaf8fbf68b2b` (development build, **not** a released client). `klt pex --backend batch
--max-units-per-job 3` (20 shard jobs per side; the fleet caps shards at 3 units at `timeout_s` 900), run as
`--submit-only` then `--attach`; layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk
ihp-sg13g2 --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally.
Request: `requests/offset_mc.mc.probe.json` with `monte_carlo.n` raised 3 -> 60 in an untracked throwaway copy (the
committed request is unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data:
`batch-mc-offset-nominal-n60.20261031.json` (all 60 samples, both sides; the full envelope is not committed).

## Statistical basis

One PVT point only: process `tt` with `mos_tt_mismatch`, 27 C, vdd 1.20 V; `vary: mismatch`; N = 60; seed
20260916 (the schematic bench's). The sigma below is a Monte-Carlo sigma **at that point**, not a corner-matrix
or 45-point result, and is quantized by the 3 mV staircase step of the `lowcount` measurement.

## Result (envelope `status: pass`; 180 rows passed, 0 failed, 0 errored; 60 samples compared)

| `vos_mv` | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.65 mV | 3.03 mV | -7.50 .. +4.50 |
| extracted | -0.30 mV | 3.41 mV | -4.50 .. +7.50 |
| per-sample extracted - schematic | -0.95 mV | 4.80 mV | |

- The extracted sigma is about 12 % above the schematic sigma at this point. With N = 60 and 3 mV quantization the
  uncertainty on each sigma (about 9 % relative at N = 60 under normality) is of the same order, so this does **not**
  by itself establish a difference. The per-sample delta sigma (4.8 mV) shows the two sides do not track
  sample-for-sample, consistent with the extracted netlist's finger decomposition (38 / 26 vs 12 / 12 devices) drawing
  different mismatch samples.
- `pass` means both sides produced a value; no tolerance is applied. This is **not** a DR-0002 verdict: the spec bound
  is not compared here, and no PVT-grid sigma exists.
- `vbias_mv` and `lowcount` are in the data file. `body_bias.status: biased`; `model_mismatch.kind: count_only`.

## A failed first submit (kept for the record)

The first attempt omitted `--pins`; every one of 180 delta rows errored with `pin_count_mismatch` (extracted
netlist 16 pins vs schematic 8), the extracted side never ran, and the `--submit-only` manifest recorded only the
schematic leg yet said `complete: true`. Resubmitting with `--pins` (the committed README command) produced both legs.
The extracted netlist sha256 of that failed attempt was `65e7168a...deebc` (no `--pins`); not used.

## Not established / still open

- The 45-point PVT offset grid (N = 60, 2700 units) and the whole-latch transient-noise floor (N = 80), including
  ss / 125 C behaviour; no DR-0002 offset or noise verdict; `td_c`; the item-7 citation, hash and regenerated signoff
  report. Item 7 stays `unmet`; acceptance rows 3-4 remain open.
- Friction (generic, for `2AMLogic/klayout-tools`): `klt pex --submit-only` reports `complete: true` with one leg
  when the extracted leg could not be submitted.

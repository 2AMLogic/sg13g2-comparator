# Whole-latch offset Monte Carlo, N = 60 at ff / 125 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1008+ge68219cbc745` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-offset-tt-m40c-n60.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (20 shard jobs per side), `--submit-only` (took 14 min) then `--attach --envelope-out`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2
--pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.json` with `monte_carlo.n` 60, process `ff` (`mos_ff_mismatch`), 125 C, vdd 1.32 V, in an
untracked throwaway copy (committed requests unchanged). Extracted netlist sha256 `b313a02d...d51d47` (same as the other
points). Data: `batch-mc-offset-ff-125c-132v-n60.20261101.json` (all 180 rows, both sides; the full envelope is not
committed).

## What went wrong in the run

Five of the 20 extracted shard jobs (`klt-sim-184286ec5899`, `-e752b04863c3`, `-0a8062af1ad7`, `-41fbcbd62749`,
`-87fca8a6588b`) reported `state=interrupted` and stayed so for more than 900 s. I capped the attach at 1500 s, after
which klt marked them lost ("interrupted; reporting the shards that finished") and wrote an envelope with
`status: error`. I did not re-run with `--resume`, so this is an incomplete point, kept as a finding. All 20 schematic
shards finished. The 15 samples without an extracted value are `mc45` .. `mc59`.

## Statistical basis

One PVT point (fast process, **125 C**, **1.32 V**); `vary: mismatch`; N = 60 requested, **45 compared** on both sides;
seed 20260916. Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a
45-point or corner-matrix result.

## Result (envelope `status: error`; 135 rows passed, 0 failed, 45 errored; 45 of 60 samples compared on both sides)

| `vos_mv` | n | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|---|
| schematic (all 60) | 60 | +0.55 mV | 3.15 mV | -7.50 .. +7.50 |
| schematic (the 45 compared) | 45 | +0.63 mV | 3.11 mV | -4.50 .. +7.50 |
| extracted (the 45 compared) | 45 | -0.17 mV | 3.42 mV | -4.50 .. +7.50 |
| per-sample extracted - schematic | 45 | -0.80 mV | 4.50 mV | -9.0 .. +12.0 |

- On the 45 paired samples the extracted sigma is about 10 % above schematic (ratio 1.10). With roughly 11 % relative
  uncertainty per sigma at n = 45 and 3 mV quantization, a difference is not established.
- `pass` on a row only says both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no ratified
  bound is compared or changed.
- `vbias_mv` agrees between sides to within 0.001 mV on the 45 paired samples; schematic mean 205.53 mV, sigma 1.22 mV.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Not established / still open

The 15 missing extracted samples at this point, the remaining offset grid points, the noise grid beyond the points
already recorded, any DR-0002 offset or noise verdict, `td_c`, and the item-7 citation, hash and regenerated signoff
report. Item 7 stays `unmet`.

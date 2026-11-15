# Whole-latch offset Monte Carlo, N = 60 at sf / 27 C / 1.20 V: extracted side lost, no comparison (issue #61, acceptance row 3, failed attempt)

Client `klt 0.8.1.dev951+g20243fdcc1cf` (development build, **not** a released client); fleet runner `klt 0.8.0`,
`runner_compatibility: match`, ngspice-46. Same command shape as `batch-mc-offset-ff-40c-n60.20261031.md`
(`klt pex --backend batch --max-units-per-job 3`, `--submit-only` then `--attach`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`). Nothing ran locally. Request:
`requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and the corner changed to process `sf`
(`mos_sf_mismatch`), 27 C, vdd 1.20 V, in an untracked throwaway copy (committed requests unchanged). Extracted netlist
sha256 `b313a02d...d51d47` (the committed one). Data: `batch-mc-offset-sf-27c-n60.20261031.json` (all 180 rows, error
messages abbreviated; the full envelope is not committed).

## Result: envelope `status: error`; 0 rows passed, 0 failed, 180 errored. No schematic-vs-extracted comparison exists.

- **Extracted side: all 60 samples errored** with `lost_shard` ("shard lost: [Errno 32] Broken pipe", stage `collect`).
  This is an infrastructure failure, not a simulation result. A second `--attach` produced the same envelope.
- **Schematic side:** 57 of 60 samples produced values; samples 15, 16 and 17 (one 3-unit shard) were
  `nothing_simulated`.
- How it got there (the cause is not established): the first `--submit-only` was cut off by the client wait; the first
  `--attach` was then killed by my wall-clock cap, after which the schematic leg's `batch-shards.json` was gone, and a
  `--resume` re-submitted the schematic leg (16 receipts), and the next `--resume` refused with a shard-map fingerprint
  mismatch. I deleted the schematic leg directory, re-ran `--submit-only` (schematic re-submitted, extracted leg
  re-attached), and `--attach`ed to that. The extracted legs were therefore submitted once and attached to across several
  killed clients.

## What this does and does not say

The schematic-only statistics are **not** a result of this issue's comparison and are given only so the data is not
discarded: `vos_mv`, 57 samples, mean +0.55 mV, sample sigma 3.06 mV, min -7.50, max +4.50 (3 mV `lowcount` staircase).
There is **no** extracted sigma at sf / 27 C, no delta, and no DR-0002 verdict. The skew corners (`sf`, `fs`) therefore
remain without extracted offset evidence; the offset Monte Carlo has extracted results at tt, ss and ff only
(`batch-mc-offset-{nominal,ss125,ff-40c}-n60.20261031.md`). Item 7 stays `unmet`.

## Next step

Re-run this point from a fresh output directory with one uninterrupted `--submit-only`, then `--attach` with a wait
long enough to finish in one client session, rather than killing and resuming the client.

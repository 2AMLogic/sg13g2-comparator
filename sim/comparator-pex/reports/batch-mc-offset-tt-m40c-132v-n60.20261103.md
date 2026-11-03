# Whole-latch offset Monte Carlo, N = 60 at tt / -40 C / 1.32 V: extracted side lost, no comparison (issue #61, acceptance row 3, failed attempt)

Client `klt 0.8.1.dev1305+g87eb519d4723` (development build, **not** a released client). Same command shape as
`batch-mc-offset-tt-125c-132v-n60.20261103.md`: `klt pex --backend batch --max-units-per-job 3` (20 shard jobs per side),
`--submit-only` then `--attach <outdir>/pex-submit.json --envelope-out`, layout `layout/comparator/comparator.gds`,
`--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT`
`/home/ubuntu/share/pdk`. Nothing ran locally. Request: `requests/offset_mc.mc.json` with `monte_carlo.n` 60, process
`tt` (`mos_tt_mismatch`), -40 C, vdd 1.32 V, in an untracked throwaway copy (committed requests unchanged; the copy's
`netlist` path was made absolute). Extracted netlist sha256 `b313a02d...d51d47` (same as the other points). Data:
`batch-mc-offset-tt-m40c-132v-n60.20261103.json` (all 180 rows, error messages abbreviated; the full envelope is not
committed).

## Result: envelope `status: error`; 0 rows passed, 0 failed, 180 errored. No schematic-vs-extracted comparison exists.

- **Extracted side: no sample has a value.** 57 of 60 samples carry `lost_shard` (`[Errno 32] Broken pipe`, stage
  `collect`); samples 27 to 29 are reported only through the schematic-side `lost_shard` error. This is an
  infrastructure failure, not a simulation result.
- **Schematic side:** 57 of 60 samples produced values; samples 27, 28 and 29 (one 3-unit shard) were lost
  (`shard lost: interrupted by client before this shard finished`).
- How it got there (the cause is not established): both `--submit-only` invocations were cut off by my 450 s and 500 s tool
  timeouts, and a third completed (2 legs, 60 units each; the client noted shard 18 "was being launched when an earlier
  submit stopped; not launching it again"). The first `--attach` hit my 570 s timeout without writing an envelope; the
  second wrote `status: error` and was also cut off by my 580 s timeout. A third `--attach` was refused because the first
  attach had already consumed the schematic `batch-shards.json`, so the run could not be re-collected. I did not
  `--resume` or resubmit, and nothing was run locally in its place.

## What this does and does not say

The schematic-only statistics are **not** a result of this issue's comparison and are given only so the data is not
discarded: `vos_mv`, 57 samples, mean +0.55 mV, sample sigma 3.01 mV, min -7.50, max +4.50 (3 mV `lowcount` staircase).
There is **no** extracted sigma at tt / -40 C / 1.32 V, no delta, and no DR-0002 verdict. `body_bias.status: biased`
(same extracted netlist as the other points). Item 7 stays `unmet`.

## Next step

Re-run this point from a fresh output directory with an uninterrupted `--submit-only` and an `--attach` given a wait long
enough to finish in one client session, rather than relying on tool-call timeouts below the client's own wait.

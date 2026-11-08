# Whole-latch offset Monte Carlo, N = 60 at ff / 27 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1016+gbfe2862d8457` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-offset-ss-27c-108v-n60.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (20 shard jobs per side, 40 jobs total), `--submit-only` then `--attach <outdir>/pex-submit.json
--envelope-out`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/offset_mc.mc.json` with `monte_carlo.n` 60, process `ff` (`mos_ff_mismatch`), 27 C, vdd 1.32 V, in an
untracked throwaway copy (committed requests unchanged; the copy's `netlist` path was made absolute). Extracted netlist
sha256 `b313a02d...d51d47` (same as the other points). Data: `batch-mc-offset-ff-27c-132v-n60.20261101.json` (all 180
rows, both sides; the full envelope is not committed).

The submit ran once, in the foreground of one session (the shard submission took about 15 minutes), and was attached
once. An earlier attempt at this same point was cut off by a tool-call limit after 24 of 40 shard jobs (see the issue
comment of 2026-11-01); those jobs were not collected and are **not** part of this result.

## Statistical basis

One PVT point (fast process, 27 C, **1.32 V**); `vary: mismatch`; N = 60, **all 60 compared** on both sides; seed
20260916. Sigma is a Monte-Carlo sigma at that point, quantized by the 3 mV `lowcount` staircase. It is not a 45-point
or corner-matrix result.

## Result (envelope `status: pass`; 180 rows passed, 0 failed, 0 errored; 60 of 60 samples compared)

| `vos_mv` | n | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|---|
| schematic | 60 | +0.65 mV | 2.93 mV | -7.50 .. +4.50 |
| extracted | 60 | -0.45 mV | 3.40 mV | -4.50 .. +7.50 |
| per-sample extracted - schematic | 60 | -1.10 mV | 4.69 mV | -9.0 .. +12.0 |

- Extracted sigma is about 16 % above schematic (ratio 1.16); with roughly 9 % relative uncertainty per sigma at n = 60
  and 3 mV quantization, **no difference is established**.
- `pass` on a row only says both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**: no ratified
  bound is compared or changed.
- `body_bias.status: biased` (same extracted netlist as the other points).

## Disclosure: identical quantized values to tt / 27 C / 1.32 V

All 60 `vos_mv` values on both sides equal, after rounding to 0.1 mV, those of `batch-mc-offset-tt-132v-n60.20261031.json`
(tt / 27 C / 1.32 V), so the sigmas match too (2.93 / 3.40 mV). The raw values differ in the fourth decimal
(e.g. sample 0 schematic 4.49947 here, 4.49898 there), so the `ff` section was applied. The same seed gives the same
mismatch draw, and the 3 mV staircase absorbs the small process shift. This point therefore adds no independent
information over tt / 27 C / 1.32 V at this resolution; it is recorded as a distinct grid point, not as an
independent sigma estimate.

## Not established / still open

The remaining offset grid points, the noise grid beyond the points already recorded, any DR-0002 offset or noise
verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

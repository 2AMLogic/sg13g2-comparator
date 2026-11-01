# Whole-latch transient-noise Monte Carlo, N = 80 at ff / 27 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1028+gd1011d681ec8` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-noise-ss-27c-108v-n80.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side, 54 jobs total), `--submit-only` then `--attach <outdir>/pex-submit.json
--envelope-out`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.json` with `monte_carlo.n` 80, process `ff` (plain `mos_ff`, **no mismatch models**, as the schematic
bench), 27 C, vdd 1.32 V, in an untracked throwaway copy (committed requests unchanged; the copy's `netlist` path was made
absolute). Extracted netlist sha256 `b313a02d...d51d47` (identical to the other points). Data:
`batch-mc-noise-ff-27c-132v-n80.20261101.json` (all 80 trials, both sides; the full envelope is not committed).

The submit ran once (about 20 minutes for the 54 shard submissions) and was attached once, both polled within a single
session with a time cap; no earlier attempt at this point exists, and no job was left uncollected.

## Statistical basis

One PVT point (fast process, 27 C, **1.32 V**); **all 80 of 80** trials compared on both sides; rungs at differential
overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded but
**does not govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible.
One-point result, not a corner-matrix or 45-point result, and not a DR-0002 verdict.

## Result (envelope `status: pass`; 240 rows passed, 0 failed, 0 errored)

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 80:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 41 / 80 = 0.513 (0.405 .. 0.619) | 44 / 80 = 0.550 (0.441 .. 0.654) |
| +1.0 mV (`d_plus`) | 74 / 80 = 0.925 (0.846 .. 0.965) | 78 / 80 = 0.975 (0.913 .. 0.993) |
| -1.0 mV (`d_minus`) | 11 / 80 = 0.138 (0.079 .. 0.230) | 19 / 80 = 0.238 (0.158 .. 0.341) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs (a coordinate search, the same
routine as the other noise points; the fit script was a throwaway and is not committed). No rung is clamped on either
side.

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.81 mV | -0.06 mV |
| extracted | 0.91 mV | -0.24 mV |

- The extracted fit sigma is about 13 % above the schematic one; with about 13 % 1-sigma scatter per fit at n = 80 and
  three rungs, **no difference is established**. All Wilson intervals overlap.
- Both fits sit below the quoted 1.0 mV rms Target at this point. That restates the comparison for one point; it is
  **not** a Row 2 verdict, because the ratified compliance statistic is not complete here.
- No trial has an intermediate output (0.05 .. 0.95 of vdd) at the 5 ns sample on the extracted side.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The remaining noise grid points, any DR-0002 noise or offset verdict, `td_c`, and the item-7 citation, hash and
regenerated signoff report. Item 7 stays `unmet`: `klt signoff` accepts only a `klt pex` report for item 7, and the
committed one is the single-corner run.

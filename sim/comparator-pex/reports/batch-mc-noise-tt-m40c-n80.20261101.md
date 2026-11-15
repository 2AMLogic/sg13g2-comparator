# Whole-latch transient-noise Monte Carlo, N = 80 at tt / -40 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1004+g940d34faf189` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-noise-tt-125c-n80.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json
--envelope-out`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and temperature 27 -> -40 C (process `tt`, plain `mos_tt`,
**no mismatch models**, as the schematic bench; vdd 1.20 V), in an untracked throwaway copy (committed requests
unchanged; the copy's `netlist` path was made absolute). Extracted netlist sha256 `b313a02d...d51d47` (identical to the
other points). Data: `batch-mc-noise-tt-m40c-n80.20261101.json` (all 80 trials, both sides; the full envelope is not
committed).

## What went wrong in the run

My first `--submit-only` was stopped by a 560 s `timeout` I put around it (my choice, not a fleet fault) before it wrote
a manifest, so it could not be resumed or attached. Some shard jobs from that invocation were already submitted; they were
not identified or collected and are not part of this result. The whole request was then submitted again into a fresh
output directory, which completed (`complete: true`, 54 jobs, both legs) and was attached once. Only that final
submission is reported.

## Statistical basis

One PVT point (typical process, **-40 C**, 1.20 V); **80 of 80** trials compared; rungs at differential overdrive 0 /
+1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded but **does not
govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible and samples in
different jobs may share a noise stream. One-point result, not a corner-matrix or 45-point result, and not a DR-0002
verdict.

## Result (envelope `status: pass`; 240 rows passed, 0 failed, 0 errored)

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 80:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 34 / 80 = 0.425 (0.323 .. 0.534) | 54 / 80 = 0.675 (0.566 .. 0.768) |
| +1.0 mV (`d_plus`) | 75 / 80 = 0.938 (0.862 .. 0.973) | 80 / 80 = 1.000 (0.954 .. 1.000) |
| -1.0 mV (`d_minus`) | 12 / 80 = 0.150 (0.088 .. 0.244) | 14 / 80 = 0.175 (0.107 .. 0.273) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs (a coordinate search, the same
routine as the 125 C point). The extracted `d_plus` rung sits at n (80/80) and was clamped with `p = (k + 0.5) / (n + 1)`,
so the extracted fit is less well determined than the schematic one.

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.78 mV | +0.05 mV |
| extracted | 0.70 mV (clamped rung) | -0.33 mV |

- The extracted static threshold is about -0.3 mV, the same sign as most other points; it is a layout-induced systematic
  offset and does not by itself say whether DR-0002's bound is met.
- Extracted sigma (0.70 mV) is slightly below schematic (0.78 mV) with one clamped rung and n = 80 per rung, so **no
  difference is established**.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The noise Monte Carlo now has tt (-40 C, 1.08 V, 1.20 V, 1.32 V and 125 C), ss, ff, sf and fs points. The other grid
points, any DR-0002 noise or offset verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7
stays `unmet`.

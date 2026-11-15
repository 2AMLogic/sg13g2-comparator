# Whole-latch transient-noise Monte Carlo, N = 80 at ff / -40 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev951+g20243fdcc1cf` (development build, **not** a released client); fleet runner `klt 0.8.0`,
`runner_compatibility: match`. Same command shape as `batch-mc-noise-ss125-n80.20261031.md`:
`klt pex --backend batch --max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and corners changed to process `ff` (plain `mos_ff`, **no
mismatch models**, as the schematic bench), -40 C, vdd 1.32 V, in an untracked throwaway copy (the committed requests
are unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data:
`batch-mc-noise-ff-40c-n80.20261031.json` (all 80 trials, both sides, three rungs; the full envelope is not committed).

## Statistical basis

One PVT point (fast/cold/high-supply, the opposite end from `ss/125C/1.08V`); N = 80 trials per rung, all 80 compared;
rungs at differential overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed
(20260916) is recorded but **does not govern** the noise (`klt` warns that `trnoise()` sources are seeded from the
process id), so this run is not reproducible and samples in different jobs may share a noise stream. One-point result,
not a corner-matrix or 45-point result, and not a DR-0002 verdict.

## Result (envelope `status: pass`; 240 rows passed, 0 failed, 0 errored; 80 trials compared on both sides)

A first `--submit-only` was cut off by the client wait before it wrote `pex-submit.json`; its few already-submitted
shard jobs were abandoned and this report is from a fresh complete run (new output directory, identical arguments at
submit and attach).

Trials that decided HIGH (`v(dout)/vdd > 0.5`; every value was within 0.001 of a rail), 95 % Wilson intervals, n = 80:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 28 / 80 = 0.350 (0.255 .. 0.459) | 55 / 80 = 0.688 (0.579 .. 0.778) |
| +1.0 mV (`d_plus`) | 74 / 80 = 0.925 (0.846 .. 0.965) | 80 / 80 = 1.000 (0.954 .. 1.000) |
| -1.0 mV (`d_minus`) | 17 / 80 = 0.213 (0.137 .. 0.314) | 22 / 80 = 0.275 (0.189 .. 0.381) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares (a rung at 0 or n clamped to a half count), as in the
other two points:

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.89 mV | -0.08 mV |
| extracted | 0.65 mV (the `d_plus` rung is clamped) | -0.51 mV |

- The extracted static threshold is about -0.5 mV at this point (about -0.7 mV nominal, about -1.3 mV at `ss/125C`),
  against about -0.1 mV schematic at all three. The sign is the same at all three points and the magnitude is smallest
  here. This is a layout-induced systematic offset; it does not by itself say whether DR-0002's bound is met.
- The sigmas are **not** distinguishable: the extracted fit rests on a clamped rung, and the per-rung binomial intervals
  at n = 80 are 10 to 20 points wide. The lower extracted sigma is not a claim of lower noise.
- Unlike `ss/125C/1.08V`, no trial hit `timestep too small` here.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The other 43 points of the 45-point noise grid, the offset grid (42 points left), any DR-0002 noise or offset verdict,
`td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

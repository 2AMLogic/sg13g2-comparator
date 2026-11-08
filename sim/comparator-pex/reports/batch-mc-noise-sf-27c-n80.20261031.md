# Whole-latch transient-noise Monte Carlo, N = 80 at sf / 27 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev958+g30585256eeb1` (development build, **not** a released client); fleet runner compatible (envelope
`status: pass`, no compatibility error). Same command shape as `batch-mc-noise-ff-40c-n80.20261031.md`:
`klt pex --backend batch --max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and corners changed to process `sf` (plain `mos_sf`, **no
mismatch models**, as the schematic bench), 27 C, vdd 1.20 V, in an untracked throwaway copy (the committed requests are
unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data:
`batch-mc-noise-sf-27c-n80.20261031.json` (all 80 trials, both sides, three rungs; the full envelope is not committed).

## Statistical basis

One PVT point (skew corner: slow NMOS / fast PMOS); N = 80 trials per rung, all 80 compared; rungs at differential
overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded but
**does not govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible and
samples in different jobs may share a noise stream. One-point result, not a corner-matrix or 45-point result, and not a
DR-0002 verdict.

## Result (envelope `status: pass`; 240 rows passed, 0 failed, 0 errored; 80 trials compared on both sides)

The `--submit-only` step was cut off twice by my 580 s tool cap (once before `pex-submit.json` existed, once with the
extracted leg unsubmitted; `--attach` refused the incomplete manifest). Re-running the identical `--submit-only` command
into the same output directory completed it (exit 0), then a single uninterrupted `--attach` exited 0. No `--resume`.

Trials that decided HIGH (`v(dout)/vdd > 0.5`; every value was within 0.001 of a rail), 95 % Wilson intervals, n = 80:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 44 / 80 = 0.550 (0.441 .. 0.654) | 61 / 80 = 0.763 (0.659 .. 0.842) |
| +1.0 mV (`d_plus`) | 74 / 80 = 0.925 (0.846 .. 0.965) | 80 / 80 = 1.000 (0.954 .. 1.000) |
| -1.0 mV (`d_minus`) | 18 / 80 = 0.225 (0.147 .. 0.328) | 16 / 80 = 0.200 (0.127 .. 0.300) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares (a rung at 0 or n clamped to a half count), identical to
the other points (the fit routine reproduces the ff / -40 C report's figures from its counts):

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.91 mV | -0.25 mV |
| extracted | 0.60 mV (the `d_plus` rung is clamped) | -0.47 mV |

- The extracted static threshold is about -0.5 mV at this point, the same sign and about the same size as at ff / -40 C
  (-0.5 mV) and tt (-0.7 mV); ss / 125 C was larger (-1.3 mV). Schematic thresholds stay within about -0.25 .. 0 mV.
  This is a layout-induced systematic offset; it does not by itself say whether DR-0002's bound is met.
- The sigmas are **not** distinguishable: the extracted fit rests on a clamped rung and the per-rung binomial intervals at
  n = 80 are 10 to 20 points wide. The lower extracted sigma is not a claim of lower noise.
- No trial hit `timestep too small` and no sample errored.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The noise Monte Carlo now has tt, ss, ff and sf points. The other 41 points of the 45-point noise grid (including `fs`),
the offset grid (41 points left plus `fs`), any DR-0002 noise or offset verdict, `td_c`, and the item-7 citation, hash and
regenerated signoff report. Item 7 stays `unmet`.

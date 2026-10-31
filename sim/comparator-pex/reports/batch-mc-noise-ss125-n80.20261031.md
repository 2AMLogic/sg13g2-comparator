# Whole-latch transient-noise Monte Carlo, N = 80 at ss / 125 C / 1.08 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev930+g6b0d9c7b3693` (development build, **not** a released client). Same command shape as
`batch-mc-noise-nominal-n80.20261031.md`: `klt pex --backend batch --max-units-per-job 3` (27 shard jobs per side),
`--submit-only` then `--attach`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk
ihp-sg13g2 --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally.
Request: `requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and corners changed to process `ss` (plain
`mos_ss`, **no mismatch models**, as the schematic bench), 125 C, vdd 1.08 V, in an untracked throwaway copy (the
committed requests are unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data:
`batch-mc-noise-ss125-n80.20261031.json` (all 80 trials, both sides, three rungs, including the three errored ones;
the full envelope is not committed).

## Statistical basis

One PVT point (slow/hot/low-supply); N = 80 trials requested per rung, 77 compared (see failures below); rungs at
differential overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916)
is recorded but **does not govern** the noise (`klt` warns that `trnoise()` sources are seeded from the process id), so
this run is not reproducible and samples in different jobs may share a noise stream. One-point result, not a
corner-matrix or 45-point result, and not a DR-0002 verdict.

## Result (envelope `status: error`; 231 rows passed, 0 failed, 9 errored; 77 trials compared on both sides)

Three trials (samples 21, 24, 27) **errored on the extracted side only**: `ngspice aborted the transient: timestep too
small at time = 1e-09 s (trouble with node "vclk#branch")`, on all three rungs each (9 rows). The schematic side passed
for the same samples. They are excluded from the counts below on both sides (paired); they are a post-layout
convergence finding, not noise, and they are why the envelope is `error` rather than `pass`.

Trials that decided HIGH (`v(dout)/vdd > 0.5`; every value was within 0.001 of a rail), 95 % Wilson intervals, n = 77:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 42 / 77 = 0.545 (0.435 .. 0.652) | 69 / 77 = 0.896 (0.808 .. 0.946) |
| +1.0 mV (`d_plus`) | 72 / 77 = 0.935 (0.857 .. 0.972) | 77 / 77 = 1.000 (0.952 .. 1.000) |
| -1.0 mV (`d_minus`) | 11 / 77 = 0.143 (0.082 .. 0.238) | 50 / 77 = 0.649 (0.538 .. 0.747) |

Fit `p(od) = Phi((od - theta) / sigma)` to the three rungs by least squares on the probits (a rung at 0 or n clamped to
a half count), as in the nominal report:

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.77 mV | -0.14 mV |
| extracted | 0.95 mV (the `d_plus` rung is clamped) | -1.31 mV |

- The extracted latch shows a static threshold of about -1.3 mV at this point (about -0.7 mV at the nominal point):
  with -1.0 mV applied it still decides HIGH in 65 % of trials. The schematic stays near balanced. This is a
  layout-induced systematic offset that grows at the slow/hot corner; it does not by itself say whether DR-0002's
  bound is met.
- The sigmas are **not** distinguishable: the extracted fit rests on a clamped rung and the per-rung binomial
  intervals at n = 77 are 10 to 20 points wide. No claim of a noise improvement or degradation is made.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Failed first attempt (kept for the record)

A first run's `--submit-only` was cut off by the client wait and a retry hit `outdir_locked` because the first process
was still running. Its `--attach` then returned the schematic side but `resume_fingerprint_mismatch` for the extracted
side, because I passed a different `-o` netlist path at attach than at submit, and the failed attach had already
consumed the schematic shard map. That run is discarded; this report is from a fresh complete run (new output
directory, identical arguments at submit and attach). Friction (generic, for `2AMLogic/klayout-tools`): `--attach`
fingerprints the `-o` path, and an attach that fails on one leg consumes the other leg's shard map so it cannot be
retried.

## Not established / still open

The other 44 points of the 45-point noise grid, the offset grid (43 points left), any DR-0002 noise or offset verdict,
`td_c`, root cause of the three timestep-too-small trials, and the item-7 citation, hash and regenerated signoff
report. Item 7 stays `unmet`.

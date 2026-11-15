# Whole-latch transient-noise Monte Carlo, N = 80 at tt / 27 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev981+g83e562f043be` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-noise-fs-27c-n80.20261031.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json`, layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and corners changed to process `tt` (plain `mos_tt`, **no
mismatch models**, as the schematic bench), 27 C, vdd 1.32 V, in an untracked throwaway copy (committed requests
unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the netlist `klt pex` extracted in this run, from the same
committed GDS as the other points). Data: `batch-mc-noise-tt-132v-n80.20261101.json` (the 77 compared trials, both
sides, three rungs; the full envelope is not committed).

## What went wrong in the run

The first `--submit-only` was interrupted part-way (19 of 27 schematic shard jobs submitted, no `pex-submit.json`) when
the Loom daemon restarted for a version roll. Those orphaned jobs were not identified or collected and are not part of
this result. A second identical invocation into the same output directory completed (exit 0). The single `--attach`
then ran about 1 h; the schematic-side shard `klt-sim-edeeec291ff4` (samples 54, 55, 56) **never started** (no
`status.json` after 1800 s, code `batch_poll_timeout`), so those three trials have no schematic value. Envelope
`status: error` (231 rows passed, 0 failed, 9 errored); samples 54..56 are excluded from both sides so the two sides use
the same trials. The shard was not re-run. This is a fleet-capacity finding, not a simulation result.

## Statistical basis

One PVT point (typical process, 27 C, **high supply 1.32 V**); **77 of 80** trials compared; rungs at differential
overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded
but **does not govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible
and samples in different jobs may share a noise stream. One-point result, not a corner-matrix or 45-point result, and
not a DR-0002 verdict.

## Result

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 77:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 36 / 77 = 0.468 (0.360 .. 0.578) | 57 / 77 = 0.740 (0.633 .. 0.825) |
| +1.0 mV (`d_plus`) | 70 / 77 = 0.909 (0.824 .. 0.955) | 76 / 77 = 0.987 (0.930 .. 0.998) |
| -1.0 mV (`d_minus`) | 14 / 77 = 0.182 (0.112 .. 0.282) | 18 / 77 = 0.234 (0.153 .. 0.340) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs (a rung at 0 or n would be clamped to
a half count; none is here), the same routine as the other points:

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.92 mV | -0.03 mV |
| extracted | 0.72 mV | -0.47 mV |

- The extracted static threshold is about -0.5 mV, the same sign and size as the other points (-0.4 mV at fs, -0.5 mV at
  ff / -40 C and sf, -0.7 mV at tt / 1.20 V, -1.3 mV at ss / 125 C). It is a layout-induced systematic offset; it does
  not by itself say whether DR-0002's bound is met.
- The sigmas are **not** distinguishable: a three-rung fit from n = 77 per rung has per-rung binomial intervals 10 to 20
  points wide, and the extracted sigma comes out lower than the schematic one here.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The noise Monte Carlo now has tt (1.20 V and 1.32 V), ss, ff, sf and fs points, the 1.32 V one incomplete (77 of 80).
The other grid points, the offset grid (41 points left), any DR-0002 noise or offset verdict, `td_c`, and the item-7
citation, hash and regenerated signoff report. Item 7 stays `unmet`.

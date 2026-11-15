# Whole-latch transient-noise Monte Carlo, N = 80 at tt / 125 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev981+g83e562f043be` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-noise-tt-108v-n80.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json
--envelope-out`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and temperature 27 -> 125 C (process `tt`, plain `mos_tt`,
**no mismatch models**, as the schematic bench; vdd 1.20 V), in an untracked throwaway copy (committed requests
unchanged). Extracted netlist sha256 `b313a02d...d51d47` (identical to the other points). Data:
`batch-mc-noise-tt-125c-n80.20261101.json` (the 77 compared trials plus the 9 errored rows; the full envelope is not
committed).

## What went wrong in the run

My first `--submit-only` was stopped by a 900 s `timeout` I put around it (my choice, not a fleet fault); its manifest
was `complete: false` (1 of 2 legs). `--resume` cannot be combined with `--submit-only`, so I ran a second identical
invocation into the same output directory, which completed (2 legs, `complete: true`). Jobs from the stopped invocation
that were not recorded in the manifest were not identified or collected and are not part of this result. The extracted-side
shard `klt-sim-afa888b806e0` (samples 36, 37, 38) **never started** (no `status.json` after 1800 s, code
`batch_poll_timeout`), so those three trials have no extracted value. Envelope `status: error` (231 rows passed, 0 failed,
9 errored); samples 36-38 are excluded from both sides so the two sides use the same trials. The shard was not re-run.
This is a fleet-capacity finding, not a simulation result.

## Statistical basis

One PVT point (typical process, **125 C**, 1.20 V); **77 of 80** trials compared; rungs at differential overdrive 0 /
+1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded but **does not
govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible and samples in
different jobs may share a noise stream. One-point result, not a corner-matrix or 45-point result, and not a DR-0002
verdict.

## Result

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 77:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 39 / 77 = 0.506 (0.397 .. 0.615) | 59 / 77 = 0.766 (0.660 .. 0.847) |
| +1.0 mV (`d_plus`) | 73 / 77 = 0.948 (0.874 .. 0.980) | 77 / 77 = 1.000 (0.952 .. 1.000) |
| -1.0 mV (`d_minus`) | 18 / 77 = 0.234 (0.153 .. 0.340) | 44 / 77 = 0.571 (0.460 .. 0.676) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs, the same form as the other points.
**Unlike the other points, the extracted `d_plus` rung sits at n (77/77), so it was clamped** with
`p = (k + 0.5) / (n + 1)`; the extracted fit is therefore less well determined than the schematic one. My fit routine was
re-implemented for this run (a simple coordinate search), not the one used for the earlier points, so small differences
from that routine are possible.

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.96 mV | -0.16 mV |
| extracted | 1.38 mV (clamped rung) | -1.20 mV |

- The extracted static threshold is about -1.2 mV, the same sign as the other points (-0.4 .. -0.7 mV at most points,
  -1.3 mV at ss / 125 C). It is a layout-induced systematic offset; it does not by itself say whether DR-0002's bound is
  met.
- The extracted sigma is higher than schematic here (1.38 vs 0.96 mV), but with one clamped rung and n = 77 per rung
  this is **not** an established difference.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The noise Monte Carlo now has tt (1.08 V, 1.20 V, 1.32 V and 125 C), ss, ff, sf and fs points, several incomplete. The
other grid points, any DR-0002 noise or offset verdict, `td_c`, and the item-7 citation, hash and regenerated signoff
report. Item 7 stays `unmet`.

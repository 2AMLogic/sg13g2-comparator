# Whole-latch transient-noise Monte Carlo, N = 80 at ff / 125 C / 1.32 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1012+g31b24f439f3f` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-noise-tt-m40c-n80.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json
--envelope-out`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80, process `ff` (plain `mos_ff`, **no mismatch models**, as
the schematic bench), temperature 27 -> 125 C and vdd 1.20 -> 1.32 V, in an untracked throwaway copy (committed requests
unchanged; the copy's `netlist` path was made absolute). Extracted netlist sha256 `b313a02d...d51d47` (identical to the
other points). Data: `batch-mc-noise-ff-125c-132v-n80.20261101.json` (the 77 compared trials, both sides; the full
envelope is not committed).

## What went wrong in the run

Submit completed on the first try (54 jobs, `complete: true`). My first `--attach` passed the layout, deck and request
again and was refused (`shard map ... was submitted from a different request`, request hash `06aecff2fb67` vs
`d66aa883430a`); I did not investigate why. `--attach <pex-submit.json>` given alone (the manifest's recorded request)
worked. During that attach three batch jobs reported `failed`; the extracted side of trials `mc39`, `mc50` and `mc53`
has no value (9 rows `error`, 231 passed, 0 failed), so those trials are excluded from both sides below and the point
is **77 of 80**, kept as a finding. I did not re-run the failed jobs.

## Statistical basis

One PVT point (fast process, **125 C**, **1.32 V**); **77 of 80** trials compared; rungs at differential overdrive 0 /
+1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded but **does not
govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible and samples in
different jobs may share a noise stream. One-point result, not a corner-matrix or 45-point result, and not a DR-0002
verdict.

## Result (envelope `status: error`; 231 rows passed, 0 failed, 9 errored)

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 77:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 36 / 77 = 0.468 (0.360 .. 0.578) | 51 / 77 = 0.662 (0.551 .. 0.758) |
| +1.0 mV (`d_plus`) | 72 / 77 = 0.935 (0.857 .. 0.972) | 77 / 77 = 1.000 (0.952 .. 1.000) |
| -1.0 mV (`d_minus`) | 11 / 77 = 0.143 (0.082 .. 0.238) | 33 / 77 = 0.429 (0.324 .. 0.540) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs (a coordinate search, the same
routine as the other noise points; the fit script was a throwaway and is not committed). The extracted `d_plus` rung
sits at n (77/77) and was clamped with `p = (k + 0.5) / (n + 1)`.

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.79 mV | -0.00 mV |
| extracted | 1.19 mV (clamped rung) | -0.71 mV |

- The extracted static threshold is about -0.7 mV, the same sign as the other points and about the same as the nominal
  point (-0.7 mV); it is a layout-induced systematic offset and does not by itself say whether DR-0002's bound is met.
- The extracted `d_minus` rung (33 / 77) is clearly above the schematic's (11 / 77): the Wilson intervals do not
  overlap. That is this point's visible difference. The extracted sigma (1.19 mV) is above the schematic's (0.79 mV),
  but three rungs, two fitted parameters, one clamped rung and n = 77 per rung do not determine it, so **no sigma
  difference is established**.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The noise Monte Carlo now has tt (-40 C, 1.08 V, 1.20 V, 1.32 V and 125 C), ss, ff (-40 C and 125 C), sf and fs
points. The other grid points, any DR-0002 noise or offset verdict, `td_c`, and the item-7 citation, hash and
regenerated signoff report. Item 7 stays `unmet`.

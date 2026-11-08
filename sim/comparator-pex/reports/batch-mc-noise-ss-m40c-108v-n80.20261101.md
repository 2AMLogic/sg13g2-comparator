# Whole-latch transient-noise Monte Carlo, N = 80 at ss / -40 C / 1.08 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev1012+g31b24f439f3f` (development build, **not** a released client); fleet runner compatible (no
compatibility error). Same command shape as `batch-mc-noise-ff-125c-132v-n80.20261101.md`: `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), `--submit-only` then `--attach <outdir>/pex-submit.json
--envelope-out`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80, process `ss` (plain `mos_ss`, **no mismatch models**, as the
schematic bench), temperature 27 -> -40 C and vdd 1.20 -> 1.08 V, in an untracked throwaway copy (committed requests
unchanged; the copy's `netlist` path was made absolute). Extracted netlist sha256 `b313a02d...d51d47` (identical to the
other points). Data: `batch-mc-noise-ss-m40c-108v-n80.20261101.json` (all 80 trials, both sides; the full envelope is not
committed).

## What went wrong in the run

My first `--submit-only` was stopped by a 500 s `timeout` I put around it (my choice, not a fleet fault) before it wrote
a manifest, so it could not be resumed or attached. Some shard jobs from that invocation were already submitted; they were
not identified or collected and are not part of this result. The whole request was then submitted again into a fresh
output directory, which completed (`complete: true`, 54 jobs, both legs) and was attached once with the manifest alone.
Only that final submission is reported. No batch job failed.

## Statistical basis

One PVT point (slow process, **-40 C**, **1.08 V**); **80 of 80** trials compared; rungs at differential overdrive 0 /
+1.0 mV / -1.0 mV, each driven by its own `trnoise()` source. The request's seed (20260916) is recorded but **does not
govern** the noise (`klt` seeds `trnoise()` sources from the process id), so this run is not reproducible and samples in
different jobs may share a noise stream. One-point result, not a corner-matrix or 45-point result, and not a DR-0002
verdict.

## Result (envelope `status: pass`; 240 rows passed, 0 failed, 0 errored)

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 80:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 40 / 80 = 0.500 (0.393 .. 0.607) | 0 / 80 = 0.000 (0.000 .. 0.046) |
| +1.0 mV (`d_plus`) | 69 / 80 = 0.863 (0.770 .. 0.921) | 15 / 80 = 0.188 (0.117 .. 0.287) |
| -1.0 mV (`d_minus`) | 13 / 80 = 0.163 (0.097 .. 0.258) | 0 / 80 = 0.000 (0.000 .. 0.046) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares on the three rungs (a coordinate search, the same
routine as the other noise points; the fit script was a throwaway and is not committed). Two extracted rungs (`d_zero`,
`d_minus`) sit at 0 and were clamped with `p = (k + 0.5) / (n + 1)`.

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.97 mV | -0.02 mV |
| extracted | 0.62 mV (two clamped rungs, unreliable) | +1.55 mV (two clamped rungs, unreliable) |

- This is the largest extracted-versus-schematic difference of the noise points: the extracted latch decides LOW in
  every `d_zero` and `d_minus` trial and only 15 of 80 at +1.0 mV, while the schematic is at 0.50 at zero overdrive. The
  Wilson intervals do not overlap on `d_zero` or `d_plus`. The extracted static threshold is positive here (about
  +1.5 mV), the opposite sign to the other points (about -0.3 to -0.7 mV); with two clamped rungs and n = 80 it is only
  a rough indication, and the extracted sigma (0.62 mV) is not meaningful as a comparison.
- In 20 of the 80 extracted `d_plus` trials the sampled output at 5 ns is intermediate (0.05 .. 0.95 of vdd, 0.06 to
  0.90), i.e. not resolved at the sampling instant at this slow corner; those are counted by the 0.5 threshold, so the
  HIGH count on that rung depends on the sampling time. No schematic trial and no other extracted rung has an
  intermediate value. This is a decision-time (metastability) observation at ss / -40 C / 1.08 V, not a noise-floor
  number.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).
- I have not established whether the shift is layout parasitics, the extraction model, or the plain-`mos_ss` bench; no
  DR-0002 verdict is drawn.

## Not established / still open

The noise Monte Carlo now has tt (-40 C, 1.08 V, 1.20 V, 1.32 V and 125 C), ss (125 C and -40 C / 1.08 V), ff (-40 C and
125 C), sf and fs points. Any DR-0002 noise or offset verdict, `td_c`, and the item-7 citation, hash and regenerated
signoff report. Item 7 stays `unmet`.

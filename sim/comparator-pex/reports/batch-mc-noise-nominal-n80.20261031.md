# Whole-latch transient-noise Monte Carlo, N = 80 at the nominal point, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev909+gaaf8fbf68b2b` (development build, **not** a released client). `klt pex --backend batch
--max-units-per-job 3` (27 shard jobs per side), run as `--submit-only` then `--attach`; layout
`layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk ihp-sg13g2 --pins
clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` raised 3 -> 80 in an untracked throwaway copy (the committed
request is unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data:
`batch-mc-noise-nominal-n80.20261031.json` (all 80 trials, both sides, three rungs; the full envelope is not
committed).

## Statistical basis

One PVT point only: process `tt` (plain `mos_tt`, **no mismatch models**, as the schematic bench), 27 C, vdd 1.20 V;
N = 80 trials per rung; rungs at differential overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own `trnoise()`
source. The request's seed (20260916) is recorded but **does not govern** the noise: `klt` warns that `trnoise()`
sources are seeded from the process id, so this run is not reproducible and samples in different jobs may share a
noise stream. N is the only reproducibility lever. This is a one-point result, not a corner-matrix or 45-point
result, and not a DR-0002 verdict.

## Result (envelope `status: pass`; 240 rows passed, 0 failed, 0 errored; 80 trials compared)

Trials that decided HIGH (`v(dout)/vdd > 0.5`; every value was within 0.01 of a rail), with 95 % Wilson intervals:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 31 / 80 = 0.388 (0.288 .. 0.497) | 70 / 80 = 0.875 (0.785 .. 0.931) |
| +1.0 mV (`d_plus`) | 74 / 80 = 0.925 (0.846 .. 0.965) | 80 / 80 = 1.000 (0.954 .. 1.000) |
| -1.0 mV (`d_minus`) | 16 / 80 = 0.200 (0.127 .. 0.300) | 24 / 80 = 0.300 (0.211 .. 0.408) |

Fitting `p(od) = Phi((od - theta) / sigma)` to the three rungs by least squares on the probits (a rung at 0 or N is
clamped to a half count):

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.88 mV | -0.09 mV |
| extracted | 0.66 mV (clamped; see below) | -0.69 mV |

- The extracted latch shows a static threshold of about -0.7 mV: with zero overdrive and no mismatch it decides HIGH
  in 87 % of trials. The schematic is close to balanced at zero. This asymmetry is a layout-induced systematic
  offset that this one-point run exposes; it does not by itself say whether DR-0002's bound is met.
- The extracted `sigma` is **not** a measurement of lower noise. The `d_plus` rung saturated (80 / 80), so the fit
  clamps it and the extracted sigma is only a bound from that rung; the uncertainty on either sigma is large (each
  rung's binomial interval at N = 80 is 10 to 20 points wide). The schematic and extracted sigmas are not
  distinguishable at this N, and no claim of a noise improvement or degradation is made.
- `pass` means both sides produced a value; no tolerance is applied.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (38 / 26 extracted vs 12 / 12 schematic devices,
  finger decomposition).

## Failed first submissions (kept for the record)

- The first `--submit-only` timed out client-side at 500 s after 23 of 27 schematic shards were submitted and wrote
  no manifest. A `--resume` retry was refused (`--submit-only cannot be combined with --resume`). A fresh
  `--submit-only` then submitted all 54 shards. The 23 shards of the abandoned attempt were left on the fleet and
  their results were not collected.
- `klt pex --attach MANIFEST` requires the layout, `--deck` and the testbench argument again; with only the manifest it
  exits 2.

## Not established / still open

- The 45-point PVT noise grid (N = 80 per point, 3600 units), including ss / 125 C behaviour; the DR-0002
  transient-noise verdict; the 45-point offset grid and the offset verdict; `td_c`; the item-7 citation, hash and
  regenerated signoff report. Item 7 stays `unmet`; acceptance rows 3-4 remain open.
- Friction (generic, for `2AMLogic/klayout-tools`): a `klt pex --submit-only` that exceeds the client wait leaves
  already-submitted shards orphaned with no manifest and no resume path.

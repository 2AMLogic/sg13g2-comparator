# Whole-latch transient-noise Monte Carlo, N = 80 at fs / 27 C / 1.20 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev965+g5d8e4f2b5009` (development build, **not** a released client; the earlier points used
`dev958`, so this is a different dev build); fleet runner compatible (no compatibility error). Same command shape as
`batch-mc-noise-sf-27c-n80.20261031.md`: `klt pex --backend batch --max-units-per-job 3` (27 shard jobs per side),
`--submit-only` then `--attach`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator --pdk
ihp-sg13g2 --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `PDK_ROOT` from `sim/env.sh`. Nothing ran locally. Request:
`requests/noise.mc.probe.json` with `monte_carlo.n` 3 -> 80 and corners changed to process `fs` (plain `mos_fs`, **no
mismatch models**, as the schematic bench), 27 C, vdd 1.20 V, in an untracked throwaway copy (the committed requests are
unchanged). Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data:
`batch-mc-noise-fs-27c-n80.20261031.json` (the 77 compared trials, both sides, three rungs; the full envelope is not
committed).

## What went wrong in the run

`--submit-only` was cut off twice by my 540 s tool cap; the third identical invocation into the same output directory
finished it (exit 0). The single `--attach` was then cut off by my own 590 s tool cap: the client reported `interrupted
by client before this shard finished` and marked one 3-trial extracted shard (samples 51, 52, 53) lost. The envelope is
`status: error` (231 rows passed, 0 failed, 9 errored). The shard map is removed by an interrupted attach, so the shard was
not recovered and not re-run. This is a client-wait failure of mine, not a simulation result; it is kept as a finding.

## Statistical basis

One PVT point (skew corner: fast NMOS / slow PMOS); **77 of 80** trials compared (samples 51..53 excluded from both sides
so the two sides use the same trials); rungs at differential overdrive 0 / +1.0 mV / -1.0 mV, each driven by its own
`trnoise()` source. The request's seed (20260916) is recorded but **does not govern** the noise (`klt` seeds `trnoise()`
sources from the process id), so this run is not reproducible and samples in different jobs may share a noise stream.
One-point result, not a corner-matrix or 45-point result, and not a DR-0002 verdict.

## Result

Trials that decided HIGH (`v(dout)/vdd > 0.5`), 95 % Wilson intervals, n = 77:

| rung | schematic | extracted |
|---|---|---|
| overdrive 0 (`d_zero`) | 49 / 77 = 0.636 (0.525 .. 0.735) | 54 / 77 = 0.701 (0.592 .. 0.792) |
| +1.0 mV (`d_plus`) | 71 / 77 = 0.922 (0.840 .. 0.964) | 77 / 77 = 1.000 (0.952 .. 1.000) |
| -1.0 mV (`d_minus`) | 14 / 77 = 0.182 (0.112 .. 0.282) | 13 / 77 = 0.169 (0.101 .. 0.268) |

Probit fit `p(od) = Phi((od - theta) / sigma)` by least squares (a rung at 0 or n clamped to a half count), the same
routine as the other points (it reproduces the sf report's figures from its counts):

| | sigma (input-referred) | theta (static threshold) |
|---|---|---|
| schematic | 0.86 mV | -0.25 mV |
| extracted | 0.58 mV (the `d_plus` rung is clamped) | -0.40 mV |

- The extracted static threshold is about -0.4 mV, the same sign and size as the other points (-0.5 mV at ff / -40 C and
  sf, -0.7 mV at tt, -1.3 mV at ss / 125 C). It is a layout-induced systematic offset; it does not by itself say whether
  DR-0002's bound is met.
- The sigmas are **not** distinguishable: the extracted fit rests on a clamped rung and the per-rung binomial intervals
  at n = 77 are 10 to 20 points wide.
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The noise Monte Carlo now has tt, ss, ff, sf and fs points, the last one incomplete (77 of 80). The other 40 points of
the 45-point noise grid, the offset grid (41 points left), any DR-0002 noise or offset verdict, `td_c`, and the item-7
citation, hash and regenerated signoff report. Item 7 stays `unmet`.

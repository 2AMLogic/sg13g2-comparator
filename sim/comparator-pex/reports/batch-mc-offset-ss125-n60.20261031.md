# Whole-latch offset Monte Carlo, N = 60 at ss / 125 C / 1.08 V, schematic vs extracted (issue #61, acceptance row 3, partial)

Client `klt 0.8.1.dev914+g92d880ab835c` (development build, **not** a released client). Same command as
`batch-mc-offset-nominal-n60.20261031.md` (`klt pex --backend batch --max-units-per-job 3`, `--submit-only` then
`--attach`; `--attach` must be given the same `--max-units-per-job` or it fails with `resume_fingerprint_mismatch`).
Request: `requests/offset_mc.mc.probe.json` with `monte_carlo.n` 3 -> 60 and corners changed to process `ss`
(`mos_ss_mismatch`), 125 C, vdd 1.08 V, in an untracked throwaway copy (the committed requests are unchanged). Nothing
ran locally. Extracted netlist sha256 `b313a02d...d51d47` (the committed one). Data:
`batch-mc-offset-ss125-n60.20261031.json` (all 60 samples, both sides).

## Statistical basis

One PVT point (the slow/hot/low-supply extreme); `vary: mismatch`; N = 60; seed 20260916. Sigma is a Monte-Carlo
sigma at that point, quantized by the 3 mV `lowcount` staircase, not a 45-point or corner-matrix result.

## Result (envelope `status: pass`; 180 rows passed, 0 failed, 0 errored; 60 samples compared)

| `vos_mv` | mean | sigma (sample, N-1) | min .. max |
|---|---|---|---|
| schematic | +0.80 mV | 3.42 mV | -7.50 .. +7.50 |
| extracted | -0.40 mV | 3.75 mV | -7.50 .. +7.50 |
| per-sample extracted - schematic | -1.20 mV | 4.98 mV | |

- Extracted sigma is about 10 % above schematic, within the ~9 % relative uncertainty of each sigma at N = 60 and
  the 3 mV quantization: no difference is established. At the nominal point the same comparison gave 3.03 / 3.41 mV.
- `pass` means both sides produced a value; no tolerance is applied. **Not a DR-0002 verdict**; no ratified bound is
  compared or changed.
- `vbias_mv` is identical on both sides in all 60 samples (mean 296.66 mV, sigma 1.37 mV).
- `body_bias.status: biased`; `model_mismatch.kind: count_only` (finger decomposition differs).

## Not established / still open

The other 43 points of the 45-point offset grid (including ff / -40 C / 1.32 V), the noise grid, any DR-0002 offset
or noise verdict, `td_c`, and the item-7 citation, hash and regenerated signoff report. Item 7 stays `unmet`.

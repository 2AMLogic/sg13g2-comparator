# Whole-latch Monte Carlo requests: bounded extracted batch probe, 2026-10-31 (issue #61, acceptance row 3)

Client `klt 0.8.1.dev897+ga42d9de8d98d` (development build, not a released client), runner klt 0.8.0
(`runner_compatibility: match`; `corners.params`, `options.osdi_preload`, `options.stage_model_inputs` all
`supported`), ngspice-46 on a Spot c7i.4xlarge. `klt pex --backend batch --deck sg13g2 --top comparator`, layout
`layout/comparator/comparator.gds`, extracted netlist sha256 `b313a02d...d51d47`. Nothing was run locally.

## What was added

`make_testbenches.py` / `make_requests.py` now also derive, from the committed schematic benches
(`comparator-offset-transient-mc`, `comparator-transient-noise`), the bodies `dut/tb_offset_mc.sp`,
`dut/tb_noise.sp` and four requests: `requests/{offset_mc,noise}.mc.json` (the full 45-point PVT grid with
`monte_carlo` N = 60 / 80 per point, i.e. 2700 / 3600 units) and `requests/{offset_mc,noise}.mc.probe.json`
(tt / 27 C / 1.20 V, N = 3). Seed 20260916 is the schematic benches' own; `vary: mismatch`. `klt sim --dry-run`
validates all four. **The two full grids were not submitted** -- see "Not established".

## Probe results (N = 3 per bench; a runner check, not a statistic)

Data: `batch-mc-probe.offset_mc.20261031.json`, `batch-mc-probe.noise.20261031.json` (derived delta tables; the
47 KB envelopes are not committed). Both envelopes `status: pass`, 9 rows, 3 corners compared, 0 errored. The
`pass` status only means both sides produced a value: no tolerance is applied to these rows.

- **Offset** (`lowcount`, `vos_mv`; per-sample quantized to the 3 mV staircase step): schematic `vos_mv`
  4.50 / 4.50 / 1.50, extracted 1.50 / -4.50 / -4.50. The bias-pin anchor `vbias_mv` is identical on both sides
  (307.1 / 310.7 / 310.5), as it must be (the mirror is not in the layout). Mismatch draws are applied: the three
  samples differ. Three samples give no sigma and no schematic-versus-extracted conclusion.
- **Noise** (`d_zero`, `d_plus`, `d_minus`, supply-normalised decisions): extracted `d_zero` was ~0.9998 in all 3
  samples (decided high at zero overdrive); schematic `d_zero` was ~0 in 2 of 3. This is consistent with the
  earlier post-layout finding of `reports/devonly-attribution.20261011.md`, but 3 trials establish nothing
  statistical.
- `klt` warns that `trnoise()` sources are **not governed by `monte_carlo.seed`** (ngspice seeds them from the
  process id), and samples in separate jobs may share a noise stream. The noise request's seed is therefore
  recorded, not reproduced, as the schematic bench's README already documents; N is the only reproducibility lever.

## A failed first attempt (kept for the record)

The first offset probe (extracted jobs of the `out-offset-v1` attempt, not committed) errored on `lowcount` on
**both** sides: `measurement 'lowcount' produced no value`. Cause: the 33 per-level `dlevK` reads live in the
original bench's control loop, so the derived body had none for `lowcount` to sum. This was a defect in
`make_testbenches.py` (now emits them as body `.meas` cards), not a runner or layout fault; the probe above is the
re-run on the fixed body.

## Not established / still open

- The full MC grids (2700 + 3600 units, extracted runs ~420 s/unit in the regeneration grid, so offset alone is
  of order days of unit time): not submitted this pass, so there is **no offset sigma, no transient-noise floor and
  no DR-0002 row result** for the extracted layout. Sharding (`--max-units-per-job`) and a sample-count decision
  belong with the grid run; no ratified bound is relaxed here.
- The 3 ss / 125 C regeneration corners, `td_c`, the item-7 citation/hash and the regenerated signoff report.
  Item 7 is unchanged (`unmet`); acceptance rows 3-4 stay open.
- Friction (generic; filed as 2AMLogic/klayout-tools#4692): `klt pex
  --format json` writes the envelope to stdout while `-o` receives the extracted netlist; a second `klt pex` on
  the same `--outdir` fails with `outdir_locked` while an `--attach` is still running.

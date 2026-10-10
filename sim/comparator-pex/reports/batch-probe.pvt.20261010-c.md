# Third 2026-10-10 batch probe: full `klt pex` PVT run on the fleet (issue #61)

New append-only record. No earlier record was edited.

## What was submitted (one submit each, nothing launched locally)

1. **`klt pex` over both PVT testbenches on `--backend batch`** (about 11:42Z to 11:46Z, klt 0.7.0+g8eec069c7576, KLayout 0.30.12, `PDK_ROOT` from `sim/env.sh`):

   ```bash
   klt pex layout/comparator/comparator.gds \
     sim/comparator-pex/requests/regeneration.pvt.staged-tmp.json \
     sim/comparator-pex/requests/kickback.pvt.staged-tmp.json \
     --deck sg13g2 --top comparator --pdk ihp-sg13g2 --pdk-root "$PDK_ROOT" \
     --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss --backend batch \
     --outdir <tmp> -o <tmp>/comparator.pex.spice --format json
   ```

   The `*.staged-tmp.json` files were throwaway copies of the committed `requests/{regeneration,kickback}.pvt.json` with `options.stage_model_inputs: true` added. They sat beside the committed requests because of the relative `netlist` path, and were deleted afterwards.
   Exit 4. Envelope `pex.batch-probe.pvt.20261010-c.json` (verbatim): `status: error`, 2 testbenches x 45 corners, **1350 `delta[]` rows, all `error`, all values `null`**, every `coverage.skipped[]` reason `unavailable_comparison`. The envelope names no cause and no job id (upstream klayout-tools#2872).
2. **`klt sim` on the staged regeneration request, `--backend batch`** (about 11:46Z to 11:47Z), submitted only to recover the cause the pex envelope drops. Exit 4. Envelope `batch-probe.regeneration.pvt.20261010-c.json`. This time capacity was granted (Spot `c7i.4xlarge`, us-east-1c), but job **`klt-sim-f07e181de148`** failed after 5 s with exit 87, and all 45 corners report `batch_job_failed` / `runner_code: batch_runner_version_mismatch`: "the fleet runner runs klt 0.5.0 but the submitting client is 0.7.0+g8eec069c7576 -- the request was not run". `environment.remote.runner_compatibility: mismatch`.
   One edit from the raw output, made for provenance hygiene (`klt env-provenance scan`): `environment.ngspice_binary` was an absolute host path. It has been reduced to the basename `ngspice`, the form the 20261009 record already uses. Nothing else was changed.

## Consequence

- Same root cause as the 20261009 record: the fleet runner image is klt 0.5.0. Capacity is no longer the blocker (compare `20261010`/`20261010-b`, both `batch_no_capacity`). A 0.5.0 client via `uvx` is not a workaround either: 0.5.0 has no `osdi_preload` support, so no SG13G2 deck elaborates (see `../README.md`, "Why nothing simulated", item 2).
- The PVT grids (regeneration, kickback) and the offset-sigma / transient-noise Monte Carlo rows on the extracted netlist remain **not run**. No schematic-vs-extracted delta exists beyond the single nominal corner in `delta-nominal-20261009.{md,json}` (tt / 1.20 V / 27 C, deterministic, no MC, no seeds, no sigma).
- Item 7 stays `unmet` / `check_failed`. The manifest citation and `manifests/t1-signoff-report.json` are unchanged. DR-0002 is untouched.
- Unblock: a fleet runner image with klt >= 0.7 and SG13G2 OSDI support. That is a change to the worker/fleet spec, not to this repo.

## Friction

- Already open and hit again: klayout-tools#2872 (pex drops per-corner diagnostics and job ids), #2851 / #2948 / #3015 (runner/client skew), #2901 (old runner drops newer options).
- New, filed with this record: **klayout-tools#3054**. `model_mismatch` fires when the model sets are identical and only the instance counts differ (finger decomposition), and its detail text says the models diverge. Both this envelope and the cited `layout/comparator/pex_report.json` carry it: `reference_only` and `extracted_only` are empty, and the counts are 12+12 (schematic) vs 38+26 (extracted fingers). It is not a model-flavour divergence.

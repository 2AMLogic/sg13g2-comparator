# Second batch re-probe of the 45-point PVT grid (issue #61), 2026-10-10

New append-only record; no earlier record was edited.

- Command: `klt sim <regeneration.pvt.json + options.stage_model_inputs: true> --backend batch --format json`
  (staging flag in a throwaway copy placed beside the committed request, deleted afterwards; `PDK_ROOT` from `sim/env.sh`), klt 0.7.0.
- Result: submit refused again, `batch_no_capacity` ("no capacity in any of the 30 pools after 3 attempt(s)"). No job was created.
- Consequence: PVT grids and the offset-sigma / noise Monte Carlo rows remain not run. No local grid was launched (host rule). DR-0002 untouched.
- Raw output: `batch-probe.regeneration.pvt.20261010-b.json`.
- Related open friction at `2AMLogic/klayout-tools`: #2948, #2851, #3015 (runner/client skew), #2917 (capacity_wait_s). Nothing new filed.

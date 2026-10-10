# Batch re-probe of the 45-point PVT grid (issue #61), 2026-10-10

New append-only record; no earlier record was edited.

- Command: `klt sim <regeneration.pvt.json + options.stage_model_inputs: true> --backend batch --format json`
  (staging flag in a throwaway copy of `requests/regeneration.pvt.json`; committed request unchanged), klt 0.7.0.
- Result: submit refused, `batch_no_capacity` ("no capacity in any of the 30 pools after 3 attempt(s)").
  No job was created, so the runner-version question (0.5.0 vs 0.7.0, see the 2026-10-09 record) was not re-tested.
- Consequence: the PVT grids and the offset-sigma / noise Monte Carlo rows remain not-run. No local grid was launched (host rule).
  Nothing here is a pass; DR-0002 untouched.
- Raw output: `batch-probe.regeneration.pvt.20261010.json`.

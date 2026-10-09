# Batch re-probe of the 45-point PVT grid (issue #61), 2026-10-09

New append-only record; no earlier record was edited.

- Command: `klt sim <regeneration.pvt.json + options.stage_model_inputs: true> --backend batch --format json`
  (the staging flag was added in a throwaway copy of `requests/regeneration.pvt.json`; the committed request is unchanged).
  Without the flag, `klt pex --backend batch` refuses at submit: `options.osdi_preload is not supported for backend 'batch'`.
- Result: capacity was available this time (job `klt-sim-531a187b367f`, spot `c7i.8xlarge`), but the job failed in 5 s,
  exit code 87, on all 45 corners: `batch_job_failed` -- "the fleet runner runs klt 0.5.0 but the submitting client is
  0.7.0 -- the request was not run (update the runner image or use a compatible client)".
  `klt pex` over the same request returned `status: error`, 540 `delta[]` rows, all values null (the schematic leg fails first).
- Consequence: no extracted-side or schematic-side PVT/Monte Carlo value exists. No local grid was launched (host rule).
  Nothing here is a pass. Upstream: klayout-tools #2851, #2948, #2901, #2872 already track this.
- Raw output: `batch-probe.regeneration.pvt.20261009.json`.

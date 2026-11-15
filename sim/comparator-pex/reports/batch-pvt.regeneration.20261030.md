# Full regeneration PVT batch outcome, 2026-10-30 (issue #61, acceptance row 2)

Client `klt 0.8.1.dev750+g3707af127575`, `--backend batch`, `PDK_ROOT` from `sim/env.sh`.
Request: `requests/regeneration.pvt.json` (45 units: 5 process corners x 3 temperatures x 3 supplies,
`options.timeout_s` 3480). Companion to `batch-probe.regeneration.nominal.20261030.md`, which recorded the
passing 1-corner probe and left this job's outcome unknown.

## Result: no usable data, all 45 units errored

Job `klt-sim-f2a0ffdf742c` (instance m7i.4xlarge, spot) was re-read with `--job-status` (`state: running`,
`elapsed_seconds: 3`, `updated_at` unchanged for about an hour) and then collected with `--attach`. Every unit
reports `batch_job_timeout`: the job "finished 'timeout' without a usable report: job exceeded 3600s";
the collected `report.json` was empty/invalid and no engine log was retrievable. Zero measurements were
produced, so no schematic-versus-extracted delta exists for any PVT corner. This is a failed run, not a pass.

## Resubmission with a split was refused by the client, nothing was submitted

`--max-units-per-job 9 --max-concurrent-jobs 2` was rejected before submit: "leaves a job of 9 units, over the
1-unit limit the fleet's 3600s whole-job ceiling allows at options.timeout_s 3480; use at most 1". The client
sizes jobs from the declared per-unit timeout, not a measured runtime, and the probe receipt records no per-unit
runtime. Splitting to 45 single-unit jobs on a guessed runtime was not attempted. No grid was run locally.

## Not established

The per-corner runtime of the whole-latch extracted regeneration bench, and therefore whether the 45-corner
grid fits the fleet in any split. Acceptance rows 2-4 (PVT results, extracted Monte Carlo, citation update)
remain open.

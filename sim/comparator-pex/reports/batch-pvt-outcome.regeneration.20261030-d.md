# Outcome of the 45-unit extracted regeneration batch job, 2026-10-30 (issue #61, acceptance row 2)

Client `klt 0.8.1.dev756+g73edb5d655c3`, `--backend batch`, `PDK_ROOT` from `sim/env.sh`. Resolves the unknown
left by `batch-pvt-attach.regeneration.20261030-c.md` for job `klt-sim-c4adab23fc10` (request
`requests/regeneration.pvt.json`, `timeout_s` 600, launched 2026-10-30T03:22:50Z). Read-only: nothing was
submitted and nothing ran locally.

## Observed

- `--job-status` at 2026-10-30T05:04:27Z: `state: failed`, `detail: job command exited 4`, `elapsed_seconds: 3453`,
  `updated_at: 2026-10-30T04:20:46Z`, instance `m7i.4xlarge` (spot, us-east-1d). The earlier "frozen at 14 s"
  reading was a stale status record, not a lost job.
- `--attach` collected the report (exit 4; netlist `sim/comparator-pex/dut/tb_regeneration.sp`; ngspice 46;
  `pdk_stamp: match`; `models_staged: true`): `corners: 45  passed: 5  failed: 0  errored: 40  inconclusive: 0`.
- All 40 errors carry the same diagnostic: `timeout - ngspice did not complete within 600s, killed`, plus
  `measurement produced no value` for every measurement of that unit. No unit failed a spec row.
- The 5 passing units are all `sf/novdd` (27 C `vdd_val` 1.2 and 1.32; 125 C `vdd_val` 1.08, 1.2 and 1.32) at
  420.0 to 424.5 s. They are the only units that finished inside the limit.

## Result: still no usable PVT data

The extracted side of the grid is 40 of 45 timeouts; no schematic-versus-extracted delta table or item-7 verdict
can be built from 5 passes at one process corner. This is not a pass, and not a spec failure: the
measurements were never produced. Acceptance rows 2-4 remain open.

## Finding: the 600 s `timeout_s` is too tight for the extracted netlist

`batch-pvt-sizing.regeneration.20261030-b.md` sized `timeout_s` 600 from a 3-unit schematic-side sample at about
173 s/unit. The extracted netlist's passing units take about 424 s, 2.4x the schematic figure, and 40 of 45 units
did not finish in 600 s, so the true extracted runtime is above 600 s for most of the grid and is not bounded by
this run. A lumped-RC extracted unit under shared-instance load is the likely cause; this run does not isolate
that. The 600 s value was chosen to let the client split the grid under the fleet's 3600 s whole-job ceiling, so a
larger value reopens that trade-off.

## Not established

The extracted per-unit runtime distribution, and whether the extracted grid fits the fleet at any `timeout_s`
that completes it. `klt pex` still has neither `--max-units-per-job` nor `--max-concurrent-jobs`, so the next
attempt needs either a larger `timeout_s` with sharded `klt sim` requests for the extracted side, or a measured
extracted-side sample first. Neither change is made here.

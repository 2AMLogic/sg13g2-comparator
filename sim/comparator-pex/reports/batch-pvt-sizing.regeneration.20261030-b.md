# Per-unit runtime and regenerated `timeout_s`, 2026-10-30 (issue #61, acceptance row 2)

Client `klt 0.8.1.dev756+g73edb5d655c3`, `--backend batch`, `PDK_ROOT` from `sim/env.sh`. Follow-up to
`batch-pvt.regeneration.20261030.md`, which left the per-unit runtime of the grid unestablished.

## Measured: schematic-side runtime, 3 units

A throwaway 3-unit copy of `requests/regeneration.pvt.json` (tt, 27 C, `vdd_val` 1.08/1.2/1.32, `timeout_s` 300,
deleted after the run; not committed) ran as job `klt-sim-c01a140b68dc` with `--wait-for-capacity 300
--fail-fast-probe`: 3 of 3 corners passed, 12 of 12 measurements reported, ngspice 46, `pdk_stamp: match`. The
client reported `runtime` 172.9 to 173.5 s per unit. This is a 3-unit schematic sample at one temperature and
process corner, not a statistic over the grid; extracted-side runtime is not measured.

## Change

`make_requests.py` now emits `timeout_s` 600 (about 3.4x the measured schematic unit), not 3480, so the client's
unit-count ceiling at the fleet's 3600 s whole-job limit is no longer 1; the four `requests/*.json` were regenerated
(`make_requests.py --check` clean). No other request field changed.

## Not established

`klt pex` has no `--max-units-per-job`/`--max-concurrent-jobs`; it submitted the whole 45-unit
`regeneration.pvt.json` as one job (`klt-sim-c4adab23fc10`, launched 2026-10-30T03:22:50Z, request sha256
`c6261a58a748a35e6fbbfdcf8516ad67109df4508db2f32f58fca7c08b39c6d7`) and the client was stopped by this run's own 300 s wall cap. `--job-status` still
showed `running`, `elapsed_seconds: 14`, `updated_at` 03:23:27Z at 03:29Z (status not advancing, as in the
earlier timeout case). Its outcome is unknown; no result is recorded and no extracted measurement, delta or
item-7 verdict exists. Nothing was run locally. Rows 2-4 stay open; the open question is whether `klt pex` can
split a grid, or the schematic and extracted sides need separate `klt sim` requests with `--max-units-per-job`.

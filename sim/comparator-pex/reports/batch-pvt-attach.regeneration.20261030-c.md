# Outcome of the 45-unit extracted regeneration batch job, 2026-10-30 (issue #61, acceptance row 2)

Client `klt 0.8.1.dev756+g73edb5d655c3`, `--backend batch`, `PDK_ROOT` from `sim/env.sh`. Follow-up to
`batch-pvt-sizing.regeneration.20261030-b.md`, which left job `klt-sim-c4adab23fc10` (request
`requests/regeneration.pvt.json`, `timeout_s` 600, launched 2026-10-30T03:22:50Z) with an unknown outcome.

## Observed (read-only; nothing submitted, nothing run locally)

- `klt sim <request> --backend batch --job-status klt-sim-c4adab23fc10` at 2026-10-30T04:0xZ: `state: running`,
  `detail: executing`, `elapsed_seconds: 14`, `updated_at: 2026-10-30T03:23:27Z`. The status record has not
  advanced for about 45 minutes, although the job's per-unit timeout is 600 s.
- `klt sim <request> --backend batch --attach klt-sim-c4adab23fc10` was left to run for 280 s and was
  terminated by the wall cap with no output and no report collected.

## Result: still no usable data

No measurement, schematic-versus-extracted delta or item-7 verdict exists for any PVT corner. This is not a
pass. Acceptance rows 2-4 remain open.

## Not established

Whether the job is alive (the status heartbeat stopped at 14 s) or was lost with its spot instance, and whether
the 45 extracted units fit the fleet. `klt pex` accepts neither `--max-units-per-job` nor
`--max-concurrent-jobs`, so the whole grid goes as one job; the only sharding route is separate `klt sim`
requests for the schematic and extracted sides. That change is not made here.

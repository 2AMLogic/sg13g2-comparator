# Extracted-side 3-unit batch sample, 2026-10-30 (issue #61, acceptance row 2)

Client `klt 0.8.1.dev761+g59994ae19827`, `klt pex --backend batch`, `PDK_ROOT` from `sim/env.sh`. Follow-up to
`batch-pvt-outcome.regeneration.20261030-d.md`, which left the extracted per-unit runtime unmeasured.

## Run

Throwaway request (not committed): `requests/regeneration.pvt.json` restricted to tt / 27 C / `vdd_val` 1.08, 1.2,
1.32, `timeout_s` 1800, same netlist, measurements and OSDI preload. Layout `layout/comparator/comparator.gds`,
`--deck sg13g2 --top comparator`. Two batch jobs, nothing run locally:

- schematic side `klt-sim-d2c797e916d3`: 3/3 corners `pass`, job `elapsed_seconds` 166.
- extracted side `klt-sim-e43af5ccce66`: 3/3 corners `error`, job `elapsed_seconds` 230. Runner `runner_request_features:
  supported`, `pdk_stamp: match`, `engine_build_comparison: mismatch` (reported by klt, not investigated here).

Envelope `status: error`; `body_bias.status: biased`. The full envelope is not committed (54 KB, carries a host
ngspice path); these figures are copied from it.

## Findings

- Extracted units complete in well under the 600 s limit when run as a small job: 230 s for 3 units, against the
  420 to 424 s per passing unit in the 45-unit job. The earlier timeouts therefore track grid size or fleet load, not
  an extracted netlist that needs more than 600 s per unit. This is one 3-unit sample; it does not bound the grid.
- All 3 extracted units fail the same way: `measurement 'td_c' produced no value -- ngspice reported: out of
  interval`. The other measurements of the unit reported. The schematic side produced `td_c` at the same corners, so
  this is a post-layout result (the decision edge falls outside the `.meas` window on the lumped-RC netlist), not a
  runner fault. Its cause is not isolated here. It is not a spec-row pass or fail.
- No schematic-versus-extracted delta table exists for these units; the delta rows for `td_c` are `error`.

## Not established

Why `td_c` does not fire on the extracted netlist; whether the 45-unit grid completes at `timeout_s` 600 when split;
Monte Carlo behavior. Item 7 is unchanged and rows 2-4 stay open.

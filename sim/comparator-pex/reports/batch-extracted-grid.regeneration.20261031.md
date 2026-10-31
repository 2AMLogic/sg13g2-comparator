# Extracted 45-corner regeneration grid via sharded batch, 2026-10-31 (issue #61, acceptance rows 1-2)

Client `klt 0.8.1.dev887+g2e9ee1aa66cf` (a development build, **not** a released client; PyPI `klayout-tools` 0.8.0
has no `klt pex --submit-only/--attach/--max-units-per-job`, checked with `uvx --from klayout-tools==0.8.0`).
`klt pex --backend batch`, layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top comparator`,
`PDK_ROOT` from `sim/env.sh`. Nothing was run locally. The extracted netlist is the committed one (sha256
`b313a02d...d51d47` as hashed by this client's manifest). Data: `batch-extracted-grid.regeneration.20261031.json`
(derived table of the 540 `delta[]` rows; the 6.6 MB envelope is not committed).

## Steps

1. **Bounded probe** (3 units, tt / 27 C / `vdd_val` 1.08, 1.2, 1.32, `timeout_s` 1800; throwaway request, not
   committed). `--submit-only` exited 0 with a manifest (jobs `klt-sim-b92fa53541b3` schematic,
   `klt-sim-b3fcedb1c2eb` extracted); `--attach` returned a normal envelope with 33 of 36 delta rows compared and the
   three `td_c` rows `error`. So async submit/collect works end to end on the fleet with this client.
2. **Full grid** (`requests/regeneration.pvt.json` with `options.timeout_s` raised 600 -> 900 in a throwaway copy,
   `--max-units-per-job 3`, so 15 shard jobs per side). `--submit-only` with sharding did not return within a 500 s
   cap (shard submission is about 20 s each; 22 of 30 jobs were submitted when the cap killed the client and no
   `pex-submit.json` was written). The run was continued with the blocking `--resume` form, which re-attached to the
   recorded shards.

## Result (envelope `status: error`; 45 corners; 462 rows passed, 0 failed, 78 errored)

- **42 of 45 corners compared on both sides**, across all of tt/ff/ss/fs/sf x vdd 1.08/1.2/1.32 x -40/27/125 C except
  below. Every schematic row is `pass` (540/540).
- **3 corners not measured: ss / 125 C / `vdd_val` 1.08, 1.2, 1.32.** One extracted shard was submitted but never
  launched (`klt sim: 1 of 15 batch job(s) were submitted but never launched`). Two further `--resume` attempts
  (jobs `klt-sim-3f2115dc2441`, `klt-sim-018e97ce238c`) each launched a fresh job that was still `running` at the
  570 s cap, which terminated the client; those envelopes are all-`error` interruptions and carry no data. The
  fleet has no cancel, so both jobs may still be running. These three corners are an unmeasured gap, not a pass.
- **`td_c` has no extracted value at any of the 45 corners** (`out of interval`). Same finding as the 3-unit sample
  and as `devonly-attribution.20261011.md` (`dc_first` already high before the input flip on full PEX). It is a
  post-layout result, not a runner fault; its cause is not re-isolated here. `td_c` rows are `error`, not pass/fail.
- Schematic-versus-extracted deltas over the 42 compared corners (`delta_pct`, schematic as reference):

  | row | median | min .. max |
  |---|---|---|
  | `td_a` | +189.8 % | +115.6 .. +266.5 |
  | `td_b` | +185.1 % | +109.3 .. +264.1 |
  | `q_dec` | -12.1 % | -24.8 .. -8.6 |
  | `i_stat` | -0.1 % | -0.1 .. +0.9 |
  | `vsup_v`, `da_end`, `db_end`, `dc_end` | 0.0 % | 0.0 .. 0.0 |
  | `da_first`, `db_first`, `dc_first` | not meaningful | see below |

  `*_first` rows record the first sampled value of a node, a near-zero quantity on the schematic side, so their
  percentage deltas (up to 1.5e12 %) are artifacts of a near-zero denominator and are not read as findings; use the
  absolute `schematic_value` / `extracted_value` in the JSON.
- These are schematic-versus-extracted deltas on the lumped-RC model, **not** DR-0002 spec-row verdicts, and carry
  no sigma. `body_bias.status: biased`. `model_mismatch.kind: count_only` (12 nmos / 12 pmos schematic vs 38 / 26
  extracted instances, finger decomposition). `extraction.model` is the lumped model quoted in
  `layout/comparator/pex_report.json`.

## Not established / still open

- The 3 ss/125 C corners; the kickback PVT request; whole-latch extracted offset and transient-noise Monte Carlo
  (no requests exist yet); the updated item-7 citation, hash and regenerated signoff report. Item 7 is unchanged
  (`unmet`); acceptance rows 2-4 stay open, row 1 is satisfied only with a development client.
- Friction for `2AMLogic/klayout-tools` (generic): `klt pex --submit-only` with sharding submits shards serially and
  does not return within several minutes, so a bounded caller is killed before the manifest is written and the
  submitted jobs cannot be collected through `--attach`; `--resume` re-launches an unlaunched shard under a new job
  id on every call.

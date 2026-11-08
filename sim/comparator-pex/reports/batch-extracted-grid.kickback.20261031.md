# Extracted 45-corner kickback grid via sharded batch, 2026-10-31 (issue #61, acceptance row 2)

Client `klt 0.8.1.dev897+ga42d9de8d98d` (a development build, **not** a released client). `klt pex --backend batch
--max-units-per-job 3` (15 shard jobs per side), layout `layout/comparator/comparator.gds`, `--deck sg13g2 --top
comparator`, `PDK_ROOT` from `sim/env.sh`, blocking form (no `--submit-only`). Request:
`requests/kickback.pvt.json` with `options.timeout_s` raised 600 -> 900 in an untracked throwaway copy (the committed
request is unchanged). Nothing was run locally. Extracted netlist sha256 `b313a02d...d51d47` (the committed one).
Data: `batch-extracted-grid.kickback.20261031.json` (derived table of the 810 `delta[]` rows; the full envelope is
not committed).

## Result (envelope `status: pass`; 45 corners; 810 rows passed, 0 failed, 0 errored)

- **All 45 corners (tt/ff/ss/fs/sf x vdd 1.08/1.2/1.32 x -40/27/125 C) measured on both sides**; every schematic row is
  `pass`; no `backend_failure`. Unlike the regeneration grid there is no unmeasured corner.
- `pass` here means both sides produced a value for the row; it is **not** a DR-0002 spec verdict.
- Schematic-versus-extracted deltas over the 45 corners (`delta_pct`, schematic as reference):

  | row | median | min .. max |
  |---|---|---|
  | `ad_pos` | -7.8 % | -9.5 .. -6.4 |
  | `ad_neg` | -14.1 % | -18.5 .. -10.0 |
  | `apmax` | -1.3 % | -1.4 .. -1.1 |
  | `apmin` | -0.9 % | -1.2 .. -0.6 |
  | `bc1` | -21.6 % | -731.3 .. +0.1 |
  | `bc0` | +0.1 % | -11.5 .. +1.1 |
  | `ap0`, `da_end`, `db_end`, `dc_end` | 0.0 % | 0.0 .. 0.0 |
  | `bd0`, `bd1`, `cd0`, `cd1`, `bp0`, `bn0`, `bp1`, `bn1` | within +-0.2 % | see JSON |

  `bc0`/`bc1` have schematic values that cross or sit near zero at some corners (`bc1` schematic min -1.6e-3), so
  their large percentage deltas are near-zero-denominator artifacts; use the absolute values in the JSON.
- These are lumped-RC schematic-versus-extracted deltas, **not** DR-0002 verdicts, and carry no sigma.
  `body_bias.status: biased` (0 unbiased devices). `model_mismatch.kind: count_only` (12 nmos / 12 pmos schematic vs
  38 / 26 extracted, finger decomposition). `extraction.model` is the lumped model quoted in
  `layout/comparator/pex_report.json`.

## Not established / still open

- The 3 ss / 125 C regeneration corners (see `batch-extracted-grid.regeneration.20261031.md`); `td_c`, which has no
  extracted value at any corner; whole-latch extracted offset and transient-noise Monte Carlo (no requests exist yet);
  mapping these deltas onto DR-0002 kickback bounds; the updated item-7 citation, hash and regenerated signoff
  report. Item 7 is unchanged (`unmet`); acceptance rows 3-4 stay open.
- Friction relevant to `2AMLogic/klayout-tools` (generic): `klt pex --format json` writes the envelope to stdout while
  `-o` receives the extracted netlist, so a caller that expects the envelope at `-o` finds only stale or no JSON.

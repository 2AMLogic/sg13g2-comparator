# corners/

Generated netlists + raw ngspice logs, one subdirectory per
`run_mismatch_check.sh` invocation (named by UTC timestamp, e.g.
`20260909-052553/`). Each run directory holds four cases:

| file | corner (from `cornerMOSlv.lib`) | mismatch modelled? |
|---|---|---|
| `nmos-mismatch.spice` / `.log` / `.csv` | `mos_tt_mismatch` | yes — includes `sg13g2_moslv_mismatch.lib` + `sg13g2_moslv_mod_mismatch.lib` |
| `nmos-negctrl.spice` / `.log` / `.csv` | `mos_tt` | no — plain `sg13g2_moslv_mod.lib`, no `agauss()` terms at all |
| `pmos-mismatch.spice` / `.log` / `.csv` | `mos_tt_mismatch` | yes |
| `pmos-negctrl.spice` / `.log` / `.csv` | `mos_tt` | no |

## What `cornerMOSlv.lib`'s five extra `_mismatch` corners are

Per the installed SG13G2 PDK's `libs.tech/ngspice/models/cornerMOSlv.lib`
(pinned release: see `sim/pdk.json`), the LV MOS corner library defines the
usual five global-process corners (`mos_tt`, `mos_ss`, `mos_ff`, `mos_sf`,
`mos_fs` — one shared parameter set applied uniformly to every device in a
netlist) **plus** five parallel `_mismatch` corners
(`mos_tt_mismatch`/`mos_ss_mismatch`/`mos_ff_mismatch`/`mos_sf_mismatch`/
`mos_fs_mismatch`) that additionally `.include` two extra files:

- `sg13g2_moslv_mismatch.lib` — Pelgrom-style sigma coefficients
  (`sg13g2_lv_nmos_delvto_mm`, `_factuo_mm`, `_dw_mm`, `_dl_mm`, and the
  `_pmos_` equivalents).
- `sg13g2_moslv_mod_mismatch.lib` — redefines `sg13_lv_nmos`/`sg13_lv_pmos`
  with `agauss()`-bound `delvto`/`factuo`/`w`/`l` parameters, each scaled by
  `1/sqrt(m*l*w*1e12)` (standard Pelgrom area scaling) and gated by a
  per-instance `mm_ok` parameter (default 1).

This is **local mismatch** (an independent random draw per device
*instance*, even within one netlist) — distinct from the also-present
`mos_tt_stat` global-process-statistics corner (`sg13g2_moslv_stat.lib`),
which draws ONE random value per *netlist* (shared by every device in the
circuit) to represent wafer-to-wafer/lot-to-lot process spread, not
device-to-device mismatch. This experiment's fixture puts two nominally
identical devices in the SAME netlist specifically to distinguish the two:
under `mos_tt_mismatch`, M1 and M2 get independent random draws (nonzero
`dVgs` spread); under the plain `mos_tt` corner, there is no `agauss()` term
present at all, so `dVgs` is identically zero regardless of seed (the
negative control).

See `../README.md` for the finding and full methodology.

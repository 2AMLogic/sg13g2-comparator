# device-mismatch-confirm

**Finding: SG13G2's LV MOS models (`sg13_lv_nmos`/`sg13_lv_pmos`) DO carry
real per-instance local mismatch**, confirmed both by reading the PDK's own
model files and by simulation (a committed ngspice Monte Carlo testbench,
not just the reading) — this repo's offset-sigma evidence therefore uses
the **Monte Carlo** path, not the sensitivity-analysis fallback.

This answers this repo's `spec/porting-plan.md` "Next steps" item 2 (issue
#6, gap-to-T1 tracker [#3](https://github.com/2AMLogic/sg13g2-comparator/issues/3)
item 6). It governs every comparator spec row with a statistical basis —
**input-referred offset sigma** above all (see `README.md`'s target-spec
table, "Offset sigma" row) — and also the statistical-basis language on the
metastability/decision-time-vs-overdrive row, since both depend on which of
the two evidence worlds (Monte Carlo vs. sensitivity) this PDK's LV devices
live in.

## PDK evidence (a lead, confirmed against the installed checkout)

Confirmed directly against the installed PDK checkout used to produce this
directory's records (release `v0.3.0`, matching this checkout's own
`.fetched-version` file — see `sim/pdk.json` for the full pin):

- `libs.tech/ngspice/models/sg13g2_moslv_mismatch.lib` (lines 20-28) defines
  Pelgrom-style sigma coefficients:
  `sg13g2_lv_nmos_delvto_mm=0.0039`, `factuo_mm=0.005`, `dw_mm=4e-9`,
  `dl_mm=2e-9` (and `sg13g2_lv_pmos_*`: `0.0022`, `0.0033`, `4e-9`, `2e-9`) —
  exactly as cited in the issue.
- `libs.tech/ngspice/models/sg13g2_moslv_mod_mismatch.lib` defines
  `.subckt sg13_lv_nmos d g s b` at **line 66** and
  `.subckt sg13_lv_pmos d g s b` at **line 155** (both confirmed against
  this checkout — matches the issue's citation exactly), each with a
  default `mm_ok=1` instance parameter and per-instance variation applied
  via e.g.
  `delvto='agauss(0, sg13g2_lv_nmos_delvto_mm/sqrt(m*l*w*1e12), (mm_ok != 1 ? 0 : 1))'`
  — standard 1/sqrt(area) Pelgrom scaling, switchable off via `mm_ok=0`.
- `libs.tech/ngspice/models/cornerMOSlv.lib` wires these into five
  additional named `.LIB` blocks beyond the ordinary global corners:
  `mos_tt_mismatch`, `mos_ss_mismatch`, `mos_ff_mismatch`, `mos_sf_mismatch`,
  `mos_fs_mismatch` — each `.include`-ing both files above (confirmed: the
  `mos_tt_mismatch` block spans lines 118-160 of the installed checkout's
  copy).

This reading alone was strong evidence but not proof — see below for the
actual simulation that confirms it (and would have reported a disagreement
if one had appeared).

## Methodology

Two nominally identical LV devices (same `w`/`l`/`ng`/`m`), each
diode-connected (gate=drain) and biased at `Id=10uA` via an ideal current
source — the same single-device fixture topology as the PDK's own reference
Monte Carlo testcase
(`libs.tech/xschem/sg13g2_tests/mc_lv_{nmos,pmos}_cs_loop.sch`,
`libs.tech/xschem/simulations/scripts/MC_mos.py`) — instantiated **twice**
in one netlist so the two devices' `Vgs` can be directly differenced per
Monte Carlo draw: `dVgs = Vgs(M2) - Vgs(M1)` is the local-mismatch signature
under test. Both devices/PMOS+NMOS are tested, per the issue's "do both if
time allows."

- **Corner under test**: `mos_tt_mismatch` (per-instance local mismatch
  enabled, `mm_ok=1`).
- **Negative control**: the same fixture run against the plain `mos_tt`
  corner (no `agauss()` term present at all in that corner's device model),
  expected to show **exactly zero** `dVgs` spread regardless of seed — this
  is the check that the testbench methodology actually discriminates
  presence/absence of mismatch, not an artifact of the measurement itself.
- **Monte Carlo loop**: `set rndseed=1234` fixed once, then `N=30` `op` +
  `reset` iterations per case (confirmed empirically during this issue's
  investigation: `reset` is what forces the circuit to rebuild from the
  netlist text, which is what makes every `agauss()`-bound parameter
  re-draw on the next `op` — dropping `reset` freezes the same draw every
  iteration). This is the exact idiom the PDK's own
  `mc_lv_{nmos,pmos}_cs_loop.sch` testcases ship, adapted here from a
  single-device sweep to a two-device *difference* sweep.
- See `corners/README.md` for what each `cornerMOSlv.lib` corner means and
  why `mos_tt_mismatch` (local mismatch) is the right corner to test here,
  as opposed to `mos_tt_stat` (global process statistics — one shared draw
  per netlist, not a per-instance difference).

## Result (run `20260909-052553`, N=30, seed=1234)

| case | corner | mean dVgs (V) | std dVgs (V) | min | max |
|---|---|---|---|---|---|
| nmos-mismatch | mos_tt_mismatch | -1.755703e-03 | 6.905510e-03 | -1.436073e-02 | 8.568073e-03 |
| nmos-negctrl | mos_tt | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 |
| pmos-mismatch | mos_tt_mismatch | -9.822584e-04 | 6.061961e-03 | -1.250483e-02 | 1.528666e-02 |
| pmos-negctrl | mos_tt | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 | 0.000000e+00 |

The `_mismatch` corner produces nonzero, seed-varying `dVgs` spread on both
device types (std ~6-7 mV at this bias/geometry); the plain `mos_tt` corner
produces **identically zero** spread across all 30 draws for both device
types. This is the expected signature of real per-instance local mismatch,
and the negative control confirms the testbench methodology is sound (it
would show the same zero result on a testbench that could not detect
mismatch even if it were present). No disagreement with the PDK-reading
above was observed.

Full per-run raw data: `records/20260909-052553-{nmos,pmos}-{mismatch,negctrl}.csv`.
Full record with provenance: `records/20260909-052553.md`.
Generated netlists + raw ngspice logs: `corners/20260909-052553/`.

**Caveat on scope**: this is a *device-level* mismatch confirmation at one
bias point, one geometry, and the `tt` (typical) global corner only — it
establishes *which evidence world this PDK lives in* (Monte Carlo vs.
sensitivity fallback), not a comparator-level offset number. The actual
comparator input-referred offset sigma (README.md's "Offset sigma" row)
still requires `design/comparator.sch` to exist first (out of scope here,
see porting-plan next step 1) and a dedicated `sim/comparator-decision/`
Monte Carlo sweep across the full comparator circuit and PVT corners
(porting-plan next step 3).

## Evidence path this block adopts going forward

**Monte Carlo**, not the sensitivity-analysis fallback, for every
comparator statistical claim (offset sigma above all) — because SG13G2's
own LV device models ship real per-instance local mismatch, confirmed by
simulation. `README.md`'s "Offset sigma" row basis text and gap-to-T1
tracker issue #3 (item 6) are updated accordingly.

## Reproducing (cold start from a fresh PDK checkout)

```bash
# 1. Fetch IHP-Open-PDK v0.3.0 (see sim/pdk.json for the exact pinned
#    tarball + sha256), e.g. via klayout-tools' scripts/fetch-ihp-sg13g2.sh,
#    laid out as PDK_ROOT/ihp-sg13g2 (open_pdks-shaped install).
export PDK_ROOT=/path/to/ihp-open-pdk
export PDK=ihp-sg13g2

# 2. Build the psp103 OSDI compact model (the PSP103 Verilog-A model both
#    sg13_lv_nmos and sg13_lv_pmos instantiate) if PDK_ROOT/$PDK/libs.tech/
#    ngspice/osdi/psp103.osdi does not already exist -- same recipe
#    sg13g2-bandgap's sim/tools/build-osdi.sh uses (checksum-pinned
#    OpenVAF-Reloaded compiler, see that repo's sim/pdk.json
#    "osdi_toolchain" for the exact pins):
#      openvaf-r -D__NGSPICE__ \
#        -o "$PDK_ROOT/$PDK/libs.tech/ngspice/osdi/psp103.osdi" \
#        psp103.va
#    run from $PDK_ROOT/$PDK/libs.tech/verilog-a/psp103/ (or wherever this
#    PDK release's own openvaf-compile-va.sh resolves it).

# 3. Run the check (single documented cold-start invocation):
./sim/device-mismatch-confirm/run_mismatch_check.sh
```

This regenerates all four cases (`nmos-mismatch`, `nmos-negctrl`,
`pmos-mismatch`, `pmos-negctrl`) under a fresh timestamped run id, writing
generated netlists + logs to `corners/<run-id>/` and a summary record to
`records/<run-id>.md`. `run_mismatch_check.sh` sources the repo's
`sim/env.sh` to resolve `PDK_ROOT`/`PDK` automatically if not already set
(same resolution order — env vars, then `/usr/share/pdk`,
`/usr/local/share/pdk`, `~/share/pdk`, `~/.ciel`, `~/.volare` — as
`sg13g2-bandgap`'s `sim/env.sh`).

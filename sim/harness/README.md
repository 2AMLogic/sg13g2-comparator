# `sim/harness/` — corner-runner reference

Stdlib-only Python. No virtualenv, no dependencies. One entry point:
[`sim/run_corners.py`](../run_corners.py).

```
python3 sim/run_corners.py --check-env          # PDK, OSDI models, tools, pins, DUT contract
python3 sim/run_corners.py --list               # known experiments + grid size
python3 sim/run_corners.py <experiment> -j 8    # run the grid, mint a record
python3 sim/run_corners.py <experiment> --no-write    # run, print, record nothing
python3 sim/run_corners.py <experiment> --sabotage-corners   # negative control
```

Ported structurally from
[`2AMLogic/gf180-comparator`](https://github.com/2AMLogic/gf180-comparator)'s
`sim/harness/` (itself ported from `2AMLogic/gf180-sar-adc`), per this
repo's `CLAUDE.md` ("two-PDK twin with sg13g2-comparator ... keep benches
structurally identical") and `spec/porting-plan.md` next steps 3–4 (issue
#8). **The "Deliberate divergences" table below is the record of what
changed for IHP SG13G2 and why** — everything not named there is unchanged
from the gf180-comparator source.

## Modules

| module | responsibility |
|---|---|
| `pdk.py` | Locate the IHP SG13G2 install and its OSDI device models. No PDK path is ever hardcoded in a netlist. |
| `toolchain.py` | Check `sim/toolchain.json`'s pins **before** simulating anything. |
| `dut.py` | Bind and validate the device under test from `sim/dut.json`. |
| `corners.py` | The corner grid: `.LIB`-section bundles, PVT axes, and `sabotage()`. |
| `testbench.py` | Load and validate `tb.json` manifests and their netlist fragments. |
| `runner.py` | Compose one self-contained deck per PVT point (incl. the OSDI preflight) and run ngspice. |
| `report.py` | Evaluate checks, render the evidence record, write logs + snapshot. |
| `cli.py` | Argument surface and console summary. |

## Ownership boundary (why fragments look incomplete)

A testbench `.spice` file is a **fragment**, not a deck. The harness owns the
process-corner `.LIB` section, the OSDI preflight, `.temp`, the DUT netlist,
the `.control` block and `.end` — so that *one* netlist sweeps the whole PVT
grid without being edited. `testbench.validate_netlist()` refuses a fragment
that tries to own any of them, because a hardcoded `.temp 27` silently pins
every corner to room temperature and nothing downstream would notice.

The fragment gets these `.param`s, in this order (see `runner.py`'s
`compose_deck`):

1. the corner `.LIB` section (`cornerMOSlv.lib`) — **before** any `.param`
   line, because each `.LIB` section here carries dozens of its own internal
   `.param` lines (PSP103 binning coefficients) that do not survive a
   top-level `.param` placed ahead of them (confirmed empirically, issue #8).
2. `vdd_nom`, `vdd_val`, `temp_c` — the PVT point.
3. `sim/dut.json`'s `params` (`dut_ib`, `dut_vcm`) — the DUT's own operating
   point, stated once for all four benches.
4. the manifest's own `params`.

Then `.temp`, then `.options`, then the DUT netlist, then the fragment, then
the `.control` block — whose first commands are the OSDI `pre_osdi` loads
(see "OSDI preflight" below), ahead of even `set rndseed`.

**One consequence worth knowing.** Unlike gf180mcu, SG13G2 has no separable
global mismatch switch a fragment can flip after the model include — local
mismatch is baked into *which* `mos_*_mismatch` corner section a bench's
`tb.json` names, so there is nothing analogous to a stray `sw_stat_mismatch`
default to collapse a Monte Carlo to σ = 0. The corresponding silent-failure
mode here is a bench that fails to select a `_mismatch` corner at all (or
gets sabotaged into one) — `sim/comparator-offset-mc/`'s `tb.json` documents
the "σ = 0 while everything looks like it ran" trap for that mechanism in
its own `checks.sig_vos_mv.description`.

## OSDI preflight

SG13G2's PSP103-based MOS models and its `r3_cmc`-based resistor models are
Verilog-A, compiled to OSDI shared libraries that ngspice must
`pre_osdi`-load before any `sg13_lv_nmos`/`sg13_lv_pmos`/`rhigh`/...
subcircuit can be instantiated — gf180mcu's ordinary SPICE `.model` cards
have no equivalent step at all. `pdk.py`'s `Pdk.missing_osdi()` /
`REQUIRED_OSDI` name the four models every deck preflights
(`psp103.osdi`, `psp103_nqs.osdi`, `r3_cmc.osdi`, `mosvar.osdi`) —
**all four, not only the ones today's placeholder DUT instantiates**, so a
DUT swap to a design using more of the PDK's device families never silently
needs this function rebuilt. `--check-env` refuses to simulate (and points at
`sim/tools/build-osdi.sh`) if any are missing; `runner.py`'s `compose_deck`
emits one `pre_osdi` line per required model as the *first* commands inside
`.control`, ahead of every analysis. The `pre_osdi` path must be UNQUOTED
(`pre_osdi /path`, not `pre_osdi "/path"`) — gf180-comparator's own
`.include`/`.lib` convention, which this module otherwise follows,
silently fails ngspice's argument parsing for this one control command
(confirmed by direct A/B testing during issue #8).

`sim/tools/build-osdi.sh` — ported from `sg13g2-opamp`'s
`sim/tools/build-osdi.sh` (issue #8's Scope section names it as the source),
replacing the manual `openvaf-r` step `sim/device-mismatch-confirm/README.md`
previously documented — builds all four from the PDK's own pinned release
tarball with a checksum-pinned OpenVAF-Reloaded compiler; no third-party
`.osdi` binary is ever downloaded. It is a **documented step in the cold-start
path** (`sim/README.md` "Cold start"), run once per PDK install, not a
manual workaround outside the command surface above.

## Checks, and what they are for

A `checks` entry names a measurement and bounds it. The vocabulary:

| key | meaning |
|---|---|
| `min` / `max` | bound the value at every completed point |
| `min_spread_pct` / `max_spread_pct` | bound the peak-to-peak spread across the whole grid, as a % of the mean magnitude |
| `min_spread_pct_by_axis` / `max_spread_pct_by_axis` | the same, per axis (`process` / `temperature` / `supply`), evaluated on every slice where the other two axes are fixed — reported weakest → strongest |

An unknown key is a hard load error, not a warning: a silently-ignored
`min_spread_pct` is exactly the failure this vocabulary exists to prevent.

**The per-axis floors are the load-bearing ones.** A
`min_spread_pct_by_axis[process]` entry is not a design claim — it asserts
that the measurement *moves* when the process axis alone is swept, which is
the only automatic proof that the corner runner is really switching models.
`sim/selftest.sh` runs every bench under `--sabotage-corners` (every corner
bundle forced to plain `mos_tt`, names kept) and **requires the run to
fail**. If a sabotaged run passes, corner switching is not taking effect and
every downstream record is worthless. For `comparator-offset-mc` specifically,
sabotage also switches mismatch off (see "Deliberate divergences" below), so
its negative control covers both the process axis and the Monte-Carlo switch
at once.

Every run prints the observed per-axis weakest → strongest spread for every
measurement, so a floor can be calibrated the first time a check is authored
rather than only after a record exists.

## The corner grid this block adopts

`corners.py` defines the bundles. SG13G2's `cornerMOSlv.lib` is itself
already a self-contained global process switch for the one device family
this block's placeholder DUT instantiates (LV MOS) — no `design.ngspice`-style
global-switch include exists in this PDK at all (confirmed by reading the
installed checkout).

| set | corners | mismatch |
|---|---|---|
| `tt` | `tt` — smoke only, **not a valid evidence matrix** | off |
| `mos` *(default)* | `tt`, `ff`, `ss`, `fs`, `sf` | off |
| `mos_mismatch` | `tt_mismatch`, `ff_mismatch`, `ss_mismatch`, `fs_mismatch`, `sf_mismatch` | on — `comparator-offset-mc`'s corner set |

Axes: **−40 / 27 / 125 °C** and **1.2 V ±10 %** (1.08 / 1.20 / 1.32 V) — this
repo's LV core rail, per `CLAUDE.md` and `README.md`'s Supply row. The `mos`
set (and, separately, `mos_mismatch`) is therefore a **45-point**
full-factorial grid, and the corner-id convention is
`<process>_<temp>c_<supply>v` (e.g. `ss_-40c_1.08v`, `tt_mismatch_27c_1.20v`).

There is no `full` set (no `res_ff`/`res_ss` promotion): the placeholder
DUT's load is an ideal SPICE resistor, not a PDK resistor subckt, so there is
no resistor-model corner to bundle yet — `corners.py`'s module docstring
names this as a tracked extension point for the day a design binds a real
PDK resistor (`rsil`/`rhigh`/`rppd`), which **do** carry real per-instance
local mismatch on this PDK (unlike gf180mcu's, whose mismatch coefficient is
hard-set to zero — see `sim/comparator-offset-mc/README.md`).

## Deliberate divergences from `gf180-comparator`'s harness

| change | why |
|---|---|
| **PDK resolution** (`pdk.py`). `SG13G2_PDK_PATH` / `PDK_ROOT`+`PDK` (default `ihp-sg13g2`) / `sim/pdk.local.json` / `sim/pdk.json` / built-in search roots — same resolution order as this repo's own `sim/env.sh`. | gf180-comparator resolves `GF180_PDK_PATH` against an `open_pdks`-shaped gf180mcu install; the variable names and defaults are PDK-specific, the resolution *order* is not. |
| **OSDI preflight** (`pdk.py`'s `REQUIRED_OSDI`/`missing_osdi()`, `runner.py`'s `pre_osdi` lines, `--check-env`'s OSDI step, `sim/tools/build-osdi.sh`). | gf180mcu's MOS/resistor models are ordinary SPICE `.model` cards, usable the instant a corner `.lib` is included — no OSDI concept exists there at all. SG13G2's PSP103/`r3_cmc` Verilog-A models must be compiled and `pre_osdi`-loaded first; see "OSDI preflight" above. |
| **Corner bundles** (`corners.py`'s `FAMILIES`/`CORNERS`/`CORNER_SETS`). One family (`mos`), no `full`/resistor set. | gf180mcu bundles one `.lib` section per device family (MOS/BJT/diode/resistor) behind a shared `design.ngspice` global switch, and gf180-comparator promotes `res_ff`/`res_ss` because its front-end gain rides on poly sheet-rho. SG13G2's `cornerMOSlv.lib` is already a self-contained global switch for LV MOS alone, and this placeholder's load is an ideal resistor (no PDK resistor bound yet) — see "The corner grid this block adopts". |
| **Mismatch mechanism** (`corners.py`'s `mos_mismatch` corner set; no `.param sw_stat_mismatch=1` fragment line anywhere). | gf180mcu's local mismatch is a global `sw_stat_mismatch` switch a fragment sets *after* the model include (order-sensitive — the wrong order silently collapses σ to 0, which `sim/comparator-offset-mc/README.md`'s twin warns about there). SG13G2 has no such switch: mismatch is baked into which `cornerMOSlv.lib` `.LIB` section is loaded (`mos_tt` vs. `mos_tt_mismatch`), confirmed against the installed checkout during issue #6 (`sim/device-mismatch-confirm/README.md`). So the corner *is* the switch, and `comparator-offset-mc`'s `tb.json` sets nothing mismatch-related at all. |
| **Supply axis**: 1.2 V ±10 % (1.08 / 1.20 / 1.32 V), SG13G2's LV core rail. | gf180-comparator sweeps 3.3 V ±10 % (2.97 / 3.30 / 3.63 V), gf180mcu's rail. SG13G2 ships no 1.8 V-rated flavor (only 1.2 V LV core and 3.3 V HV I/O — `sg13g2-bandgap`'s DR-0002), and `CLAUDE.md`/`README.md` target the 1.2 V LV core. |
| **`.param` ordering** (`runner.py`'s `compose_deck`). Emitted *after* the corner `.LIB` line, not before it. | gf180-comparator's deck (like gf180-sar-adc's) emits every `.param` ahead of the model includes. SG13G2's `cornerMOSlv.lib` `.LIB` blocks each carry dozens of their own internal `.param` lines (PSP103 binning coefficients); a top-level `.param` placed before such a `.LIB` does not survive ngspice's parse of it (confirmed empirically, issue #8). |
| **`dut.py` / `sim/dut.json`** — unchanged in mechanism, kept because gf180-comparator already made this exact divergence from `gf180-sar-adc` for the same reason (topology not yet decided) and this repo is in the identical situation. | Not a new divergence — named here only so the chain of provenance (`gf180-sar-adc` → `gf180-comparator` → this repo) is traceable from one file. |

BJT and diode sections have no counterpart here at all (this PDK's `.LIB`
corner bundles are MOS-only); this block instantiates neither.

## Known measurement floors

**The `meas` result-precision floor is ~1 µV, and it is not a solver
setting.** ngspice's `meas`/`let`+`print` machinery returns roughly six
significant digits, so differencing two ~1.2 V node levels quantizes the
answer at ~1 µV before any `measure` expression touches it. Tightening
`reltol`/`vntol`/`abstol` buys solver accuracy but does **not** move this
floor. The way past it is to measure a quantity that is *already* small — a
behavioural node referenced near 0 V — which is what
`sim/comparator-kickback/` does, and it resolves the same physical quantity
about a thousand times finer. Both forms are in that bench's record so the
floor is visible rather than asserted.

**A variance term that should be exactly zero can round negative.**
`comparator-offset-mc`'s Monte-Carlo σ formulas (`sqrt(svaq/nmax -
(sva/nmax)^2)*1e3`, etc.) compute a population variance from two running
sums; when the underlying corner carries no mismatch at all (a plain
non-`_mismatch` `mos_*` section — e.g. `--corners tt`, or
`--sabotage-corners`, which forces every section to plain `mos_tt`), that
variance is mathematically ~0 but can land a few ULPs on the negative side of
zero from floating-point summation order. ngspice's `sqrt()` of a negative
real returns a **complex** result (`real,imag`), which does not match this
harness's `m_<name> = <float>` measurement regex at all — the point then
fails as "no measurements parsed" instead of cleanly reporting a near-zero σ.
Every `sqrt()` in `comparator-offset-mc/testbench/tb.json`'s `measure` block
is therefore guarded with `abs()` (issue #8) so the mismatch-off case reports
a clean, correctly-failing near-zero σ instead of a parse error; see that
file's `evidence.notes` for the full account. `sim/characterize.sh smoke` and
`sim/selftest.sh`'s nominal-point step also use `tt_mismatch`, not plain
`tt`, as `comparator-offset-mc`'s single quick corner for the same reason —
a real, if noisier, single-point Monte-Carlo draw is a more representative
smoke point for a bench whose whole job is measuring a mismatch-driven σ.

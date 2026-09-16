# `sim/`

xschem + ngspice testbenches and **append-only** results, on the SG13G2
1.2 V LV core rail.

Five experiments backing the four first-class rows of
[`README.md`'s target specification](../README.md#target-specification-ratified--dr-0002)
(the offset-σ row has two, deliberately — see below):

| experiment | row it backs | method |
|---|---|---|
| [`comparator-offset-mc/`](comparator-offset-mc/) | Offset σ (**lower bound**, front end only) | Monte Carlo on SG13G2's `mos_*_mismatch` per-instance local-mismatch models, `dc` sweep against the loop-broken `comparator_dut_analog` reduced sub-model |
| [`comparator-offset-transient-mc/`](comparator-offset-transient-mc/) | Offset σ (**whole latch**, strobe → decision) | Monte Carlo on the same `mos_*_mismatch` models, transient digital-staircase sweep against the un-reduced `comparator_dut` topology |
| [`comparator-preamp-noise/`](comparator-preamp-noise/) | Input-referred noise | `.noise`, total integrated output noise ÷ measured DC gain |
| [`comparator-regeneration/`](comparator-regeneration/) | Decision time vs. overdrive, **metastability** | transient overdrive ladder, τ extracted from it |
| [`comparator-kickback/`](comparator-kickback/) | **Kickback** | 1 kΩ source impedance *and* a floating high-Z input |

`comparator_dut` has no DC-resolvable operating point (DR-0001 Decision §3),
so `comparator-offset-mc`'s reduced sub-model was DR-0001's own named interim
path for that row (Consequence 2) rather than a design choice made from
scratch. Both experiments stay committed — see
[`comparator-offset-transient-mc/README.md`](comparator-offset-transient-mc/README.md#relationship-to-comparator-offset-mc)
for why retiring the reduced-sub-model bench was considered and rejected.

Metastability and kickback are first-class rows here, not appendices, per
[`CLAUDE.md`](../CLAUDE.md).

Plus one supporting confirmation, not a spec-row bench:

```
sim/device-mismatch-confirm/
                          issue #6: confirms SG13G2's LV MOS models carry
                          per-instance local mismatch (Monte Carlo evidence,
                          not just a PDK-model reading) -- see its own
                          README.md for the finding and methodology. This is
                          what makes the Monte Carlo evidence path (rather
                          than the sensitivity-analysis fallback) the right
                          one for comparator-offset-mc above.
```

> **Current status: the device under test is the DR-0001 schematic, and the
> spec table it is scored against is ratified by
> [DR-0002](../spec/decision-records/0002-target-spec-ratification.md).**
> Ratified is not met — DR-0002 records three rows the current design misses,
> and two rows whose evidence here is a lower bound that cannot certify
> compliance either way. `sim/dut.json` binds
> [`design/comparator.spice`](../design/comparator.spice) (`provenance:
> schematic`), regenerated from the xschem sources in
> [`design/`](../design/) per
> [`spec/decision-records/0001-comparator-topology.md`](../spec/decision-records/0001-comparator-topology.md):
> a single-tail StrongARM dynamic latch on `sg13_lv_nmos`/`sg13_lv_pmos`.
> Records made against it are no longer placeholder-banner'd, and the
> `20260916-*` ones are the evidence DR-0002 ratified the table on
> (`spec/porting-plan.md`'s third step in this chain, now taken). Their own
> Claim text still says they are "NOT evidence toward
> `README.md#target-specification`" — correct when written, superseded by
> DR-0002; `sim/` is append-only, so that text stays as-is rather than being
> rewritten. Earlier `provenance: placeholder` records made against
> [`sim/dut/placeholder_comparator.spice`](dut/) remain committed
> (append-only) and still carry their own banner. See
> [`sim/dut/README.md`](dut/README.md) for the full binding history and the
> `comparator_dut_analog` reduced-sub-model caveat.

## Cold start

Everything is stdlib Python plus ngspice; there is no virtualenv to create.

```bash
# 1. Install the pinned PDK (see sim/pdk.json for the exact release tag +
#    tarball sha256), e.g. via klayout-tools' scripts/fetch-ihp-sg13g2.sh,
#    laid out open_pdks-style as PDK_ROOT/ihp-sg13g2:
export PDK_ROOT=/path/to/pdk-root
export PDK=ihp-sg13g2

# 2. Install ngspice 46 or newer, built with OSDI support (Debian/Ubuntu:
#    apt-get install ngspice).

# 3. Build the OSDI device models (PSP103 MOS, r3_cmc resistors) IHP-Open-PDK
#    ships as Verilog-A source, not prebuilt binaries -- a one-time step per
#    PDK install, checksum-pinned OpenVAF-Reloaded compiler, no third-party
#    .osdi binary ever downloaded (sim/harness/README.md "OSDI preflight"):
sim/tools/build-osdi.sh

# 4. Verify PDK, OSDI models, tools, pins and the DUT interface contract:
python3 sim/run_corners.py --check-env

# 5. Smoke the whole command surface -- one nominal point per bench, seconds:
./sim/characterize.sh smoke

# 6. Prove the HARNESS itself works, including the sabotage negative control:
./sim/selftest.sh

# 7. Reproduce every committed record (full 45-point PVT grid per bench):
./sim/characterize.sh characterize
```

`source sim/env.sh` exports the same PDK environment the harness resolved, so
an interactive `ngspice` or `xschem` session sees exactly what the runner
does.

If your PDK lives somewhere unusual, either set `SG13G2_PDK_PATH` (or the
conventional `PDK_ROOT` + `PDK` pair) or write a git-ignored
`sim/pdk.local.json`.

## Reproducing one record

Every record ends with the exact command that regenerates it. It is always:

```bash
python3 sim/run_corners.py <experiment-slug> -j 8
```

A re-run mints a **new** record; it never overwrites one already committed.
`sim/` is an evidence trail, not a status page.

## Pinned toolchain

[`sim/toolchain.json`](toolchain.json) pins the toolchain and the harness
**checks it before simulating**, refusing to run on a mismatch (override with
`--allow-toolchain-drift`, which then stamps the drift into every record made
under it).

| pin | value | checked? |
|---|---|---|
| IHP-Open-PDK release | `0.3.0` | **exact** — the release IS the device models |
| ngspice | ≥ 46 (major), OSDI-capable | floor |
| Python | ≥ 3.9 | floor |
| xschem | recorded, not checked | nothing here invokes xschem until `design/` has a schematic |
| OpenVAF-Reloaded (OSDI compiler) | `v24.0.1mob`, checksum-pinned | checked by `sim/tools/build-osdi.sh` at build time, not by the corner runner |

PDK variant: **ihp-sg13g2**, set in [`sim/pdk.json`](pdk.json).

## Corner grid

SG13G2's `cornerMOSlv.lib` is already a self-contained global process switch
for LV MOS — no `gf180mcu`-style multi-family bundle is needed. Full
definitions and rationale, including the full divergence table from
`gf180-comparator`'s harness: [`sim/harness/README.md`](harness/README.md).

| axis | points |
|---|---|
| process | `tt`, `ff`, `ss`, `fs`, `sf` (the default `mos` set, mismatch off); the same five with mismatch on (`mos_mismatch`) for `comparator-offset-mc` |
| temperature | −40 °C, 27 °C, 125 °C |
| supply | 1.08 V, 1.20 V, 1.32 V (1.2 V ± 10 %) |

**45 points**, full factorial, per recorded run. Corner ids are
`<process>_<temp>c_<supply>v`, e.g. `ss_-40c_1.08v`, `tt_mismatch_27c_1.20v`.

There is no resistor-corner promotion yet: the placeholder DUT's load is an
ideal SPICE resistor, not a PDK resistor subckt — a tracked extension point
(`sim/harness/corners.py`'s module docstring), not a silent omission.

## Directory convention

```
sim/<experiment-slug>/
  README.md                       method, provenance, and what was NOT ported
  testbench/tb.json               manifest: analyses, measurements, checks
  testbench/<name>.spice          netlist FRAGMENT (harness owns models/OSDI/.temp/.control)
  records/<record-id>.md          the evidence record   <- append-only
  records/<record-id>.json        the same, machine-readable
  corners/<record-id>/<corner-id>.log   raw ngspice output, one per PVT point
  netlist-snapshots/<record-id>.spice   DUT + fragment exactly as simulated
```

`<record-id>` is `<UTC-YYYYmmdd-HHMMSS>-<short-sha>`.

## Record format

Every record states, in its header, everything needed to judge or reproduce
it:

- the **claim** it substantiates (or, today, that it substantiates the
  harness and not a spec row);
- the **DUT** — id, provenance (`placeholder` / `schematic` / `extracted`),
  path and sha256;
- the **testbench** fragment and manifest sha256s;
- the **commit**, flagged loudly if the working tree was dirty — a
  dirty-tree record is not citable;
- the **PDK** variant and release version, and the **toolchain** observed,
  plus any accepted drift;
- the **corner matrix** actually run and how many points completed;
- for a Monte-Carlo record, the **seed, draw count and σ derivation**
  (`CLAUDE.md` requires all three);
- the full per-corner result table, the grid spread, the per-axis corner
  sensitivity, the verdict, and the reproduction command.

Raw per-corner ngspice logs are committed alongside (`.gitignore` explicitly
un-ignores `sim/*/corners/**/*.log` for this reason), so a reader can check a
number against the tool's own output rather than against a table somebody
transcribed.

## Rules

- **No claim without a testbench.** A number that is not in a record under
  `sim/` is not a result.
- **PVT corners on every recorded result.** A single-corner run is a smoke
  test and writes no evidence.
- **`sim/` is append-only.** Add records; never edit or delete one.
- **A placeholder measurement is never a spec claim.** The provenance stamp
  is the mechanism, not the etiquette.
- **Do not relax a check to make a result pass.** A check that is wrong gets
  a documented recalibration citing the record it was calibrated from — the
  convention every `min_spread_pct_by_axis` floor here already follows.

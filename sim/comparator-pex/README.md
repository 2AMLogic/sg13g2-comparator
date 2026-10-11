# `sim/comparator-pex/` -- post-layout `klt pex` attempt (issue #61, T1 item 7)

**Historical first-attempt outcome (see "Update 2026-10-09 (later)" below for the current state: a single-corner extracted run now works). On that first attempt the schematic-vs-extracted spec re-run did NOT run: no spec row had an extracted-side value, so there was no delta to report,
and T1 item 7 stayed
`unmet`.** What exists is the extraction itself, a complete and reproducible
`klt pex` setup, and the exact reasons the simulation leg cannot run on the
available backends. Nothing here is a pass, and nothing was relaxed
(DR-0002 is untouched).

## Update 2026-10-09 (later): single-corner extracted run now works locally

The host's ngspice is now 46 (matches `sim/toolchain.json`), so the OSDI
v0.4 blocker in "Why nothing simulated" (item 1) no longer applies; the
text below it is kept as the record of the earlier attempt. The same
`klt pex` command, unchanged, now produces real `delta[]` rows
(`--backend local`, nominal requests only, 54 s):

- Envelope: `layout/comparator/pex_report.json` (this is the cited item-7
  artifact; the extracted netlist `comparator.pex.spice` is byte-identical,
  sha256 `9bd443be...980a`). Table: `reports/delta-nominal-20261009.{md,json}`
  (`make_delta_table.py`).
- Basis: **one corner, tt / 1.20 V / 27 C; deterministic transients; no MC,
  no seeds, no sigma.** Status `error`: 29 pass, 0 fail, 1 errored.
- Findings (single-corner observations, not statistics):
  - Decision delay is much slower extracted: `td_a` (50 mV overdrive) 0.710 ns
    -> 2.040 ns (+187 %), `td_b` (1 mV) 0.963 -> 2.682 ns (+178 %). Part of
    this is the layout's 64 fingers with drawn junction geometry versus the
    schematic's 24 devices with none, not only routing RC; the two are not
    separated here.
  - `td_c` (0.1 mV overdrive): schematic 1.106 ns; extracted has no value.
    The extracted `dc` output is already high at 18 ns (before the input
    flips to +0.1 mV), so it resolved to the opposite side at -0.1 mV and
    never makes the rising transition the measure waits for. This is
    consistent with an extracted systematic offset larger than 0.1 mV at
    this corner (in the extracted netlist `vinn` carries 0.197 fF, 6.0 %, more
    lumped ground C than `vinp`: `Cvinn` 3.4536 fF vs `Cvinp` 3.2566 fF,
    `layout/comparator/comparator.pex.spice` lines 630 and 640). That asymmetry
    is a candidate cause, not a measured one; one run cannot size the offset:
    offset sigma needs the MC bench, which was not run.
  - `dc_first` reads `pass` at +30126069 % in the delta table, but it is **not
    a meaningful delta** and must not be read as a pass. It is the same
    flipped-decision artifact as `td_c`. The row samples the decision node
    before the input flip (`.meas tran dc_first find v(dcn) at=18n`): the
    schematic sits at ~0 (3.32e-6) and the extracted netlist has already
    resolved high (0.99999). The percentage is a logic-level flip divided by
    a near-zero denominator. The `pass` status only means both legs produced
    a value; the request sets no limit on this row. It is the same
    observation as the `td_c` finding, not separate evidence.
  - Kickback is smaller but not eliminated: `ad_pos` -8.0 %, `ad_neg`
    -14.1 %, `apmax` -1.3 %; `bc1` -79.6 % (a tiny-magnitude current row).
  - Rows with no change beyond 0.1 %: supply, end-state, bias current
    (`i_stat` -0.08 %), common-mode levels.
- Renderer semantics (issue #181): `make_delta_table.py` keeps klt's raw status and
  `delta_pct` as measurement availability and adds a separate, explicitly mapped
  interpretation: logic rows (`d*_first`/`d*_end`) as states against the bench's own
  0.1/0.9 polarity checks (no percentage), `td_a`/`td_c` as absolute values against
  DR-0002 Row 3 (1.5 ns at 50 mV, 2.0 ns at 0.1 mV) on PVT-grid corners; every
  other key is ungraded. Tests: `tests/test_delta_table.py`. The 20261009 table
  above is historical and unchanged.
- Not run: the 45-point PVT grids and the offset / noise Monte Carlo rows.
  `klt sim --backend batch` was re-probed and refused:
  `batch_no_capacity` ("no capacity in any of the 30 pools after 3
  attempts"). No local grid was launched as fallback (host rule). The
  derived DR-0002 quantities (kickback mV, tau) were not recomputed against
  the spec limits; only schematic-vs-extracted raw deltas are recorded.
- DR-0002 is untouched; nothing was relaxed.

## Update 2026-10-10: batch re-probe

`klt sim --backend batch` on the staged PVT regeneration request was refused again
(`batch_no_capacity`, 30 pools). Record: `reports/batch-probe.regeneration.pvt.20261010.{md,json}`.
The PVT and Monte Carlo rows remain not run; no local grid was launched.

A second probe the same day (`reports/batch-probe.regeneration.pvt.20261010-b.{md,json}`) was refused identically (`batch_no_capacity`, 30 pools).

A third probe (`reports/batch-probe.pvt.20261010-c.md`) ran the full `klt pex` over both staged PVT requests on `--backend batch`, and this time capacity was granted. Result: all 1350 delta rows errored (`reports/pex.batch-probe.pvt.20261010-c.json`). A direct `klt sim` submit (`reports/batch-probe.regeneration.pvt.20261010-c.json`, job `klt-sim-f07e181de148`) shows the cause: `batch_runner_version_mismatch` (runner klt 0.5.0, client 0.7.0), the same as on 2026-10-09. The blocker is now the runner image, not capacity. The `model_mismatch` block in both pex envelopes is a count-only (finger) difference with identical model sets, not a flavour divergence (filed upstream as klayout-tools#3054).

## Update 2026-10-11: extracted-device-only diagnostic leg (issue #191)

A controlled attribution study, **not compliance evidence**; the original full
PEX above remains the item-7 artifact and DR-0002 is untouched. Three legs on
the same regeneration stimulus and wrapper (tt / 1.20 V / 27 C, deterministic,
no sigma): schematic, extracted-device-only, full PEX.

- `make_devonly.py [--check]` derives `dut/comparator.devonly.sp` from
  `layout/comparator/comparator.pex.spice` (sha256 `9bd443be...980a`): 64
  fingers kept with model/W/L/AS/AD/PS/PD verbatim; 252 terminal series R
  collapsed onto their parent nets; 16 ground C and 52 coupling C removed; the
  DC substrate tie kept. It refuses unknown elements/directives, non-terminal
  series R, duplicate or orphan terminal R, unresolved `__t` device nodes and
  C on terminal nodes (`tests/test_devonly.py`). Also generates
  `dut/tb_regeneration.devonly.sp` and `requests/regeneration.devonly.{nominal,pvt}.json`
  (checked in CI with the other generators).
- Report: `reports/devonly-attribution.20261011.{md,json}` (rendered by
  `make_devonly_report.py` from `reports/devonly-nominal-sim.20261011.json` and
  the `klt pex` re-run, which reproduced the 20261009 schematic/full values
  exactly). `td_a` 0.710 -> 1.536 -> 2.040 ns. The increments (+0.826 ns
  device representation/junction geometry, +0.504 ns routing RC) are
  conditional differences in a nonlinear circuit, not an additive
  decomposition; finger count and junction geometry are not separated from
  each other. `td_c` has a value on the device-only leg (2.230 ns) and none on
  full PEX.
- PVT: the 45-point device-only request went to `--backend batch` once
  (`reports/devonly-pvt-batch.20261011.json`, job `klt-sim-5e70ae964e3a`): all
  45 points errored, `batch_runner_version_mismatch` (runner klt 0.5.0). No
  local grid was launched.

## What ran, and what it proved

| Artifact | What it is |
|---|---|
| `layout/comparator/comparator.pex.spice` | The lumped-RC netlist `klt pex` extracted from `layout/comparator/comparator.gds` (`--deck sg13g2 --top comparator`, `--pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`, `--pdk ihp-sg13g2`). 64 devices, 18 nets, 8 pins. sha256 `9bd443be...980a`. |
| `reports/pex.attempt-20261009.json` | The verbatim `klt pex --format json` envelope (klt 0.7.0+g4cbdfa769875, KLayout 0.30.12, `--backend local`). `status: error`; 30 `delta[]` rows, all `error`, all values `null`; `coverage.nothing_checked: true`. Carries `extraction.model` and `body_bias` verbatim. |
| `reports/batch-probe.regeneration.nominal.json` | The `klt sim --backend batch` probe of the nominal regeneration request (see "Why nothing simulated"). |

Facts from the extraction (these are extraction results, **not** simulation
results; the layout is the one whose `content_hash` is pinned by items 3 and 4):

- `body_bias.status: "biased"`, 0 unbiased devices, `unbiased_pmos_body_nets: []`.
  The disclosure item 7 requires is therefore the clean one.
- `extraction.model` is the lumped model: one series R per net terminal and one
  ground C per net, vertical-overlap coupling only (no lateral coupling: no
  `--critical-net` was declared), quasi-static (no frequency dependence), no
  distributed RC. It does not model fringe shielding or same-layer coupling.
- Totals: 252 R (593.6 ohm summed), 16 ground C (177.0 fF), 52 coupling C
  (2.39 fF).
- Per-net lumped C (fF), from `klt extract --parasitics`: `vinp` 3.26,
  `vinn` 3.45, `ln` 17.27, `lp` 17.11, `tail` 7.64, `clk` 15.14,
  `dout` 6.54, `doutb` 6.71. The input pair sees 0.197 fF (6.0 %, relative
  to `vinp`) more ground capacitance on `vinn` than on `vinp` (`Cvinn vinn
  vsubs 3.453621e-15` vs `Cvinp vinp vsubs 3.256586e-15`,
  `layout/comparator/comparator.pex.spice` lines 630 and 640). That is an observation about the
  extracted netlist; what it costs in offset or kickback is exactly the
  measurement that did not run.
- Extraction warnings carried by the envelope: layer 63/0 (26 shapes) is outside
  the sg13g2 deck's connectivity graph (already disclosed for item 4 in
  `manifests/README.md`).
- Extracted devices are the layout's 64 fingers with drawn `AS/AD/PS/PD`
  junction geometry; the schematic leg has 24 devices with no junction
  geometry. Part of any extracted delta will be that, not routing parasitics.

## Why nothing simulated

Every spec row needs the PSP103 OSDI compact model. Both places a `klt sim`
leg can run fail on that, independently of this design:

1. **Local (this host).** `ngspice-42` supports OSDI v0.3 only; the PDK's
   `psp103.osdi` targets v0.4 (built for ngspice 46, `sim/toolchain.json` pins
   `ngspice_min_major: 46`). `pre_osdi` prints
   `NGSPICE only supports OSDI v0.3 but ".../psp103.osdi" targets v0.4!`
   and the deck never elaborates. `python3 sim/run_corners.py --check-env`
   shows the same `toolchain: DRIFT` (floor 46, installed 42). Host tools are
   not changed from a sweep, so this was not worked around. The schematic
   leg cannot run either, so the existing harness records cannot be
   reproduced on this host.
2. **Batch fleet.** `options.osdi_preload` is refused outright for
   `--backend batch`; with `options.stage_model_inputs: true` the job is
   accepted, runs on a Spot `m7i.4xlarge`, and fails in 5 s with
   `batch_runner_version_mismatch`: the fleet runner image is klt **0.5.0**,
   the client 0.7.0. klt 0.5.0 has no `osdi_preload` support at all, so the
   corner could not be elaborated even if the version gate were bypassed.
   No grid was launched locally as a fallback (host rule).

The multi-corner PVT requests (`requests/*.pvt.json`, 45 points) and the Monte
Carlo rows (offset sigma, input-referred noise) were therefore **not run and
not submitted**: a one-corner probe already fails on the runner, so a 45-point
submit would only repeat it 45 times. Offset sigma and noise additionally need
`monte_carlo` sample counts and seeds committed with the result
(`CLAUDE.md`); they have no extracted-side result of any kind here.

| DR-0002 spec row | Bench (whole latch, `comparator_dut`) | Extracted-side result |
|---|---|---|
| Decision time vs overdrive / metastability | `comparator-regeneration` | not run (request: `requests/regeneration.{nominal,pvt}.json`) |
| Kickback | `comparator-kickback` | not run (`requests/kickback.{nominal,pvt}.json`) |
| Offset sigma (whole latch) | `comparator-offset-transient-mc` | not run, not expressed as a request (needs MC, batch) |
| Input-referred noise (transient) | `comparator-transient-noise` | not run, not expressed as a request (needs MC, batch) |

`comparator-offset-mc` and `comparator-preamp-noise` are not in scope: they
instantiate `comparator_dut_analog`, the loop-broken sub-model, which has no
layout counterpart.

## How the setup works (so the run is a re-run, not a rewrite, once a backend exists)

`klt pex` swaps exactly one `.include` line for the extracted netlist and
reuses everything else byte-for-byte, and the layout covers only the core cell
`comparator`, not the `comparator_dut` wrapper (bias mirror `XMB`). So:

- `dut/comparator.schematic.sp` is the schematic leg: the `.subckt comparator`
  device cards from `design/comparator.spice`, verbatim, with the header pin
  order changed to the extractor's (`clk dout doutb vbias vdd vinn vinp vss`).
  Regenerate/verify with `make_reference.py [--check]`. **Pin order matters:**
  `klt pex` checks pin count only; the extractor writes pins alphabetically
  while the design's `comparator` declares them in signal order, and the
  testbench instantiates positionally (upstream
  [klayout-tools#2890](https://github.com/2AMLogic/klayout-tools/issues/2890)).
- `dut/tb_{regeneration,kickback}.sp` carry the stimulus lines of the committed
  benches verbatim, one `.include`, and the `comparator_dut` wrapper defined
  inline (`XMB` is identical on both legs and is not in the layout, which is a
  scope limit of the extracted leg). The wrapper is derived from the
  `.subckt comparator_dut` block of `design/comparator.spice`: header and the
  `XMB` bias-mirror card verbatim, the core instance re-pinned to the
  extractor's order (`x1 clk dout doutb ibias vdd vinn vinp vss comparator`).
  `make_testbenches.py [--check]`.
- `requests/*.json` are `klt sim` requests built from the benches' `tb.json`
  by `make_requests.py`: the `.meas` cards are the benches' `meas tran` lines
  verbatim; derived quantities (`tau_ps`, `kick_*_mv`, ...) are not requests
  and would be recomputed from the reported raw values in the delta table.
  `*.nominal.json` is one corner (mos_tt, 27 C, 1.20 V); `*.pvt.json` is the
  45-point grid (5 process x 3 supply x 3 temperature).
  `make_requests.py [--check]`.

### Freshness check (CI) and intentional regeneration

The committed `dut/*.sp` and `requests/*.json` are generated adapter inputs,
not evidence: they must always equal what the three generators derive from the
current `design/comparator.spice` (core and `comparator_dut` wrapper),
`sim/dut.json` (`dut_ib`, `dut_vcm`) and the source benches'
`sim/comparator-{regeneration,kickback}/testbench/` (stimulus fragment,
`.options`, `tran` analysis, `meas tran` cards). CI checks this in the
`harness-unit-tests` job (issue #123). Locally, from the repository root
(stdlib Python only; no PDK, ngspice, klt or batch submission):

```bash
python3 sim/comparator-pex/make_reference.py --check
python3 sim/comparator-pex/make_testbenches.py --check
python3 sim/comparator-pex/make_requests.py --check     # nominal and PVT
python3 -m unittest discover -s sim/comparator-pex/tests -p 'test_*.py'
```

`--check` never writes. On drift it exits non-zero and names each `missing:`
or `stale:` path. After an intentional source change, regenerate and commit
the result in the same change:

```bash
python3 sim/comparator-pex/make_reference.py
python3 sim/comparator-pex/make_testbenches.py
python3 sim/comparator-pex/make_requests.py
```

The check covers only these current generated inputs. `reports/`,
`layout/comparator/pex_report.json` and any campaign or result envelope are
append-only evidence and are never regenerated or compared by it.

Reproduce the committed envelope (changes nothing outside `/tmp`):

```bash
export PDK_ROOT=$HOME/share/pdk          # parent of ihp-sg13g2/
klt pex layout/comparator/comparator.gds \
  sim/comparator-pex/requests/regeneration.nominal.json \
  sim/comparator-pex/requests/kickback.nominal.json \
  --deck sg13g2 --top comparator --pdk ihp-sg13g2 --pdk-root "$PDK_ROOT" \
  --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss --backend local \
  --outdir /tmp/pex -o /tmp/comparator.pex.spice --format json
```

On a host whose ngspice loads OSDI v0.4 the same command yields real
`delta[]` rows. On this host it reproduces the `error` envelope above.

## Upstream (`2AMLogic/klayout-tools`) friction

Already filed, and hit here: #2570 (no ihp-sg13g2 batch AMI), #2851 and #2948
(runner/client version skew), #2901 (older runner silently drops newer request
options), #2872 (`klt pex` drops `klt sim`'s per-corner diagnostics, so the
envelope cannot say why every row errored), #2890 (pin order). New, filed with
this change: **#2956** (a local ngspice that cannot load the OSDI library is
reported as "measurement produced no value", with no preflight or diagnostic
code).

## What closes the gap

Any one of: a worker with ngspice >= 46 (matching `sim/toolchain.json`) run as
a single-corner local `klt pex`; a fleet runner image with klt >= 0.7 and
`ihp-sg13g2` OSDI support (then the `*.pvt.json` requests plus an MC
`monte_carlo` request go to batch). Then cite the resulting envelope as item 7
in `manifests/sg13g2-comparator.json` and re-render
`manifests/t1-signoff-report.json`. The committed report is `status: error`
and must not be cited.

# `sim/comparator-pex/` -- post-layout `klt pex` attempt (issue #61, T1 item 7)

**Outcome: the schematic-vs-extracted spec re-run did NOT run. No spec row has
an extracted-side value, so there is no delta to report, and T1 item 7 stays
`unmet`.** What exists is the extraction itself, a complete and reproducible
`klt pex` setup, and the exact reasons the simulation leg cannot run on the
available backends. Nothing here is a pass, and nothing was relaxed
(DR-0002 is untouched).

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
  `dout` 6.54, `doutb` 6.71. The input pair sees 0.19 fF (5.6 %) more
  ground capacitance on `vinn` than on `vinp`. That is an observation about the
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
  scope limit of the extracted leg). `make_testbenches.py [--check]`.
- `requests/*.json` are `klt sim` requests built from the benches' `tb.json`
  by `make_requests.py`: the `.meas` cards are the benches' `meas tran` lines
  verbatim; derived quantities (`tau_ps`, `kick_*_mv`, ...) are not requests
  and would be recomputed from the reported raw values in the delta table.
  `*.nominal.json` is one corner (mos_tt, 27 C, 1.20 V); `*.pvt.json` is the
  45-point grid (5 process x 3 supply x 3 temperature).

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

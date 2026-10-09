# T1 signoff manifest — the machine-graded verdict of record

`manifests/sg13g2-comparator.json` is this block's **`klt signoff --manifest`
block manifest** (issue [#37]), and `manifests/t1-signoff-report.json` is
what `klt signoff` renders from it — frozen verbatim at the pinned `klt`
build and re-graded on every CI run. **As of this directory landing, these
two files are the verdict of record for this block's gap to T1
(design-evidence tiers), replacing the hand-maintained checkbox list in
tracking issue [#3].** Nothing else in this repo should be treated as the
finder's-answer to "what is this block's T1 state" — the per-experiment
narratives under `sim/`, `design/README.md`, and `spec/` remain the
*engineering* accounts; the manifest and its rendered report are the
*graded* ones.

The fleet-side counterpart is the `--fleet` roll-up
([2AMLogic/2am#956](https://github.com/2AMLogic/2am/issues/956)); a fleet
manifest that lists this block points at
`manifests/sg13g2-comparator.json` from this repo's root (`klt signoff`'s
file-backed evidence paths resolve against the invoking process's working
directory — run from this repo's root, not this subdirectory).

## Why this exists

Every prior "gap to T1" read in this repo (and the fleet) was hand-written
prose against whatever the checklist said that day. The checklist grew an
eleventh item on 2026-09-17
([klayout-tools#2025](https://github.com/2AMLogic/klayout-tools/issues/2025)
— **Power delivery (structural)**), invalidating every prior hand-read the
moment it merged; this repo's tracker issue [#3] still describes a
ten-item list. This manifest is the fix: an unmet item renders `unmet` with
a stated `reason`, a cited item renders `met` only when its evidence is a
*passing* `klt` envelope whose input content-hash matches the pin in the
manifest — and when the checklist moves again, re-rendering moves with it
mechanically.

**An all-`unmet` manifest is a correct result.** Per the tiers doc and
`klt signoff`'s own contract, an unmet row is the honest, machine-readable
statement of a gap — issue [#37] commits this manifest precisely so the
gap is graded, not hand-read. Which rows are deliberately uncited, and
why, is the rest of this document.

## The manifest

| Field | Value | Basis in this block |
|---|---|---|
| `block` | `sg13g2-comparator` | **Required** — identifies this block's row in the fleet roll-up (2AMLogic/2am#956), which consumes exactly this file |
| `kind` | `analog` | confirmed against the block itself, not taken from the filing: the DUT is a single-tail StrongARM dynamic latch (`design/comparator.spice`, DR-0001) on `sg13_lv_nmos`/`sg13_lv_pmos` — a continuous-time-analog comparator with no digital partition, no RTL, no standard cells, and no mixed-signal boundary to declare. The spec rows are offset-σ, input-referred noise, metastability/decision time, and kickback — all analog measurements (`README.md`'s target-spec table). Analog satisfies the Analog column only, which is the column every row below is graded against. |
| `evidence` | items `3`, `4`, `5` and `11` | item 3 cites the `klt drc` envelope, item 4 the `klt lvs` envelope, item 5 a `klt sim` corner-matrix envelope whose own verdict is a Target **fail** (below), item 11 the compound of a `klt erc` supply-spec envelope and that same LVS envelope; every other item is deliberately uncited — see "What is deliberately uncited, and why" |

## What is deliberately uncited, and why

The `klt` JSON envelopes cited here are the item 3 DRC report, the item 4 LVS report (also
part of item 11), the item 11 `klt erc` supply report and one
item 5 `klt sim` corner envelope (`sim/klt-corner-verification/`, issue #62); no
`klt yield`/passing `pex` run has been minted. There is therefore nothing else the grader *accepts* to
cite, and per [#37]'s own rule — "do not
cite an envelope that does not actually support the item" — nothing is
borrowed to make a row go green. Every other row renders `unmet`/`no_evidence`,
which is the grader's honest statement that no check backs the claim, per
row:

- **Item 1 (Design sources), 2 (Layout), 9 (Testbenches shipped), 10 (Repo
  hygiene)** — these four have no `klt` verb behind them: the grader accepts
  *any* passing envelope regardless of topical relevance, so citing any
  envelope there would be exactly the borrowed pass the tiers doc warns
  about. The concrete artifacts themselves exist in the repo — the
  committed schematic + regenerating netlist (`design/`, item 1's actual
  artifact), five experiment directories with cold-start invocations
  (`sim/README.md`, item 9's), README/spec/license (item 10's) — but
  verifying them is the grader-visible *gap*, honestly `unmet`, not a
  defect claim. (For item 2, Layout: since issue #58 the generated stream
  `layout/comparator/comparator.gds` and the generator that reproduces it
  are committed — see `layout/README.md`. The row stays uncited until the
  pinned `klt` includes klayout-tools#2718's artifact-anchored generic
  evidence; that pin bump is tracked in #65.)
- **Item 4 (LVS clean)** — cited since #60; see "Item 4" below.
- **Item 5 (Full corner verification vs a ratified spec)** — cited since
  #62, and still `unmet`, because two ratified Targets fail on the evidence.
  See "Item 5" below.
- **Item 6 (Statistical claims carry Monte Carlo evidence)** — the
  machine-checkable evidence is a `klt yield` JSON report; this repo's
  Monte-Carlo offset evidence (`sim/comparator-offset-mc/`,
  `sim/comparator-offset-transient-mc/`, seeds and run counts committed) is
  real but in the repo's own record format, not `klt yield` output. When a
  `klt yield` campaign is minted it gets cited here with a pinned
  `content_hash`.
- **Item 7 (Post-layout verification)** — an analog block's item 7 accepts
  a `klt pex` report and nothing else. It is **cited** (since #61) at
  `layout/comparator/pex_report.json`, `content_hash` pinned to the layout
  revision, and it renders `unmet` / `check_failed`, deliberately: the
  envelope is `status: error` (29 of 30 `delta[]` rows pass, 0 fail, 1
  errored, `nothing_checked: false`). The one errored row is
  `regeneration.nominal.td_c`, the 0.1 mV-overdrive decision delay: on the
  extracted netlist that case never produces the post-flip rise the
  `.meas` waits for (its output is already high before the flip, i.e. it
  decided the other way at -0.1 mV), so the measurement has no value. That
  is a recorded post-layout finding, not a tooling failure, and the request
  was not edited to hide it. The run is **one corner only** (tt, 1.20 V,
  27 C, deterministic transient, no Monte Carlo, no sigma): the 45-point PVT
  grids and the offset-sigma / noise Monte Carlo rows were not run because
  the batch fleet refused the submit (`batch_no_capacity`, no capacity in
  any of 30 pools) and host rules forbid a local grid. Extraction half:
  `body_bias.status: "biased"` (0 unbiased devices); `extraction.model` is
  the quasi-static lumped-RC model (single series R per net, net-to-ground
  C plus vertical-overlap coupling; no lateral coupling without
  `--critical-net`, no fringe shielding, no distributed RC) quoted in full
  in the envelope. Per-row deltas: `sim/comparator-pex/reports/delta-nominal-20261009.{md,json}`;
  discussion and what closes the gap: `sim/comparator-pex/README.md`. The
  earlier errored attempt (`pex.attempt-20261009.json`) is kept as history.
- **Item 8 (Characterization report)** — the one item the generic envelope
  (`"kind": "generic"`) may satisfy. No aggregated, current
  characterization artifact exists yet (the tracker's item 8 is honestly
  "not started: no one-command characterization script exists"); a generic
  envelope without a real report behind it would be a hand-rolled "yep,
  it's fine" standing in for evidence item 8 never proved, so the row is
  left `unmet`.
- **Item 11 (Power delivery (structural))** — cited since #38; see "Item 11" below.

## Item 11 (Power delivery, structural) — cited, `met`, with the evidence's limits

Item 11 is a compound citation (issue [#38]): a list of two evidence files,
both file-backed and pinned by `content_hash`.

| Part | File | Pinned `content_hash` | Tool-defined value |
|---|---|---|---|
| `klt erc` | `layout/comparator/erc_report.json` | `sha256:67e44380bac6f5b2eb52ac80cfc0422856e06a8b12cd7526b36717531655ea41` | `provenance.input.content_hash`: the GDS (the same value item 3 pins) |
| `klt lvs` | `layout/comparator/lvs_report.json` | `sha256:6970e7e51951f876f68536d37d37adf16e5ff121862c9ee60a8be94ff6a3bf0b` | `provenance.input.content_hash`: the extracted netlist (item 4's value; the envelope was **not** re-minted, none of its inputs changed) |

**Declared supply set, reconciled against the schematic.** The ERC request
(`layout/comparator/erc_supply_spec.json`, derived from the generator's layer
table by `layout/comparator/erc_tool.py`) declares exactly `vdd` and `vss` as
`kind: supply`. The ratified netlist's top is
`.subckt comparator vinp vinn clk vbias dout doutb vdd vss`
(`design/comparator.spice`); `vdd` and `vss` are its only supply ports (1.2 V
LV core rail), and the grader reads `supply_nets: ["vdd", "vss"]` from the
request. The grader cannot detect an undeclared supply, so this sentence is
the claimant's enforcement of set completeness.

**`vbias` is not a supply.** It is an independent bias input port: its own
Metal3 pin, its own `VBIAS`-`VBIAS` entry in the LVS `net_correspondence`,
and no geometry connecting it to vdd in this top. The older description of
`vbias` as "tied to vdd" applies to the `comparator_dut_latch` test wrapper
only, not to the drawn cell. The request declares it as a `kind: signal` net,
so the run additionally proves it is one island and is not shorted to a
supply; it is not counted among the supplies.

**ERC half.** `klt erc --deck sg13g2 --top comparator --findings-only`
reads `erc_status: clean`, 0 findings. `erc_coverage.checked` holds
`erc.net_connectivity` for `vdd`, `vss` and `vbias`, `erc.missing_tie` for the
`nwell_vdd` tie and `erc.floating_gate` for the 10 gate nets;
`erc_coverage.skipped` is empty, so the tie is not a
`degenerate_tap_declaration`. The tie is narrowed to Activ & nSD & Cont (the
contacts of the n-tap bars; only those carry nSD) inside NWell. The envelope's
own `status` is `not_checked` (antenna accumulation skipped by
`--findings-only`; no antenna table exists for this deck). Item 11 does not
grade it, and no antenna claim is made.

**LVS half.** `lvs_report.json` is a `status: match` with `VDD`->`VDD` and
`VSS`->`VSS` in `net_correspondence` (the reference is the SPICE subcircuit,
which carries the supply pins). As for item 4, `power_connectivity` and
`body_verification` are `unchecked`: they are not a geometric power-grid or
body verification.

**What this does not establish.**
- No p-tap (substrate) tie is in the cited request: `klt erc` has no
  substrate layer. `layout/run_flow.sh` checks the p-tap bars in a temp
  fixture with a scratch layer, which is a flow check, not cited evidence.
- Diffusion/well continuity is not modelled (klayout-tools#2180); supply
  continuity is through contacts, Metal1-3 and vias. No finding of that kind
  occurred, so no waiver was needed. No `devices[]` carve-out is declared (no
  rail-spanning device body exists; `provenance.devices` is empty).
- Not IR-drop or EM (`klt power`), not DRC coverage (item 3), not item 4's
  signal verdict.
- Stage 7 of `layout/run_flow.sh` (CI runs it with `--check`) re-derives the
  request, requires the committed envelope to equal a fresh run, and runs five
  temp-fixture negative controls (a severed vdd track gives
  `erc.unconnected_net`; a vdd-vss strap `erc.supply_short`; no nSD
  `erc.missing_tie`; an un-narrowed tap declaration the skipped
  `degenerate_tap_declaration`; a p-tap fixture without pSD
  `erc.missing_tie`), so the clean verdict is known to be falsifiable.

## Item 3 (DRC clean) — cited, with the deck's coverage gaps

Item 3 cites `layout/comparator/drc_report.json`, the `klt drc --deck sg13g2
--top comparator` envelope for `layout/comparator/comparator.gds` (issue
#59), pinned by `content_hash`
`sha256:67e44380bac6f5b2eb52ac80cfc0422856e06a8b12cd7526b36717531655ea41`
(the GDS's own hash, recorded as `provenance.input.content_hash`). It reads
`status: clean`, `violation_count: 0`, `rules_checked` 21, against deck
`sha256:894326a4e37fb24fef2f7ffc6ae1da55a0e262b0f0bc1c09adc4862909278fda`
(klt `0.5.0+ge8ca621a6961`, KLayout 0.30.10). `layout/run_flow.sh` stage 6
regenerates it; `--check` requires it fresh (`klt drc --check`). `klt signoff`
grades item 3 on `status: clean` alone and does not enforce disclosure, so the
three `coverage` fields of the envelope are quoted verbatim here. This is
klt's *curated* deck, **not** the foundry's own DRC deck: "clean" means clean
inside this scope only.

`coverage.layers_in_stream_without_rules` (drawn in the stream, no rule in the
deck: nSD, pSD, NWell, Metal3 pin, Metal3 text, and the text layer):

```
7/0, 14/0, 30/2, 30/25, 31/0, 63/0
```

`coverage.rules_skipped` (22; every one has reason `no_applicable_geometry`
in `coverage.inapplicable`: this layout draws no Metal4/5, TopMetal or
Via3/4/TopVia, and the deck's Metal3 enclosure of Via3 has no Via3 to act on):

```
metal3.enclosing.via3.1, metal4.enclosing.via4.1, metal4.space.1,
metal4.width.1, metal5.enclosing.topvia1.1, metal5.space.1, metal5.width.1,
topmetal1.enclosing.topvia1.1, topmetal1.enclosing.topvia2.1,
topmetal1.space.1, topmetal1.width.1, topmetal2.enclosing.topvia2.1,
topmetal2.space.1, topmetal2.width.1, topvia1.space.1, topvia1.width.1,
topvia2.space.1, topvia2.width.1, via3.space.1, via3.width.1, via4.space.1,
via4.width.1
```

`coverage.deck_scope` (chapters of the foundry DRM the deck transcribes):

```
Act, Cnt, Gat, M1, M2, M3, M4, M5, TM1, TM2, TV1, TV2, V1, V2, V3, V4
```

Consequences stated plainly: NWell and nSD/pSD geometry, Gat.c endcap,
Cnt.e/Cnt.f, latch-up tap distance, density and seal ring are **not checked**
by this evidence (see `layout/README.md`, "What this layout is, and is not").
Also, `layout/comparator/drc_report.json` records its input as the
repo-relative `layout/comparator/comparator.gds` (run from the repo root); the
pinned build does not embed a host-absolute path
([klayout-tools#2659](https://github.com/2AMLogic/klayout-tools/issues/2659)
did not bite here).

## Item 4 (LVS clean) — cited, with the verdict's limits

Item 4 cites `layout/comparator/lvs_report.json`, the `klt lvs` envelope
(issue #60) comparing `layout/comparator/comparator.gds` (extracted with
`klt extract --deck sg13g2`) against the `.subckt comparator` block of
`design/comparator.spice`, pinned by `content_hash`
`sha256:6970e7e51951f876f68536d37d37adf16e5ff121862c9ee60a8be94ff6a3bf0b`.
That is the tool-defined value, `provenance.input.content_hash`, and it is
the hash of the **extracted netlist** (`layout/comparator/lvs_extracted.spice`),
not of the GDS or the schematic. The tool does not bind it to either, so
`layout/run_flow.sh --check` (run in CI) re-derives both links and fails on a
changed GDS, schematic subcircuit or request; see `layout/README.md`, stage 4.

The envelope reads `status: match` (engine `klayout` 0.30.10, klt
`0.5.0+ge8ca621a6961`), 24/24 devices, 18/18 nets, 8/8 pins including
`vdd`/`vss` and the independent `vbias`, 0 mismatches, 0 warnings.
`power_connectivity.status` is `unchecked`, which `klt signoff` accepts: with
`reference.form: subckt-call` the supply pins take part in the ordinary
compare, so the signal-only power check does not apply. That is **not** a
geometric power-grid verification. `body_verification` is also `unchecked`.
Supply ERC is item 11 (#38, below); post-layout simulation (#61) is separate work. The reference is
cut out of the schematic netlist as a workaround for
[klayout-tools#2852](https://github.com/2AMLogic/klayout-tools/issues/2852).

## Item 5 (Full corner verification) — cited, and `unmet` on a real Target failure

The spec table is ratified
([DR-0002](../spec/decision-records/0002-target-spec-ratification.md),
merged via PR #18). Since #62, every DR-0002 row and sub-bound has been
re-measured on the schematic DUT as `klt sim` corner-matrix envelopes over
the full 45-point PVT grid, run on the batch fleet with this pinned klt.
They are in
[`sim/klt-corner-verification/`](../sim/klt-corner-verification/README.md),
campaign `20261009-d73a9ac`, graded literally by `sim/kltsim/grade.py`
(`grading.md` there). The per-row verdicts, binding points and conditions
are in that README. **Two Targets fail:**

- **Row 2, input-referred noise**: the grid-wide mean of the per-point
  probit-slope σ is **1.289 mV rms**, against a ≤ 1.0 mV Target and a
  ≤ 0.6 mV Stretch. The DR-0002 record had 1.335 mV, NOT MET.
- **Row 4a, peak injected charge Q_kick per side**: measured directly for the
  first time, **23.6 … 31.5 fC**, with **39/45 points over the 25 fC Target**
  (binding `ff_125c_1.32v`). DR-0002 left this clause "CONSISTENT, NOT
  CERTIFIED". The instrument is timestep-converged and
  passes #78's known-charge fixture (unipolar, negative, bipolar and
  restoring-resistor injections read back to 0.002 fC; campaign
  `20261009-issue78`), so the FAIL stands on a validated instrument.

Rows 1, 3a, 3b, 3c and 4b meet their Targets at 45/45 points, and the supply
and temperature grid (5a) is fully exercised. Row 5's power has no Target
(DR-0002 ratifies none), and its Stretch fails.

**What is cited, and why that envelope.** The pinned `klt signoff` grades
item 5 on **one** `sim` envelope and calls it passed only when that
envelope's own `status` is `pass`. The campaign's requests encode only
DR-0002 Target bounds and validity gates as `limits`, so an envelope's own
status is the Target verdict of the rows it carries. The manifest cites
`sim/klt-corner-verification/campaigns/20261009-d73a9ac/kickback.envelope.json`,
pinned by `content_hash`
`sha256:5329b96594ca66668a235d8c3418b958b511fc4a17f3cf652a3bd84cc51c8af7`
(its `provenance.input.content_hash`: the committed netlist body, which
inlines `design/comparator.spice` byte for byte). That envelope's own status
is `fail`: 6 pass / 39 fail / 0 error, the Row 4a Target. The grader
re-hashes the body and renders item 5 **`unmet` / `check_failed`**
(`critical_metric_blockers: sim__corner__failed_count = 39`). This is the
truthful one-envelope summary.

**What must not be cited**, so a later change does not quietly flip the
verdict:

- `regeneration.envelope.json` has status `pass`, but citing it would render
  item 5 `met` on Rows 3 and 5 alone.
- The offset and noise envelopes have status `pass`, but their status
  reflects only per-sample gates. Rows 1 and 2 are caller-side population
  statistics that klt sim cannot grade
  ([klayout-tools#2960](https://github.com/2AMLogic/klayout-tools/issues/2960)).

Item 5 can honestly read `met` only when every bounded Target in `grading.md`
passes, and the citation is then whichever envelope the tool accepts as
covering them.

## Regeneration and freshness

The report is frozen at the pinned `klt` build — `2AMLogic/klayout-tools` @
`e8ca621a6961879cec1af60cc932c3b3d58ddcaa` (the same pin the fleet's other
committed manifest, `gf180-usb2-phy`, freezes against). A released `klt`
older than 2026-09-17 does **not** know item 11 and renders a ten-item
report; the pinned build renders all eleven. If the pinned build moves,
the manifest, the freeze, and the pin move in one change.

```bash
klt signoff --manifest manifests/sg13g2-comparator.json --format json > /tmp/fresh.json
klt signoff --manifest manifests/sg13g2-comparator.json --format text
diff /tmp/fresh.json manifests/t1-signoff-report.json   # regeneration = update the frozen report in the same change
```

Exit `0` means every T1 item met (this repo is **not** there: exit `3`,
`tier: null`, `3/11` item rows met at the time of freezing: items 3, 4 and 11; item 7 is cited but renders `unmet`). Exit codes
`0` and `3` are both clean runs; exit `1` is an error and must be fixed,
not committed around.

**The freshness contract is the pin, and CI re-checks it**
(`scripts/check_signoff_report.py`, wired into
`.github/workflows/ci.yml`):

1. Every future citation pins a `content_hash` matching the committed
   artifact's own recorded input revision (`provenance.input.content_hash`,
   spelled in `klt`'s JSON-contract). A citation without a
   pinned hash cannot have its freshness verified at all, and a manifest
   update that cites an unpinnable, unprovenanced envelope renders
   `unverifiable_provenance` — never a quiet pass. If a cited artifact's
   input changes without re-minting the envelope *and* updating the
   manifest, the grader renders that item `unmet`/`stale_evidence`.
2. The committed `t1-signoff-report.json` must equal a fresh render,
   byte-semantics compared, on every CI run. A manifest citing an artifact
   that has since changed *fails CI* rather than rotting — and so does a
   report frozen against a different `klt` build or a moved checklist:
   regeneration and the manifest move in the same change, visibly.

## Files

| File | What it is |
|---|---|
| `sg13g2-comparator.json` | the block manifest — `block`, `kind`, per-item pinned evidence citations (items 3, 4, 5 and 11 cited; the rest deliberately uncited — see above). **The stable path a fleet roll-up points at.** |
| `../sim/klt-corner-verification/campaigns/20261009-d73a9ac/kickback.envelope.json` | the cited item 5 evidence (`klt sim` envelope, status `fail`); the rest of that campaign, its grading and its reproduction are in `../sim/klt-corner-verification/README.md` |
| `../layout/comparator/drc_report.json` | the cited item 3 evidence (`klt drc` envelope), regenerated by `layout/run_flow.sh` |
| `../layout/comparator/lvs_report.json` | the cited item 4 evidence (`klt lvs` envelope), with its derived inputs `lvs_extracted.spice`, `lvs_reference.spice`, `lvs_request.json`, regenerated by `layout/run_flow.sh` |
| `../layout/comparator/erc_report.json`, `../layout/comparator/erc_supply_spec.json` | the cited item 11 `klt erc` evidence and its derived request, regenerated by `layout/run_flow.sh` (item 11 also cites `lvs_report.json`) |
| `t1-signoff-report.json` | `klt signoff --manifest sg13g2-comparator.json --format json` output, frozen at the pinned `klt`; CI diff-checks a fresh render against it |
| `README.md` | this claim document — kind basis, citation rationale and the disclosure of the uncited rows, the regeneration contract |

[#37]: https://github.com/2AMLogic/sg13g2-comparator/issues/37
[#3]: https://github.com/2AMLogic/sg13g2-comparator/issues/3
[#38]: https://github.com/2AMLogic/sg13g2-comparator/issues/38

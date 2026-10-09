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
| `evidence` | items `3`, `4` and `5` | item 3 cites the `klt drc` envelope, item 4 the `klt lvs` envelope, item 5 a `klt sim` corner-matrix envelope whose own verdict is a Target **fail** (below); every other item is deliberately uncited — see "What is deliberately uncited, and why" |

## What is deliberately uncited, and why

The `klt` JSON envelopes cited here are the item 3 DRC report, the item 4 LVS report and one
item 5 `klt sim` corner envelope (`sim/klt-corner-verification/`, issue #62); no
`klt yield`/passing `pex`/`erc` run has been minted. There is therefore nothing else the grader *accepts* to
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
  a `klt pex` report and nothing else. A `klt pex` run was attempted for
  #61 and is committed at `sim/comparator-pex/reports/pex.attempt-20261009.json`,
  but it is `status: error` (all 30 `delta[]` rows errored, `nothing_checked:
  true`): neither this host (ngspice-42 cannot load the OSDI v0.4 PSP103
  models) nor the batch fleet (runner klt 0.5.0 vs client 0.7.0, no OSDI
  preload) could run the simulation leg. An errored envelope is not
  evidence, so it is **not cited** and the row stays `unmet`. The
  extraction half is real: `body_bias.status: "biased"` (0 unbiased devices),
  `extraction.model` is the quasi-static lumped-RC model (vertical-overlap
  coupling only, no lateral coupling or distributed RC). Details, the
  not-run rows and what closes the gap: `sim/comparator-pex/README.md`.
  When a passing envelope exists it gets cited here with a pinned
  `content_hash`, with `extraction.model` and the `body_bias` disclosure
  quoted verbatim.
- **Item 8 (Characterization report)** — the one item the generic envelope
  (`"kind": "generic"`) may satisfy. No aggregated, current
  characterization artifact exists yet (the tracker's item 8 is honestly
  "not started: no one-command characterization script exists"); a generic
  envelope without a real report behind it would be a hand-rolled "yep,
  it's fine" standing in for evidence item 8 never proved, so the row is
  left `unmet`.
- **Item 11 (Power delivery (structural))** — no `klt erc` supply run and no
  supply-carrying LVS compare exist yet. The row exists (that is
  this manifest's guarantee: the day the checklist has an item, this block
  has a graded row for it) and its closing work is tracked in companion
  issue [#38].

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
ERC (#38) and post-layout simulation (#61) are separate work. The reference is
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
`tier: null`, `2/11` item rows met at the time of freezing: items 3 and 4). Exit codes
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
| `sg13g2-comparator.json` | the block manifest — `block`, `kind`, per-item pinned evidence citations (items 3, 4 and 5 cited; the rest deliberately uncited — see above). **The stable path a fleet roll-up points at.** |
| `../sim/klt-corner-verification/campaigns/20261009-d73a9ac/kickback.envelope.json` | the cited item 5 evidence (`klt sim` envelope, status `fail`); the rest of that campaign, its grading and its reproduction are in `../sim/klt-corner-verification/README.md` |
| `../layout/comparator/drc_report.json` | the cited item 3 evidence (`klt drc` envelope), regenerated by `layout/run_flow.sh` |
| `../layout/comparator/lvs_report.json` | the cited item 4 evidence (`klt lvs` envelope), with its derived inputs `lvs_extracted.spice`, `lvs_reference.spice`, `lvs_request.json`, regenerated by `layout/run_flow.sh` |
| `t1-signoff-report.json` | `klt signoff --manifest sg13g2-comparator.json --format json` output, frozen at the pinned `klt`; CI diff-checks a fresh render against it |
| `README.md` | this claim document — kind basis, citation rationale and the disclosure of the uncited rows, the regeneration contract |

[#37]: https://github.com/2AMLogic/sg13g2-comparator/issues/37
[#3]: https://github.com/2AMLogic/sg13g2-comparator/issues/3
[#38]: https://github.com/2AMLogic/sg13g2-comparator/issues/38

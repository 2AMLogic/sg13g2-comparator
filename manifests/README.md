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
| `evidence` | `{}` | every item is deliberately uncited — see "What is deliberately uncited, and why" below |

## What is deliberately uncited, and why

This repo has **no `klt` JSON envelope of any kind committed** — no
`klt drc`/`lvs`/`sim`/`yield`/`pex`/`erc` run has ever been minted here
(verified at freeze time: no `*.json` under `sim/`, `design/`, or
`layout/` carries a `klt` envelope's `schema_version`). There is therefore
nothing the grader *accepts* to cite, and per [#37]'s own rule — "do not
cite an envelope that does not actually support the item" — nothing is
borrowed to make a row go green. Every row renders `unmet`/`no_evidence`,
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
  defect claim. (For item 2, Layout, no `layout/` exists at all.)
- **Item 3 (DRC clean) and 4 (LVS clean)** — no layout exists, so no DRC or
  LVS run has ever had an input; both render `unmet`/`no_evidence` (blocked
  on gap-to-T1 item 2, layout).
- **Item 5 (Full corner verification vs a ratified spec)** — two gaps,
  each alone sufficient: `README.md`'s target-spec table is **DRAFT** (no
  ratification decision record yet — #12), and verdicts against a draft
  spec are provisional by construction; and the PVT evidence that does
  exist (`sim/`, 45-corner matrix, per-row records) is in this repo's own
  append-only record format, which no `klt sim` envelope represents.
- **Item 6 (Statistical claims carry Monte Carlo evidence)** — the
  machine-checkable evidence is a `klt yield` JSON report; this repo's
  Monte-Carlo offset evidence (`sim/comparator-offset-mc/`,
  `sim/comparator-offset-transient-mc/`, seeds and run counts committed) is
  real but in the repo's own record format, not `klt yield` output. When a
  `klt yield` campaign is minted it gets cited here with a pinned
  `content_hash`.
- **Item 7 (Post-layout verification)** — an analog block's item 7 accepts
  a `klt pex` report and nothing else; no layout means no extraction. The
  item's `body_bias` disclosure duty applies when a `pex` citation first
  appears here, not now.
- **Item 8 (Characterization report)** — the one item the generic envelope
  (`"kind": "generic"`) may satisfy. No aggregated, current
  characterization artifact exists yet (the tracker's item 8 is honestly
  "not started: no one-command characterization script exists"); a generic
  envelope without a real report behind it would be a hand-rolled "yep,
  it's fine" standing in for evidence item 8 never proved, so the row is
  left `unmet`.
- **Item 11 (Power delivery (structural))** — no layout means no `klt erc`
  supply run and no supply-carrying LVS compare. The row exists (that is
  this manifest's guarantee: the day the checklist has an item, this block
  has a graded row for it) and its closing work is tracked in companion
  issue [#38].

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
`tier: null`, `0/11` item rows met at the time of freezing). Exit codes
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
| `sg13g2-comparator.json` | the block manifest — `block`, `kind`, per-item pinned evidence citations (none yet, deliberately — see above). **The stable path a fleet roll-up points at.** |
| `t1-signoff-report.json` | `klt signoff --manifest sg13g2-comparator.json --format json` output, frozen at the pinned `klt`; CI diff-checks a fresh render against it |
| `README.md` | this claim document — kind basis, citation rationale and the disclosure of the uncited rows, the regeneration contract |

[#37]: https://github.com/2AMLogic/sg13g2-comparator/issues/37
[#3]: https://github.com/2AMLogic/sg13g2-comparator/issues/3
[#38]: https://github.com/2AMLogic/sg13g2-comparator/issues/38

# Porting / design plan

**Status**: DRAFT. This plan names what transfers from the nearest siblings
and what this repo designs fresh. It ratifies nothing and is not itself a
decision record — see [`spec/README.md`](README.md) for when a DR is
required.

## The topology-vs-methodology split

This repo's `CLAUDE.md` is explicit and load-bearing here: *"New block on
this PDK; the topology is textbook. StrongARM latch plus optional
continuous-time preamp. Start from the literature (Razavi's StrongARM
tutorial is canonical) and the PDK models, **not from the SAR canaries'
embedded comparators**."* That sentence draws a hard line this plan keeps
explicit throughout:

- **Topology** (latch architecture, device sizing, preamp/no-preamp
  decision) — sourced from the literature and SG13G2's own PDK device
  models. **Not** ported from `sky130-sar-adc` or `gf180-sar-adc`'s embedded
  comparators, even though those comparators are a mature, working
  StrongARM-class design on a sibling PDK.
- **Testbench / methodology structure** (offset sweep, Monte-Carlo draw
  convention, decision-time-vs-overdrive sweep, kickback bench) — this *is*
  legitimate prior art to reference, because it is topology-agnostic
  measurement scaffolding, not circuit IP. `sky130-sar-adc` and
  `gf180-sar-adc` both ship exactly this kind of reusable methodology (see
  below), and citing it here is explicitly sanctioned by `CLAUDE.md`'s own
  verification requirements (PVT corners, append-only evidence, stated
  statistical basis).

## Topology sourcing: literature + SG13G2 PDK models (not a sibling port)

- **Primary reference**: B. Razavi, *"The StrongARM Latch,"* IEEE Solid-State
  Circuits Magazine, 2015 — the canonical StrongARM comparator tutorial named
  directly in this repo's `CLAUDE.md`. It documents the standard
  double-tail / single-tail dynamic-latch topology, the regeneration
  mechanism, and the offset/kickback/speed tradeoffs that drive sizing
  decisions.
- **Device models**: SG13G2's own LV (`sg13_lv_nmos`/`sg13_lv_pmos`, 1.2 V
  core) and HV (`sg13_hv_nmos`/`sg13_hv_pmos`, 3.3 V I/O) MOS flavors, per
  the process specification and `sg13g2_moslv_mod.lib` /
  `sg13g2_moshv_mod.lib`, as already confirmed by
  [`sg13g2-bandgap`'s DR-0002](https://github.com/2AMLogic/sg13g2-bandgap/blob/main/spec/decision-records/0002-supply-voltage-scope.md).
  No 1.8 V-rated device family exists in this PDK, so the topology's headroom
  analysis (stacked-device count vs. supply) must be re-derived for SG13G2's
  1.2 V LV core rather than assumed from any 1.8 V or 3.3 V sibling.
- **What this explicitly rules out**: copying `sky130-sar-adc`'s
  [`design/comparator.sch`](https://github.com/2AMLogic/sky130-sar-adc)-equivalent
  or `gf180-sar-adc`'s
  [`design/comparator/comparator.sch`](https://github.com/2AMLogic/gf180-sar-adc/blob/main/design/comparator/comparator.sch)
  schematic, sizing, or preamp/no-preamp decision. Both of those are embedded
  SAR-ADC subblocks, sized for that ADC's own common-mode and speed
  constraints — not a validated, reusable standalone-comparator design this
  repo should inherit. The preamp/no-preamp decision itself is unresolved and
  is future design work (out of scope for this bootstrap issue), to be
  recorded as its own decision record once a schematic exists (mirroring
  `sky130-sar-adc`'s
  [`DR-004-comparator-topology-and-noise-budget.md`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/spec/decision-records/DR-004-comparator-topology-and-noise-budget.md)
  shape: context, decision, sizing rationale, alternatives considered, spec
  lines affected, consequences, open items).

## Testbench / methodology references (prior art on *how to measure*, not what to build)

### `sky130-sar-adc` — offset sweep, Monte-Carlo draw convention, decision-time-vs-overdrive sweep

[`sky130-sar-adc`](https://github.com/2AMLogic/sky130-sar-adc) ships a
dedicated, standalone comparator-characterization experiment at
[`sim/comparator-decision/`](https://github.com/2AMLogic/sky130-sar-adc/tree/main/sim/comparator-decision)
(confirmed present via the GitHub API, contents read directly):

- [`sim/comparator-decision/run.py`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/sim/comparator-decision/run.py)
  — a bespoke driver with four subcommands relevant to this repo's own
  bench design:
  - `regen` — transient regeneration-time sweep vs. differential input. This
    repo's decision-time-vs-overdrive row (see top-level README) should use
    the same sweep shape: single reset→evaluate transient edge per
    differential-input point, at the target clock, across PVT corners with
    seeds and run counts committed (per `CLAUDE.md`'s metastability
    requirement).
  - `offset` — mismatch-driven offset via `_mm`-class local-mismatch
    corners, Monte-Carlo draws varying `rndseed`, with a same-seed,
    mismatch-disabled negative control expected to reproduce identical
    results across draws. This is the Monte-Carlo draw convention this
    repo's own offset-sigma row should adopt, *if* SG13G2 ships equivalent
    per-instance local-mismatch terms for its LV devices (unconfirmed as of
    this pass — see the README's offset-sigma basis column); otherwise the
    documented sensitivity-analysis fallback applies instead.
  - `noise` — a reduced (loop-broken) sub-model `.noise` analysis of the
    input pair + tail, diode-connecting the cross-coupled latch pair to get
    a well-posed small-signal analysis. Documented there
    ([`DR-004-comparator-topology-and-noise-budget.md`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/spec/decision-records/DR-004-comparator-topology-and-noise-budget.md))
    as a **lower bound** (excludes regeneration-phase noise), which is the
    same caveat this repo's input-referred-noise row carries.
  - `noise-corners` — the noise measurement swept across the ratified PVT
    corner set.
- [`sim/comparator-decision/corners/`](https://github.com/2AMLogic/sky130-sar-adc/tree/main/sim/comparator-decision/corners),
  [`sim/comparator-decision/mc-draws/`](https://github.com/2AMLogic/sky130-sar-adc/tree/main/sim/comparator-decision/mc-draws),
  and a `records/`-equivalent evidence directory follow that repo's
  `sim/README.md` append-only convention (testbench/, netlist-snapshots/,
  corners/, mc-draws/, records/) — the same append-only shape this repo's own
  future `sim/README.md` should adopt, per `CLAUDE.md`'s "`sim/` results are
  append-only evidence."
- [`spec/decision-records/DR-004-comparator-topology-and-noise-budget.md`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/spec/decision-records/DR-004-comparator-topology-and-noise-budget.md)
  — the design-rationale record documenting that repo's comparator topology
  choice and noise-budget methodology. Referenced here for its noise
  *measurement methodology* (the loop-broken `.noise` technique and its
  lower-bound caveat) — not for its topology choice, which is out of scope
  per the split above.

### `gf180-sar-adc` — kickback bench

[`gf180-sar-adc`](https://github.com/2AMLogic/gf180-sar-adc) ships a
dedicated kickback-characterization experiment at
[`sim/comparator-kickback/`](https://github.com/2AMLogic/gf180-sar-adc/tree/main/sim/comparator-kickback)
(confirmed present via the GitHub API: `corners/`, `netlist-snapshots/`,
`records/` subdirectories), alongside that repo's embedded comparator design
at
[`design/comparator/comparator.sch`](https://github.com/2AMLogic/gf180-sar-adc/blob/main/design/comparator/comparator.sch)
/ `comparator.spice`. This repo's own kickback row (see top-level README)
has no same-PDK standalone-comparator prior art to draw numbers from — the
methodology reference here is specifically: drive the comparator's input
nodes from a realistic source impedance (not an ideal voltage source) and
record the disturbance directly at those nodes during a decision edge, per
`CLAUDE.md`'s "kickback is measured, not assumed." The `comparator.sch` /
`comparator.spice` design files are cited only to locate the kickback
experiment's driven circuit context — their StrongARM topology itself is,
again, out of scope per the split above.

### `sg13g2-bandgap` — same-PDK deck patterns

[`sg13g2-bandgap`](https://github.com/2AMLogic/sg13g2-bandgap) is the
nearest **same-PDK** sibling — not a comparator, but the repo that already
worked through SG13G2-specific tooling friction this repo will hit again.
Named here specifically for:

- The **klayout-tools SG13G2 DRC/LVS starter deck** — `sg13g2-bandgap`
  reports using the curated SG13G2 extraction/DRC deck that shipped with
  klayout-tools after
  [klayout-tools#905](https://github.com/2AMLogic/klayout-tools/issues/905) /
  [#911](https://github.com/2AMLogic/klayout-tools/pull/911), including its
  documented starter-subset coverage gaps (rules skipped, layers without
  rules) that show up verbatim in that repo's `drc_report.json` /
  `lvs_report.json` provenance fields. This repo's own future `klt drc` /
  `klt lvs` runs should expect and document the same class of gaps.
  [klayout-tools#1242](https://github.com/2AMLogic/klayout-tools/pull/1242)
  (SiGe HBT recognition declined upstream) and
  [klayout-tools#1273](https://github.com/2AMLogic/klayout-tools/issues/1273)
  (no well/substrate-tap layer in the curated deck) are two concrete,
  already-filed examples of the friction-protocol pattern this repo's
  `CLAUDE.md` asks agents to keep filing generically against the tool, not
  the design.
- **PVT sweep conventions** — `sg13g2-bandgap`'s pre- and post-layout
  (PEX) PVT sweep structure and its `spec/decision-records/` numbering
  convention (`NNNN-<slug>.md`) are the pattern this repo's own
  `spec/README.md` and future PVT sweeps mirror.
- **Supply-voltage scoping precedent** —
  [`spec/decision-records/0002-supply-voltage-scope.md`](https://github.com/2AMLogic/sg13g2-bandgap/blob/main/spec/decision-records/0002-supply-voltage-scope.md)
  is the record this repo's own README target-spec table cites directly for
  "SG13G2 has no 1.8 V flavor" — the same fact both repos independently need
  and one is not re-deriving from scratch.

## Other siblings consulted (not primary sources)

- [`sky130-comparator`](https://github.com/2AMLogic/sky130-comparator) and
  [`gf180-comparator`](https://github.com/2AMLogic/gf180-comparator) are this
  block's own twins (identical bench structure and topology-vs-methodology
  split, per each twin's own `CLAUDE.md`) but were, as of this issue's
  curation (2026-09-06), simultaneous wave-5 standups at the same or an
  adjacent bootstrap stage — `sky130-comparator`'s equivalent issue had
  already merged (its curated version independently made the same
  `spec/target-spec.md` → `README.md` filename correction, corroborating
  this repo's own curation), while `gf180-comparator`'s was still open and
  uncurated. Neither had numbers this repo's spec should port; they remain
  the comparative targets this repo's own numbers will eventually be read
  against (the 1.2 V SG13G2 vs. 1.8 V sky130 vs. gf180 headroom/speed/offset
  tradeoff), not sources for this pass.

## Next steps (not part of this issue's scope)

This issue is scaffolding only — no circuit design happens in this pass. See
[gap-to-T1 tracker issue #3](https://github.com/2AMLogic/sg13g2-comparator/issues/3)
for the honest, artifact-by-artifact survey of everything below (all
unchecked as of this pass). Future work, once a Builder picks it up:

1. Design `design/comparator.sch` from first principles against SG13G2's LV
   device models and Razavi's StrongARM tutorial, documenting the topology
   and preamp/no-preamp decision as a decision record (mirroring
   `sky130-sar-adc`'s DR-004 shape).
2. Confirm whether SG13G2's LV device models ship real per-instance
   local-mismatch terms (the "strong" statistical story) or only
   global-process corners (requiring the sensitivity-analysis fallback) —
   this is itself a committed early result per `CLAUDE.md`.
3. Stand up a `sim/comparator-decision/`-equivalent experiment directory
   here, porting the `regen`/`offset`/`noise` *methodology* (not numbers)
   from `sky130-sar-adc`, with this repo's own ideal-stimulus, standalone
   testbench (no CDAC or SAR-sequencer dependency).
4. Stand up a `sim/comparator-kickback/`-equivalent experiment, porting the
   *methodology* (not the embedded design) from `gf180-sar-adc`.
5. Once real measurements exist, revisit the README target-spec table's
   DRAFT bounds and file a ratification decision record if/when the table
   is set, changed, or scoped (see `spec/README.md`).

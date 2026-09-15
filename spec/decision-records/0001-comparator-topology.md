# 0001: Comparator topology — single-tail StrongARM latch, no continuous-time preamp

- **Status**: proposed (input to a future spec-ratification act; this record
  ratifies nothing in `README.md`'s target-specification table on its own —
  see "Spec lines affected" below and `spec/README.md`'s DR process).
- **Date**: 2026-09-15
- **Decided by**: Builder agent, issue #10
- **Related**: [#3](https://github.com/2AMLogic/sg13g2-comparator/issues/3)
  (gap-to-T1 tracker; this record is the topology decision named there as
  the first step of a three-issue chain — topology decision → schematic
  implementation → spec ratification), [`spec/porting-plan.md`](../porting-plan.md)
  ("topology sourcing" section, the mandate this record discharges),
  [`sim/dut/README.md`](../../sim/dut/README.md) ("Why the DUT is split into
  three subckts, not one", the interface-contract consequence this record
  must weigh), `sky130-sar-adc`'s
  [`DR-004-comparator-topology-and-noise-budget.md`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/spec/decision-records/DR-004-comparator-topology-and-noise-budget.md)
  (shape mirrored, not content — see Context), `sg13g2-bandgap`'s
  [`0002-supply-voltage-scope.md`](https://github.com/2AMLogic/sg13g2-bandgap/blob/main/spec/decision-records/0002-supply-voltage-scope.md)
  (confirms SG13G2's LV/HV-only device menu, cited below)
- **Supersedes**: none (first decision record in this repo)
- **Superseded by**: none

## Context

This repo's `CLAUDE.md` names the topology class already ("StrongARM latch
plus optional continuous-time preamp... Start from the literature (Razavi's
StrongARM tutorial is canonical) and the PDK models, not from the SAR
canaries' embedded comparators") but leaves two things genuinely open:
which member of the StrongARM/dynamic-latch family, and whether the optional
preamp is exercised. `spec/porting-plan.md`'s "topology sourcing" section
explicitly defers both to this record, and explicitly rules out copying
`sky130-sar-adc`'s or `gf180-sar-adc`'s embedded-comparator sizing or
topology conclusions — those are subblocks sized for a different ADC's own
common-mode and speed constraints, not reusable standalone-comparator
decisions.

**Why this is not a sky130-sar-adc DR-004 port.** DR-004 rejected a static
preamp on a *headroom-foreclosure* argument specific to its own design: an
1.8 V core rail whose input common mode was *pinned* near `V_REF/2` by a
differential top-plate CDAC, leaving only a 23.1 mV nominal margin
(DR-004's own Context, citing that repo's DR-003 Item 1) for the dynamic
latch's own tail + input-pair stack — before any preamp stage's own devices
are even considered. This repo has **no CDAC and no SAR sequencer** driving
the comparator's inputs (`sim/dut/README.md`'s three-subckt contract is
built for a standalone comparator); this repo's own `sim/dut.json` already
states the standalone convention explicitly: *"there is no CDAC or other
driving circuit to inherit a common mode from here, so mid-rail is the
natural standalone choice"* (`dut_vcm = 0.6 V` at the 1.2 V LV rail). The
common mode here is a **free design choice**, not an externally pinned
constraint — so DR-004's headroom-foreclosure mechanism does not
mechanically transfer, and re-deriving the headroom argument from SG13G2's
own numbers (below) is required rather than optional.

**Device menu.** SG13G2 ships exactly two MOS voltage flavors — LV
(`sg13_lv_nmos`/`sg13_lv_pmos`, 1.2 V core, defined in
`libs.tech/ngspice/models/sg13g2_moslv_mod.lib`, corners in
`cornerMOSlv.lib`) and HV (`sg13_hv_nmos`/`sg13_hv_pmos`, 3.3 V I/O) — no
1.8 V-rated family exists, confirmed independently here and already on file
via `sg13g2-bandgap` DR-0002. `README.md`'s target-specification table
already commits this block's Target supply to "1.2 V ±10% LV core"; this
record's headroom analysis is therefore scoped to the LV device flavor
only, consistent with (not re-litigating) that existing Target row.

**Real device numbers, not assumed ones.** To avoid re-deriving headroom
from an assumed `Vth`/`Vov` (the exact failure mode this repo's `CLAUDE.md`
warns against when porting a sibling's 1.8 V analysis), this record probed
the installed SG13G2 checkout's own PSP103-based LV models directly with an
uncommitted scratch `ngspice` `.op` run (diode-connected device + ideal
current source, the same single-device probe topology already committed at
[`sim/device-mismatch-confirm/testbench/tb_lv_mismatch_pair.spice.tmpl`](../../sim/device-mismatch-confirm/testbench/tb_lv_mismatch_pair.spice.tmpl)
and the PDK's own
`libs.tech/xschem/sg13g2_tests/mc_lv_{nmos,pmos}_cs_loop.sch` reference
testcase). **This probe is informal and not committed as `sim/` evidence**
— it is order-of-magnitude reasoning for a block-diagram-level topology
call, not a citable simulation record; a committed headroom/sizing testbench
is deferred to the schematic-implementation issue next in this chain.
Conditions: `mos_tt` corner, 27 °C, `psp103.osdi` pre-loaded, `l=0.5 µm`
throughout (a representative planning length, not a sizing commitment):

| device | W | `Id` | measured `Vgs` | PSP103 op-point `vth` |
|---|---|---|---|---|
| `sg13_lv_nmos` | 20 µm | 10 µA | 0.2292 V | 0.2349 V |
| `sg13_lv_pmos` | 20 µm | 10 µA | 0.4465 V | 0.3965 V |
| `sg13_lv_nmos` (tail candidate, same `J`) | 40 µm | 20 µA | 0.2130 V | — |

At this repo's own standalone bias convention (`dut_vcm = 0.6 V` mid-rail,
`dut_ib = 20 µA` total tail current, both already committed in
`sim/dut.json` for the placeholder DUT), a bottom-tail single-tail latch's
tail node sits near `V_cm − V_gs,input ≈ 0.6 − 0.229 ≈ 0.371 V` above `VSS`
— against a tail device whose own `Vgs` at the matching current density
(0.213 V) sits within ~20 mV of its extracted `Vth` (0.235 V), i.e. a small
`Vov` and correspondingly small `Vdsat` (tens of mV at most for a PSP103
device this close to weak/moderate inversion). **0.371 V of available
tail-node headroom against a `Vdsat` of a few tens of mV is a comfortable
margin, not a thin one** — the opposite character from DR-004's 23.1 mV
CDAC-pinned case, precisely because `V_cm` is free here rather than fixed.
This is the concrete, SG13G2-grounded re-derivation `CLAUDE.md`/the issue
require in place of assuming the sky130 conclusion carries over.

## Decision

**1. Topology: a single-tail (bottom-tail) StrongARM dynamic latch** — the
canonical topology Razavi's tutorial is named for: a tail current-source
device gating a differential NMOS input pair into a cross-coupled
NMOS/PMOS regenerative latch pair, with a CLK-gated PMOS reset (precharge)
pair holding both output nodes at `VDD` while `CLK = 0`. This is the
textbook single-stage member of the StrongARM/dynamic-latch family
`spec/porting-plan.md` names as the sourcing target, on SG13G2's own
`sg13_lv_nmos`/`sg13_lv_pmos` LV devices, at the 1.2 V LV core rail
`README.md` already targets. The double-tail variant is a real alternative
(see Alternatives Considered) but is not the topology this record adopts.

**2. No continuous-time preamp.** The latch's own input pair is the entire
analog front end; there is no preceding, continuously-biased differential
amplifier stage. Rationale, argued from SG13G2's own numbers and this
repo's own first-class spec rows (`CLAUDE.md`), not from DR-004's
headroom-foreclosure argument (Context, above, explains why that argument
does not transfer):

- **Headroom does not foreclose a preamp here** (Context) — so this is a
  power/speed cost-benefit judgment, not a "no other option" conclusion.
  Naming this plainly matters: a future revision that finds the bare
  latch's offset or noise unacceptable (Open items) has a real, not
  foreclosed, escalation path (Alternatives Considered).
- **Decision time is a first-class, aggressive spec row.**
  `README.md`'s DRAFT bound (`≤ 1.5 ns` Target / `≤ 0.8 ns` Stretch at
  50 mV overdrive) is measured from the evaluate edge. Any static preamp
  ahead of the latch inserts its own settling time before the latch can
  even begin regenerating, directly consuming part of that budget for a
  stage whose only job is to condition the signal the latch would resolve
  on its own. The StrongARM's whole appeal, per the tutorial this repo's
  `CLAUDE.md` names as canonical, is that positive-feedback regeneration
  from a reset condition reaches a rail-to-rail decision without a
  preceding gain stage — this record takes that appeal at face value given
  the aggressive timing target.
- **Power is a first-class spec row with the same character.**
  `README.md`'s Supply/power row sets `≤ 20 µW average` as Stretch. A
  continuously-biased preamp differential pair draws current for the
  entire clock period regardless of decision activity; the bare dynamic
  latch's hallmark property (also textbook) is that it draws current only
  during the brief evaluate/regeneration transient. Adding a preamp stage
  works directly against this budget for a design with no other forcing
  function (below) to justify the cost.
- **The offset/noise targets are not obviously out of reach for a bare
  latch at this technology**, so there is no forcing function pulling the
  other way. `README.md`'s DRAFT offset bound (`≤ 15 mV` / `≤ 8 mV` 3σ) and
  noise bound (`≤ 1.0 mV` / `≤ 0.6 mV` rms) sit in the same order of
  magnitude that DR-004's own bare-latch Monte Carlo produced at a
  *different* PDK/supply and a deliberately modest, unoptimized input-pair
  width (`W = 4 µm`: input-referred offset stdev ≈ 97 mV *before* the
  linear pick-off calibration's own stated invalidity for large draws, and
  a noise floor of 0.70 mV rms differential, lower-bound). That is evidence
  the *class* of number this repo targets is not disqualifying for a bare
  latch — not proof this repo's own eventual sizing clears it, which is
  explicitly schematic-implementation work, not this record's job.
- **A preamp is not ruled out permanently.** If the schematic-implementation
  issue's own transient offset/noise evidence (Consequences, below) finds
  the bare latch's numbers land outside the DRAFT bounds, adding a preamp
  becomes the natural next escalation, informed by real measured numbers
  from this topology rather than a hypothetical.

**3. This topology provides no DC-resolvable analog front end.** Per
`sim/dut/README.md`'s own framing, `comparator_dut_analog` is meant to
expose a real, continuously-biased sub-block with a stable small-signal
operating point — precisely what a preceding static preamp would be. A
bare single-tail latch's "front end" is its own input pair, which shares
the tail node and the cross-coupled latch's regenerative loop; it has no
stable DC operating point once `CLK` goes high (the loop's positive
feedback prevents one), and no meaning to being probed while `CLK` is held
low (it is off, undifferentiated from the tail switch). **This record
therefore answers the issue's required question directly: no, the chosen
topology does not provide a DC-resolvable front end for
`comparator_dut_analog`** — see Consequences for what that implies for the
offset-MC and preamp-noise benches.

## Sizing rationale (block-diagram level)

This is explicitly **not** transistor sizing — that is the
schematic-implementation issue's job. What this record commits to at the
block-diagram level, so that issue has a starting point rather than a blank
page:

- **Device count / roles**: 1 tail NMOS switch, 2 input-pair NMOS, 2
  cross-coupled NMOS (latch pair), 2 cross-coupled PMOS (latch pair), 2
  CLK-gated PMOS reset/precharge devices on the output nodes — the 9-device
  single-tail class DR-004 itself started from (its own Amendment A later
  added 2 more precharge devices for a reset-integrity defect specific to
  its own topology's internal node arrangement; whether SG13G2's version
  needs the same fix is schematic-implementation work, named as an open
  item below, not assumed either way).
- **Bias point**: `V_cm = 0.6 V` (mid-rail on the 1.2 V LV core), matching
  `sim/dut.json`'s existing standalone convention — this record adopts it
  rather than inventing a new one, since no CDAC or other driving circuit
  exists to derive a different common mode from.
- **Tail current**: same order of magnitude as `sim/dut.json`'s existing
  `dut_ib = 20 µA` (the value the harness already forces into the `ibias`
  pin for every bench) — not a sizing commitment, but the value the
  schematic-implementation issue should treat as the harness's existing
  expectation unless it has a documented reason to change it (which would
  itself require a `sim/dut.json` edit).
- **All devices are LV flavor** (`sg13_lv_nmos`/`sg13_lv_pmos`) at the 1.2 V
  core rail — no HV (3.3 V) devices are used anywhere in this topology;
  this record does not scope in a mixed-rail variant.

## Alternatives considered

- **Static preamp + single-tail latch** (preamp stage ahead of the latch
  decided above). Rejected for wave 1 — see Decision §2. Not headroom-
  foreclosed at this supply/common-mode combination (Context), unlike
  DR-004's case; the rejection here is a speed/power cost-benefit judgment
  against this repo's own first-class decision-time and power spec rows,
  and is explicitly revisitable if bare-latch offset/noise evidence
  disqualifies it.
- **Double-tail (two-stage) dynamic latch** — a first differential pair
  and tail driving intermediate nodes into a second cross-coupled
  regenerative stage, also covered by Razavi's tutorial and by
  `spec/porting-plan.md`'s own naming of "StrongARM- or double-tail-class"
  as the candidate family. Not chosen for wave 1: it adds device count,
  area, and a second dynamic current pulse for isolation/kickback benefits
  this record's single-tail choice does not strictly need (the kickback
  target, `≤ 5 mV` / `≤ 2 mV` into a 1 kΩ source, is a bench result to be
  measured against the chosen topology, not pre-judged here). Named as a
  real, not-pursued alternative — a legitimate escalation path alongside
  the preamp option if the single-tail latch's own kickback bench result
  is unacceptable.
- **HV (3.3 V) devices, or a mixed LV/HV rail.** Not considered further:
  `README.md`'s Target row already commits to the 1.2 V LV core, and this
  record's own headroom analysis shows the LV rail is not the constraint
  driving any topology choice here. Revisiting this would require its own
  supply-scope decision record, not a topology one.
- **Deferring the topology decision until a full PVT/Monte-Carlo campaign
  exists.** Rejected as a process matter, mirroring DR-004's own reasoning:
  the schematic-implementation issue is independently designable and
  simulatable without a full corner/MC campaign in hand first, and a
  block-diagram-level decision (this record) is what unblocks that issue
  rather than waiting on evidence that itself needs a schematic to
  produce.

## Spec lines affected

**No `README.md` row is ratified, changed, or scoped by this record** — per
`spec/README.md`'s DR process, that requires a later, explicit
spec-ratification act (the third issue in this chain), which this record is
not. This record does, however, name which DRAFT rows its Decision §3
finding (no DC-resolvable front end) bears on, so the ratification issue
does not have to rediscover it:

- **Offset sigma** and **Input-referred noise** rows — both currently
  describe (in `README.md`'s Basis column and `spec/porting-plan.md`) a
  `dc`/`.noise`-based measurement methodology mirroring DR-004's own
  reduced-sub-model technique. Decision §3 means that methodology is not
  available for this topology as a *primary* measurement (only as a
  DR-004-style lower-bound approximation on a diode-connected reduced
  sub-model) — see Consequences.
- **Decision time vs. overdrive** and **Kickback** rows are transient-based
  already (per their existing Basis text) and are unaffected by Decision
  §3.
- **Supply/power** row is unaffected — this record's device menu (LV-only)
  and bias point (`V_cm = 0.6 V`, `dut_ib` order of magnitude) are
  consistent with, not a change to, that row's existing "1.2 V ±10% LV
  core" Target.

## Consequences

1. **`sim/dut/README.md`'s named contingency is now the live path, not a
   hypothetical.** That file already states: *"If the ratified topology
   turns out to have no DC-resolvable front end at all — a bare dynamic
   latch, say — then `comparator_dut_analog` cannot be provided honestly,
   and the offset-MC and preamp-noise benches must be re-founded on
   transient Monte Carlo / transient noise instead."* This record commits
   to exactly that topology, so that re-founding is now required work, not
   an open question. It is explicitly **not** performed by this record —
   it is schematic-implementation (and possibly a follow-on
   harness-adaptation) scope, named here so it does not surface as a
   surprise later.
2. **A concrete interim path exists for `comparator_dut_analog`'s interface
   contract**, even though it cannot be a real continuously-biased stage:
   the same diode-connected, loop-broken reduced sub-model DR-004 itself
   used for its own (explicitly lower-bound, regeneration-noise-excluding)
   noise number. Whether the schematic-implementation issue uses that
   interim approximation (satisfying the pin contract syntactically, with
   the same DR-004-style lower-bound caveat carried forward) or the
   benches are fully re-founded on transient methodology instead (per
   `sim/dut/README.md`'s own suggestion) is **not decided by this record**
   — named as an open item.
3. **This aligns with, rather than contradicts, `CLAUDE.md`'s own
   metastability spec-row wording** — "the input-referred noise floor from
   transient-noise runs with seeds and run counts committed" already names
   transient noise as this repo's methodology for that row, independent of
   this record. Decision §3's consequence is therefore consistent with the
   repo's charter, not a new burden invented by this topology choice.
4. **The already-scaffolded `sim/comparator-offset-mc/` and
   `sim/comparator-preamp-noise/` bench directories** (issue #8, built and
   proven against the placeholder DUT's real, continuously-biased
   `comparator_dut_analog`) will need rework once a real design lands —
   their current `dc`/`.noise` bench structure assumed a DC-resolvable
   front end existed, consistent with the placeholder but not with this
   record's chosen topology. This is a real, named cost of this decision,
   not a free consequence.
5. **The reset/precharge device sizing may need the same kind of fix
   DR-004's Amendment A found** (its pre-amendment 9-device topology had a
   latch-pair-sources-to-`GND` arrangement that left the reset phase an
   unstable equilibrium at 3 of 9 corners) — SG13G2's own devices have
   different `Vth`/mismatch/conduction characteristics, so this is named as
   something the schematic-implementation issue must check on its own
   evidence, not assumed to reproduce or not reproduce here.

## Open items

- **A committed headroom/bias-point testbench.** This record's headroom
  numbers (Context) come from an uncommitted scratch probe, explicitly
  flagged as such. The schematic-implementation issue should commit a real
  `.op` testbench (or fold the check into the schematic's own bring-up) so
  the headroom claim becomes citable evidence, not a decision-record
  aside.
- **Whether `comparator_dut_analog` becomes a DR-004-style reduced
  sub-model or the offset-MC/preamp-noise benches are fully re-founded on
  transient methodology** (Consequence 2) — not decided here.
- **The slow/cold corner's headroom margin.** This record's numbers are
  `mos_tt`, 27 °C only, mirroring DR-004's own first-pass scope limitation
  (its Open items flagged the same gap for its own `ss`/`-40 °C` case, and
  it was never closed at the time of this citation). SG13G2's own
  slow/cold behavior is unconfirmed here.
- **Reset-device sizing / reset-integrity check** (Consequence 5) — not
  performed in this record; schematic-implementation scope.
- **Double-tail and preamp escalation paths** (Alternatives Considered)
  remain named, real options if the bare single-tail latch's measured
  offset, noise, or kickback numbers (once a real design and its
  benches exist) land outside `README.md`'s DRAFT bounds.
- **Ratification.** Like DR-004, nothing in this record is binding on
  `README.md`'s target-specification table until a future spec-ratification
  act rules on it — the third issue in this chain, not this one.

# `sim/comparator-regeneration/`

**Decision time versus input overdrive** over the full PVT grid, the
regeneration time constant **τ** extracted from it, near-metastable
behaviour, and the switching energy per decision.

Backs [`README.md`'s decision-time row](../../README.md#target-specification-ratified--dr-0002)
(≤ 1.5 ns at 50 mV overdrive, 1.2 V core; ≤ 0.8 ns stretch), and supplies the
τ that **every metastability statement in this repo is computed from** — now
itself a ratified, bounded sub-row (**τ ≤ 250 ps**, and ≤ 2.0 ns at 0.1 mV
overdrive, per
[DR-0002](../../spec/decision-records/0002-target-spec-ratification.md)) —
metastability is a first-class row here, per [`CLAUDE.md`](../../CLAUDE.md),
not a footnote.

```bash
python3 sim/run_corners.py comparator-regeneration -j 8
```

## Method

Three comparator instances, driven in parallel at three overdrives:

| rung | overdrive | why |
|---|---|---|
| `td_od50_ns` | 50 mV | the overdrive the spec row is stated at; large-signal, sets `t0` |
| `td_od1_ns` | 1 mV | inside the logarithmic region |
| `td_od01_ns` | 0.1 mV | one decade smaller again — the τ lever arm and a near-metastable probe |

A regenerative decision resolves in `t = t0 + τ·ln(V_logic /(A·V_in))`, so
the delay difference between two *known* overdrives gives τ directly:

```
tau = (t(0.1 mV) - t(1 mV)) / ln(10)
```

τ is extracted from the two small rungs because both sit inside the
logarithmic region. `resolve_decades = t(1 mV)/τ` is reported alongside it:
it is the exponent that any `exp(-t/τ)` metastability probability is taken
to, so it is the number that decides whether a metastability claim means
anything at this corner.

Two design decisions make the measurement robust:

- **Every instance decides both ways in one run.** Each input is a PWL that
  is negative for the first strobe and positive for the second, and the delay
  is taken on the *second* — where the output must actively flip a latch
  holding the opposite answer. So no delay depends on which state the output
  happened to power up in. The `dout_*_first` / `dout_*_end` check pairs are
  the proof that this actually happened.
- **Every timing threshold is supply-normalized** (each output divided by its
  own supply, crossed at 0.5). A fixed absolute threshold would turn the
  ±10 % supply axis into a measurement artefact.

Mismatch is off (this bench runs the `mos` corner set, not `mos_mismatch` —
see `sim/harness/corners.py`). Regeneration time and offset are separable and
are budgeted separately: offset moves the input at which the decision flips
(that is `sim/comparator-offset-mc/`), τ sets how fast a given overdrive
resolves. Combining them here would make neither attributable.

## Provenance

Methodology ported from
[`gf180-comparator/sim/comparator-regeneration/`](https://github.com/2AMLogic/gf180-comparator/tree/main/sim/comparator-regeneration)
(itself ported from `gf180-sar-adc`), per
[`spec/porting-plan.md`](../../spec/porting-plan.md) and issue #8.

**Ported:** τ extracted from a two-overdrive delay difference rather than
assumed; the both-polarities-in-one-run stimulus (the earlier alternative —
a `.nodeset`-hinted static-input deck — fails at cold corners because the
operating point sometimes converges to the answer the decision was meant to
produce); supply-normalized timing thresholds; parallel instances so one
transient run covers the whole ladder; reporting static current and
switching energy from the same deck; the `abstol=1e-13` solver tolerance
(see "Records" below for why it is load-bearing here too).

**Deliberately NOT ported:**

- **The topology and its sizing**, and every delay/τ/energy number from it.
- **The LSB-derived overdrive ladder.** Upstream's rungs come from a
  converter's reference LSB. There is no converter here: the primary rung is
  50 mV because that is what this repo's own spec row is stated at, and the
  small rungs are a clean decade apart to make the τ arithmetic exact.
- **The bit-cycle timing and its `margin_ns` measurement.** Those are a SAR
  bit-trial budget. A standalone comparator has no bit cycle to have margin
  against; the strobe period here is chosen only to give the front end more
  than ten time constants to settle before the decision.
- **The `--netlist ... extracted` post-layout variant** and its bespoke
  driver script. No layout exists in this repo yet; when one does, the DUT
  binding takes an `extracted` netlist and this same manifest runs unchanged
  (see [`sim/dut/README.md`](../dut/README.md)).
- **The glitch-window delay search.** Needed upstream because that repo's
  output stage pulses transiently when both regeneration nodes fall
  together — a property of that specific stage. Whether this repo's eventual
  output stage has the same behaviour is unknown until the topology is
  chosen; if it does, the window comes back and gets documented then rather
  than being carried in speculatively.

## Records

| record | DUT | grid | verdict |
|---|---|---|---|
| [`20260910-232833-8148438`](records/20260910-232833-8148438.md) | `placeholder-v1` (**placeholder**) | 45/45, `mos` × 3 T × 3 V | PASS |
| [`20260916-021945-36773c7`](records/20260916-021945-36773c7.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`) | 45/45, `mos` × 3 T × 3 V | **FAIL** (`td_od50_ns` temperature-axis floor only — recalibrated below, issue #16) |
| [`20260916-113309-180cca7`](records/20260916-113309-180cca7.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`) | 45/45, `mos` × 3 T × 3 V | PASS (post-recalibration, issue #16 — see below) |

**Read the banner on that record.** It was taken against the placeholder DUT
and substantiates the harness, not the decision-time row. It is also the
record the `td_od50_ns` per-axis floors are calibrated from (observed
weakest slices: process 2.61 %, temperature 12.76 %).

### Two placeholder-specific caveats that applied to `20260910-232833-8148438`

- `e_dec_fj` **carried no check and was not a figure.** The placeholder's
  decision stage was behavioural and drew no supply current at all, so what
  was measured was the front end's switching energy plus numerical residue of
  the charge integral. A check belonged here the moment a transistor-level
  decision stage was bound — which is now the case (`design/comparator.spice`,
  `sim/dut.json` provenance `schematic`), so `testbench/tb.json` now carries a
  real `e_dec_fj` sanity-envelope check (issue #20). The first transistor-level
  record, `20260916-021945-36773c7`, observed `e_dec_fj` in the ~31–61 fJ range
  across the 45-point grid.
- **Solver tolerances are load-bearing on this deck.** `abstol` is `1e-13`,
  not the `1e-15` `sim/comparator-kickback/`'s deck uses: at `1e-15`, several
  points fail to take their first transient step at all (`Timestep too
  small …`), because the three PWL-driven controlled sources present branch
  currents far below that floor at t = 0. A re-run that changes `reltol`,
  `vntol` or `abstol` is not bit-comparable with a record taken here. (This
  caveat is not DUT-specific and still applies unchanged to the real design.)

### Stale-prose flag on `20260916-021945-36773c7` (issue #20)

That record's own `Claim` line correctly states it substantiates
`design/comparator.spice`'s real transistor-level regeneration behaviour, but
its evidence `Note` list still carries the verbatim placeholder-era
"`e_dec_fj` CARRIES NO CHECK, DELIBERATELY…" text above, because the harness
reproduces `testbench/tb.json`'s `evidence.notes` into every record it
writes, and that field had not yet been corrected when this record was
taken. `sim/` records are append-only, so this record is **not** edited;
`tb.json` has been corrected (issue #20, including adding the `e_dec_fj`
check named above) so every record taken after it carries the accurate note.

### `td_od50_ns` temperature-axis floor: RECALIBRATED against the real DUT (issue #16)

`design/README.md`'s "Open items" section previously documented that this
bench's `td_od50_ns` temperature-axis floor (`>= 8.0 %`, calibrated against
the placeholder record above) FAILed against `20260916-021945-36773c7`'s
observed weakest temperature slice (`2.73 %`) — a real measured property of
the real design's regeneration speed, not a harness defect: regeneration
speed is set by transconductance, which falls with temperature, but the
same temperature rise also lowers `V_th` and so raises the effective
overdrive, partially cancelling the net temperature dependence. Per this
repo's "do not relax a check to make a result pass" rule, that FAIL was left
committed as-is (append-only) rather than silently patched, and the floor
has now been recalibrated with margin below the real DUT's own observed
value — not loosened to make the old record retroactively pass. The new
floor (`>= 1.5 %`, ~45 % margin below the observed `2.729 %`) is calibrated
from `20260916-021945-36773c7` (`testbench/tb.json`'s `td_od50_ns` check
comment carries the full citation) and is confirmed by the fresh
`20260916-113309-180cca7` record above — a clean-tree (`dirty: false`) run
taken *after* the recalibrated `tb.json` was committed, so it is citable
under `sim/README.md`'s "Record format" rule — which PASSes against it. The
process-axis floor (`>= 1.5 %`) is unchanged — it still holds against the
real DUT's own weakest observed process slice (`25.16 %`).

# `sim/comparator-offset-mc/`

**Monte-Carlo input-referred offset** of the comparator front end over the
full PVT grid, plus the part of that offset that moves with input common
mode.

Backs [`README.md`'s Offset-σ row](../../README.md#target-specification-draft--engineering-to-ratify)
(≤ 15 mV 3σ input-referred, ≤ 8 mV stretch) — the headline result for this
block, because SG13G2's LV device models are confirmed to ship real
per-instance local mismatch (`sim/device-mismatch-confirm/`, issue #6), so
this claim uses the Monte Carlo evidence path rather than the
sensitivity-analysis fallback.

> **`provenance: schematic` records here are a LOWER BOUND, not the design's
> real offset.** The chosen topology
> ([DR-0001](../../spec/decision-records/0001-comparator-topology.md)) has
> no DC-resolvable analog front end, so `comparator_dut_analog` (what this
> bench instantiates) is a diode-connected, loop-broken reduced sub-model —
> it excludes the regenerative loop's own contribution to offset entirely.
> See [`design/README.md`](../../design/README.md) before quoting any
> number below.

```bash
python3 sim/run_corners.py comparator-offset-mc -j 8
```

## Method

`setseed 20260910` once, then **200 draws per PVT point** through a
`dowhile` / `reset` loop — each `reset` re-evaluates the `agauss()`
expressions inside SG13G2's LV MOS `_mismatch` model, which is what makes
every iteration an independent local-mismatch draw (confirmed against the
installed checkout during issue #6, `sim/device-mismatch-confirm/README.md`).

> **Seeding mechanism corrected by issue #28.** On the pinned ngspice-46
> toolchain (`sim/toolchain.json`), the ngspice `set rndseed=<N>` control
> command does **not** actually seed the stream `agauss()` mismatch draws
> come from — two runs of the same deck with the same `set rndseed=`
> produce *different* draw sequences, confirmed by direct A/B testing
> during issue #28. `setseed <N>` (no `set` prefix) is the mechanism that
> actually reseeds ngspice-46's RNG stream and gives byte-identical draws
> across repeated runs — this manifest was switched to it, and every record
> taken **after** issue #28 is reproducible via the command above. The two
> records taken before issue #28 (see "Records" below) used the broken
> `set rndseed=` mechanism; their reproduction command does not reproduce
> their own numbers, and their own `mc_seed` text is left describing that
> (broken) mechanism as originally written, per `sim/`'s append-only
> convention.

Per draw, one `dc` sweep produces six operating points: the differential
input at 0 mV and +2 mV, at each of three common modes (`dut_vcm` − 50 mV,
`dut_vcm`, `dut_vcm` + 50 mV). From them:

- **gain** `A_v = (dv(+2 mV) − dv(0))/2 mV`, measured on the *same* draw;
- **offset** `V_os = −dv(0)/A_v`;
- **common-mode-dependent offset** `V_os(V_cm ± 50 mV) − V_os(V_cm)`.

The same seed is used at every PVT point (common random numbers), so movement
of σ across the grid is a real PVT effect rather than sampling noise. N for
statistical-error purposes is 200 — not 200 × 45 — giving 1/√(2N) = **5.0 %**
precision on each reported σ.

Every draw's `voa` / `ddc` / `dde` is printed into the per-corner log, so the
raw sample set is in the evidence trail and not only its summary statistics.

### Mismatch is a corner selection here, not a fragment parameter

Unlike gf180mcu (a global `sw_stat_mismatch` switch a fragment flips *after*
the model include), SG13G2 has no such switch: local mismatch is baked into
which `cornerMOSlv.lib` `.LIB` section this bench's `tb.json` names in its
`corners` field — `mos_mismatch` (the `mos_{tt,ff,ss,fs,sf}_mismatch` set,
see `sim/harness/corners.py`). This fragment therefore sets nothing
mismatch-related at all; the corner *is* the switch. `mm_ok` defaults to 1
inside the PDK's own `sg13_lv_nmos`/`sg13_lv_pmos` subckts.

### No resistor null control — and no resistor load at all

`gf180-comparator`'s twin of this bench carries a null control proving
gf180mcu's resistor model has its local-mismatch coefficient hard-set to
zero. This bench's DUT (`comparator_dut_analog` in `design/comparator.spice`)
has no resistor load to null-control in the first place: its front-end load
is a pair of diode-connected PMOS devices (`M5A`/`M6A`, per
[`design/README.md`](../../design/README.md)), not a resistor of any kind —
ideal or PDK. Those load devices ARE real `sg13_lv_pmos` instances, so their
own local mismatch is captured by `sig_vos_mv` below like any other device on
the `mos_mismatch` corner set; there is no separate resistor-mismatch term to
include or exclude. (An earlier, now-superseded placeholder DUT used an ideal
SPICE resistor load here, which genuinely had no PDK resistor mismatch model
to null-control — SG13G2's own `rsil`/`rhigh`/`rppd` resistor subckts do
carry real per-instance mismatch, unlike gf180mcu's, and remain a named,
tracked extension point, `sim/harness/corners.py`'s module docstring, for a
DUT that actually instantiates one.)

### The two checks that are not design numbers

- **`av_sigma_pct ≤ 5 %`** proves the Monte-Carlo draw is *preserved* across
  the two DC points a gain is taken from. If it were re-rolled, the "gain"
  would be dominated by the difference of two independent offsets and every
  `V_os` in the record would be meaningless. This is the check that makes the
  method valid.
- **`sig_vos_mv ≥ 0.05 mV`** is the mismatch-on guard AND this bench's
  sabotage negative control: `--sabotage-corners` forces every corner to
  plain `mos_tt` (mismatch off, see `sim/harness/corners.py`), which must
  and does collapse this measurement toward exactly zero. See
  `testbench/tb.json`'s own `checks.sig_vos_mv.description` for the full
  account, including the sqrt()/abs() numerical-precision trap a
  zero-variance draw set can otherwise trip (`sim/harness/README.md`
  "Known measurement floors").

## Provenance

Methodology ported from
[`gf180-comparator/sim/comparator-offset-mc/`](https://github.com/2AMLogic/gf180-comparator/tree/main/sim/comparator-offset-mc)
(itself ported from `gf180-sar-adc`), per
[`spec/porting-plan.md`](../../spec/porting-plan.md) and issue #8.

**Ported:** the fixed-seed + `dowhile`/`reset` draw loop (the seeding
control command itself, `setseed`, is corrected for ngspice-46 by issue #28
— see "Method" above); one instance, two DC points per draw, with
`av_sigma_pct` as the draw-preservation self-check; the common-random-numbers
convention across the grid; the "state seed, draw count and σ derivation in
the record" discipline; N = 200.

**Adapted for SG13G2 (structural, not a numeric change):** mismatch is
selected by corner (`mos_mismatch`), not by a `.param sw_stat_mismatch=1`
fragment line — see "Mismatch is a corner selection here" above and
`sim/harness/README.md`'s divergence table.

**Deliberately NOT ported:**

- **The topology, the sizing, and every number.** Upstream's front end is
  sized for its own ADC's CDAC-driven common mode; its result is same-family
  context that the target is reachable at *some* sizing, not a value this
  repo inherits.
- **The CDAC-derived common-mode band.** There is no CDAC here. The ±50 mV
  band is a stated property of this comparator's own input range, swept
  through an auxiliary source so the manifest never has to know what
  `dut_vcm` is.
- **Everything expressed in LSB.** A standalone comparator has no LSB; all
  bounds here are in volts.
- **`A_Vt` back-extraction.** It needs the input pair's effective W and L,
  which is a property of a design this repo does not have yet. It belongs in
  a device-characterization experiment, not here.
- **The resistor null control.** No PDK resistor is bound in this placeholder
  yet — see "No resistor null control" above.

## Records

| record | DUT | grid | verdict |
|---|---|---|---|
| [`20260910-232619-8148438`](records/20260910-232619-8148438.md) | `placeholder-v1` (**placeholder**) | 45/45, `mos_mismatch` × 3 T × 3 V | PASS |
| [`20260916-021822-36773c7`](records/20260916-021822-36773c7.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`, `comparator_dut_analog` — a DR-0001 lower-bound reduced sub-model, see banner above) | 45/45, `mos_mismatch` × 3 T × 3 V | PASS |
| [`20260916-125444-4d0cf7c`](records/20260916-125444-4d0cf7c.md) | `comparator-dr0001` (**schematic**, `design/comparator.spice`, `comparator_dut_analog`) | 45/45, `mos_mismatch` × 3 T × 3 V | PASS |

**Read the banner on that second record.** It was taken against the placeholder DUT
and substantiates the harness, not the offset row. It is also the record the
`vbias_anchor_mv` per-axis floors are calibrated from (observed weakest
slices: process 25.17 %, temperature 26.20 %).

**Stale-prose flag on `20260916-021822-36773c7` (issue #20).** That record's
own `Claim` line correctly states `comparator_dut_analog` is DR-0001's
diode-connected, loop-broken reduced sub-model — but its evidence `Note`
list still carries verbatim placeholder-era text describing "this
placeholder's front-end load" as "an ideal SPICE resistor, not a PDK
resistor subckt", because the harness reproduces `testbench/tb.json`'s
`evidence.notes` into every record it writes, and that field had not yet
been corrected when this record was taken. The real front-end load is a
diode-connected PMOS pair (see "No resistor null control" above), whose
local mismatch IS captured in this record's `sig_vos_mv`. `sim/` records are
append-only, so this record is **not** edited; `tb.json` has been corrected
(issue #20) so every record taken after it carries the accurate note.

**`20260916-125444-4d0cf7c` is the first record minted on the corrected
seeding mechanism (issue #28).** Its `mc_seed` correctly names `setseed`
(not `set rndseed=`) and is genuinely reproducible via its own committed
reproduction command — confirmed by re-running the single-corner slice
`--corners tt_mismatch --temps 27 --supply-tolerance 0 --no-write` twice and
diffing byte-identical output before minting this record. Its per-corner
`sig_vos_mv`/`vos_3sig_mv` numbers are statistically consistent with (not
required to exactly equal) `20260916-021822-36773c7`'s own numbers — both
draw from the same underlying mismatch-on population at N = 200 per point,
just via different (both fixed) seeds, `20260910` in both cases, but under
the previously-broken vs. now-corrected seeding mechanism, so an exact
numeric match between the two is not expected or required. The two earlier
records above predate this fix; their own reproduction commands do not
reproduce their own numbers (see "Method" above) — read their `mc_seed`
text with that caveat.

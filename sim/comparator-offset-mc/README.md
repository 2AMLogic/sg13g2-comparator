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

```bash
python3 sim/run_corners.py comparator-offset-mc -j 8
```

## Method

`set rndseed=20260910` once, then **200 draws per PVT point** through a
`dowhile` / `reset` loop — each `reset` re-evaluates the `agauss()`
expressions inside SG13G2's LV MOS `_mismatch` model, which is what makes
every iteration an independent local-mismatch draw (confirmed against the
installed checkout during issue #6, `sim/device-mismatch-confirm/README.md`).

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

### No resistor null control

`gf180-comparator`'s twin of this bench carries a null control proving
gf180mcu's resistor model has its local-mismatch coefficient hard-set to
zero. This placeholder's front-end load is an ideal SPICE resistor, not a
PDK resistor subckt (`sim/dut/placeholder_comparator.spice`'s header
explains why), so there is no PDK resistor mismatch model in this circuit to
null-control at all — not because SG13G2's resistors lack local mismatch
(they don't: `rsil`/`rhigh`/`rppd` carry real per-instance mismatch, unlike
gf180mcu's), but because this placeholder does not yet bind one. That is a
named, tracked extension point (`sim/harness/corners.py`'s module
docstring), not a silent omission.

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

**Ported:** the `set rndseed` + `dowhile`/`reset` draw loop; one instance,
two DC points per draw, with `av_sigma_pct` as the draw-preservation
self-check; the common-random-numbers convention across the grid; the "state
seed, draw count and σ derivation in the record" discipline; N = 200.

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

Not yet minted — see `sim/README.md`'s Experiments table for the one-command
cold start (`sim/characterize.sh characterize`). This section is updated
with the first committed 45-point record's id, DUT and verdict once it
lands; that record is also what the `vbias_anchor_mv` per-axis floors above
are calibrated from.

**Read the banner on any record here before citing it.** Every record taken
against `sim/dut.json`'s current `placeholder-v1` binding substantiates the
harness, not the offset row.

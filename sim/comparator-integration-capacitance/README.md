# Integration-node capacitance study (issue #497)

**Characterization, Phase 2 of [#479](https://github.com/2AMLogic/sg13g2-comparator/issues/479)
(Row 2 noise closure).** Measures whether *matched added capacitance at the
input-pair drains* can narrow the effective decision bandwidth enough to
close Row 2 within the Row 3c delay limit. It proposes no bound, adopts no
candidate, and changes no spec row, no DUT and not `sim/dut.json`.

Part of [#479](https://github.com/2AMLogic/sg13g2-comparator/issues/479).
[#498](https://github.com/2AMLogic/sg13g2-comparator/issues/498) varies PMOS
widths in a separate study. Phase 1 (the density/bandwidth split of Row 2)
landed in [#494](https://github.com/2AMLogic/sg13g2-comparator/pull/494).

## Declaration: what a setting is

- **Control** (zero added capacitance): the archived `ib10_sw20lat6` geometry
  of the #92 bias study — `XM1.w=8u XM2.w=8u XM3.w=6u XM4.w=6u XM5.w=6u
  XM6.w=6u XMSW.w=20u` at `dut_ib=1e-05` — read back from the committed
  [`20261115-issue92-bias`](../klt-corner-verification/campaigns/20261115-issue92-bias/)
  campaign. Its 18-point screening mean is **1.05259 mV rms** at the fixed
  36.27 nV/√Hz injection; its worst Row 3c decision is **1.862 ns** at
  SS / −40 °C / 1.08 V against the 2.0 ns Target.
- **Settings**: an equal capacitance per side added at the integration
  nodes, **both terminals of each capacitor declared**: each runs from its
  node (`np` on the vinp side, `nn` on the vinn side) to the subcircuit's
  `vss` rail. Declared set (per side): **1 fF, 2 fF, 4 fF** — `cadd1f`,
  `cadd2f`, `cadd4f` — spanning the ~10 % bandwidth cut the control needs
  for 1.0 mV with margin on both sides.

## Candidate netlists and the structural DUT binding

[`candidates/cadd1f.spice`](candidates/cadd1f.spice),
[`candidates/cadd2f.spice`](candidates/cadd2f.spice) and
[`candidates/cadd4f.spice`](candidates/cadd4f.spice) are each
`design/comparator.spice` verbatim plus exactly two matched capacitor pairs:

- inside `.subckt comparator`: `C497P np vss <C>` / `C497N nn vss <C>`;
- inside `.subckt comparator_dut_analog`: `C497AP aon vss <C>` /
  `C497AN aop vss <C>` (the loop-broken mapping below).

The extra elements cannot be expressed by the issue #92 geometry override
(w/l fields only), so a candidate is a **structural DUT binding**:
`build --candidate NAME` inlines the named file instead of the schematic and
declares its name, path and sha256 in the body header, and
`sim/kltsim/grade.py`'s DUT check verifies the embedded DUT against the
reference FILE's own bytes — a self-consistent body of the *wrong* setting, a
tampered or drifted reference, a stale envelope hash and the plain schematic
are each refused for a named setting. Both build and grade also re-derive the
candidate from today's `design/comparator.spice`, so a candidate cannot
silently drift from the schematic it modifies. The default schematic path and
the geometry-only path are unchanged for existing callers.

Candidate files are inputs pinned by hash (like `design/comparator.spice`
itself, not append-only evidence): a changed candidate invalidates every body
that cites it, visibly.

## Loop-broken model mapping (Phase 1 calibration)

The Phase 1 method (issue #477) measures each design's own input-referred
density `S = white_out(1 MHz) / |Av(1 Hz)|` against the loop-broken
`comparator_dut_analog` sub-model. The capacitance maps **node to node**:
`np` (drain of XM1, vinp side) is `aon` (drain of XM1A, vinp side) in the
model, and `nn` ↔ `aop`, so each capacitor keeps its node-to-vss terminals.
[`reports/20261121-issue497-calibration/front-end-cadd.spice`](reports/20261121-issue497-calibration/front-end-cadd.spice)
carries exactly that mapping as a `c_add` parameter; the control row
(`c_add = 0`) reproduces Phase 1's measured `ib10_sw20lat6` densities as the
cross-check. The calibration reports differential output density at 1 MHz,
absolute gain at 1 Hz and their quotient per setting per PVT point.

## Measurement plan

1. **Screens** on the #92 reduced 18-point grid (tt/ff/ss × 1.08/1.32 V ×
   −40/27/125 °C), all on the batch fleet: the noise bench (N = 80 trials
   per rung, unchanged 36.27 nV/√Hz injection, one six-point part per
   process so the three parts tile the 18 points exactly once) and the
   regeneration bench (worst Row 3c decision). Published per setting: the
   mean per-point probit sigma with valid/expected counts, and the worst
   0.1 mV decision delay with its PVT point and counts.
2. **At most one setting advances** to the full 45-point Rows 1–5 campaign,
   graded by `sim/kltsim/grade.py` against DR-0002 and compared with the
   archived
   [`full_w8_l034`](../klt-corner-verification/campaigns/20261009-issue92/full_w8_l034/grading.md)
   baseline (a Target the 8 µm baseline passes must still pass). A negative
   result — no setting reaches 1.0 mV rms inside the 2.0 ns Row 3c limit —
   completes the study; eliminated settings keep their full-grid rows
   unmeasured.

Every Row 2 figure is labelled with its grid, statistic and injected
density. The unchanged-bench comparison runs at 36.27 nV/√Hz; candidate-own
density figures derived from the calibration are projections, labelled as
such, and never a Row 2 Target verdict.

## Tooling disclosures

The ngspice transient-noise source ignores klt's per-sample
`.options seed=` ([klayout-tools#2963](https://github.com/2AMLogic/klayout-tools/issues/2963));
separate transient sources additionally cannot be independently seeded
([klayout-tools#5772](https://github.com/2AMLogic/klayout-tools/issues/5772)).
Draws are therefore independent but not reproducible; the grader refuses any
point whose samples repeat a raw noise draw. Generic `klt` capability gaps
found by this study are filed under the
[friction protocol](../CLAUDE.md) and linked from the report.

## Reproduce

```bash
# build one setting's screen inputs (campaign dir under
# sim/klt-corner-verification/campaigns/):
python3 sim/run_klt_corner_verification.py build \
  --campaign 20261121-issue497/scr_cadd2f --screen \
  --bench regeneration --bench transient_noise \
  --dut-param dut_ib=1e-05 \
  --geometry XM1.w=8u --geometry XM2.w=8u --geometry XM3.w=6u \
  --geometry XM4.w=6u --geometry XM5.w=6u --geometry XM6.w=6u \
  --geometry XMSW.w=20u --candidate cadd2f
python3 sim/run_klt_corner_verification.py run \
  --campaign 20261121-issue497/scr_cadd2f --bench regeneration \
  --capacity-wait-s 600
python3 sim/run_klt_corner_verification.py run \
  --campaign 20261121-issue497/scr_cadd2f --bench transient_noise \
  --capacity-wait-s 600
# the study report (control + screens + finalists):
python3 sim/run_klt_corner_verification.py capacitance --campaign 20261121-issue497
```

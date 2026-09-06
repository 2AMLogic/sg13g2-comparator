# sg13g2-comparator

A dynamic latched comparator on IHP SG13G2 on
[IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK), IHP's open-source 130 nm SiGe BiCMOS PDK — designed by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source xschem + ngspice flow.

**Status: just opened.** Nothing is designed yet. The first work is
the offset and noise measurement methodology — Monte-Carlo mismatch against the PDK's statistical models, if shipped, or a documented sensitivity fallback.
See [issue #3](https://github.com/2AMLogic/sg13g2-comparator/issues/3) for
the honest, artifact-by-artifact gap-to-T1 survey (everything unchecked —
nothing is built yet) and [`spec/porting-plan.md`](spec/porting-plan.md) for
what's designed fresh (topology, from the literature and SG13G2's own PDK
models) versus what's referenced as methodology prior art (testbench
structure, from `sky130-sar-adc` and `gf180-sar-adc`).

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation here is produced by AI agents working from a ratified
spec and an append-only evidence trail — not human-authored work that agents
merely assisted with. Verification is the product: every claim traces to a
recorded result under PVT corners. Where the agents hit friction with the
open-source tooling — most often
[klayout-tools](https://github.com/2AMLogic/klayout-tools) — that friction is
filed as a public issue against the tool itself, so the fix benefits everyone
using this PDK, not just this repo.

## Why this block, on this PDK

The catalog has SAR ADCs whose comparators live inside them, but no
standalone comparator on any PDK — no block whose spec IS offset, noise,
metastability, and decision time, measured for their own sake. A StrongARM
latch on SG13G2's CMOS devices fills that gap on the thinnest foundry and
becomes the reusable decision element for a future sg13g2 SAR ADC.

The honest centerpiece is **statistical claims from open models**: offset
sigma means Monte-Carlo over the PDK's mismatch models if SG13G2 ships them,
and a documented, clearly-labelled sensitivity-analysis fallback if it does
not. Which of those two worlds this PDK lives in is itself a result worth
committing early. Metastability gets characterized (decision-time vs input
overdrive), not hand-waved.

## Target specification (DRAFT — engineering to ratify)

No sibling has a ratified comparator spec to port yet —
[sky130-comparator](https://github.com/2AMLogic/sky130-comparator) and
[gf180-comparator](https://github.com/2AMLogic/gf180-comparator) are the same
wave-5 standalone-comparator twin set, at the identical bootstrap stage as
this repo (sky130-comparator's bootstrap issue has since merged; neither twin
had a ratified spec at the time this table was drafted). These bounds are
therefore original engineering judgment for SG13G2's 1.2 V LV core flavor,
not a ported number — SG13G2 has no 1.8 V-rated device family (only a 1.2 V
LV core and a 3.3 V HV I/O flavor, per
[`sg13g2-bandgap`'s DR-0002](https://github.com/2AMLogic/sg13g2-bandgap/blob/main/spec/decision-records/0002-supply-voltage-scope.md)),
so the sky130 twin's 1.8 V numbers do not carry over even as a starting
point. Each row states its basis rather than asserting a bare figure. See
[`spec/porting-plan.md`](spec/porting-plan.md) for what *does* transfer
(testbench structure and methodology, not topology or spec numbers) from
[`sky130-sar-adc`](https://github.com/2AMLogic/sky130-sar-adc) and
[`gf180-sar-adc`](https://github.com/2AMLogic/gf180-sar-adc).

| Parameter | Target | Stretch | Basis |
|---|---|---|---|
| Offset sigma | ≤ 15 mV, 3σ (input-referred, post-calibration-free) | ≤ 8 mV, 3σ | Monte Carlo over SG13G2's shipped local-mismatch device models, once confirmed present in the installed PDK's `sg13g2_moslv_mod.lib` (per `CLAUDE.md`'s "Offset claims state their statistical basis"), N ≥ 200 draws per corner, once a comparator schematic exists. If SG13G2 does not ship per-instance mismatch terms for LV devices, this row falls back to a documented sensitivity analysis (device-size / threshold-perturbation sweep) instead of a Monte-Carlo sigma — which of the two worlds applies is itself a result this repo commits to recording, not assumed here. No schematic exists yet, so no measurement exists; this bound is a placeholder pending design. |
| Input-referred noise | ≤ 1.0 mV rms, differential | ≤ 0.6 mV rms, differential | ngspice `.noise` analysis on a reduced (loop-broken) sub-model of the latch's input pair + tail — the same methodology `sky130-sar-adc`'s [`spec/decision-records/DR-004-comparator-topology-and-noise-budget.md`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/spec/decision-records/DR-004-comparator-topology-and-noise-budget.md) documents (excludes regeneration-phase noise; a lower bound, not a complete figure). No SG13G2-specific same-topology measurement exists yet — this bound is first-principles engineering judgment pending this repo's own testbench (see porting plan). |
| Decision time vs. overdrive | ≤ 1.5 ns at 50 mV overdrive, 1.2 V core | ≤ 0.8 ns at 50 mV overdrive | Transient regeneration-time sweep vs. differential input at the target clock, methodology mirroring `sky130-sar-adc`'s [`sim/comparator-decision/run.py`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/sim/comparator-decision/run.py) `regen` subcommand, run across this repo's own PVT corners with seeds and run counts committed (per `CLAUDE.md`'s metastability-as-first-class-spec-row requirement). This is a first-class spec row, not a derived afterthought: the noise floor above and this row together define the metastability characterization. No SG13G2 measurement exists yet; this bound is a placeholder pending design. |
| Kickback | ≤ 5 mV disturbance into a 1 kΩ source impedance at the input nodes, single decision edge | ≤ 2 mV | Bench drives a realistic source impedance and records the input disturbance directly (per `CLAUDE.md`'s "kickback is measured, not assumed"), methodology mirroring `gf180-sar-adc`'s [`sim/comparator-kickback/`](https://github.com/2AMLogic/gf180-sar-adc/tree/main/sim/comparator-kickback) experiment structure. Source impedance (1 kΩ) is a stated planning assumption, not yet tied to any specific driving stage; no SG13G2 measurement exists yet. |
| Supply / power | 1.2 V ±10% LV core (`sg13_lv_nmos`/`sg13_lv_pmos`) | ≤ 20 µW average at a stated clock rate (TBD) | SG13G2 ships exactly two MOS voltage flavors — 1.2 V LV core and 3.3 V HV I/O, no 1.8 V flavor — confirmed against the SG13G2 process spec and `sg13g2_moslv_mod.lib`/`sg13g2_moshv_mod.lib` via `sg13g2-bandgap`'s [DR-0002](https://github.com/2AMLogic/sg13g2-bandgap/blob/main/spec/decision-records/0002-supply-voltage-scope.md). The 1.2 V LV core is the Target flavor per this repo's `CLAUDE.md` ("supply/power at 1.2 V core"); a 3.3 V HV I/O flavor is scoped in only if a future decision record ratifies it (see `spec/README.md`). Power figures are first-principles engineering judgment — no design exists yet to measure quiescent/dynamic current. |

**Statistical basis, stated once for the table.** Whether SG13G2's LV device
models ship real per-instance local-mismatch terms (the "strong" statistical
story) or only global-process corners (requiring the documented
sensitivity-analysis fallback) is not yet confirmed for this repo — see
`CLAUDE.md`'s "Offset claims state their statistical basis." Establishing
which of those two worlds applies is itself an early, committed result, not
assumed in this table.

**Ratification status.** This table stays **DRAFT** in this pass — no
decision record is filed for it yet. [`spec/README.md`](spec/README.md)
documents when a DR is required (whenever this table is set, changed, or
scoped) and how to write one.

## License

Apache-2.0.

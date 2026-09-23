# sg13g2-comparator

A dynamic latched comparator on IHP SG13G2 on
[IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK), IHP's open-source 130 nm SiGe BiCMOS PDK — designed by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source xschem + ngspice flow.

![fleet burndown](https://raw.githubusercontent.com/2AMLogic/2am/main/fleet-metrics/charts/sg13g2-comparator.svg)

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

## Target specification (ratified — DR-0002)

**Ratified by [`spec/decision-records/0002-target-spec-ratification.md`](spec/decision-records/0002-target-spec-ratification.md)**
against the measured `provenance: schematic` records listed in the Basis column
— every one of them taken on DR-0001's single-tail StrongARM
([`design/`](design/)) over a 45-point PVT grid (5 process × 3 temperature ×
3 supply). **One row's Target is ratified in a state the current design does
not meet** (input-referred noise — on the whole-latch compliance evidence
DR-0002's pre-merge revision folds in), and the design also misses three
Stretch-bound targets (the offset Stretch at 27/45 points, the decision-time
Stretch at the `ss` corners, the power Stretch); the Measured column says so
per row, because `CLAUDE.md` forbids relaxing a bound to make a result pass.
One row (Kickback) was revised rather than held — DR-0002 §"Row 4"
gives the full reasoning and the alternatives that were rejected; its charge
sub-bound is ratified as **consistent, not certified**, because no committed
testbench emits that quantity directly (DR-0002 Row 4 (b)–(c) and its open
items).

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

| Parameter | Target (ratified) | Stretch | Measured on the DR-0001 schematic | Basis |
|---|---|---|---|---|
| Offset sigma | ≤ 15 mV, 3σ (input-referred, calibration-free), at **every** PVT point. Statistical basis: Monte Carlo over SG13G2's per-instance local-mismatch models, two benches — front-end `comparator-offset-mc`: N = 200 draws per point, seed `20260910`, σ precision ±5 %; whole-latch `comparator-offset-transient-mc`: N = 60 draws per point, seed `20260916`, σ precision ±9.1 % | ≤ 8 mV, 3σ | **Target MET at 45/45 points on the whole latch; Stretch NOT MET at 27/45.** Whole latch (un-reduced `comparator_dut`: input pair, tail, cross-coupled regenerative pair, reset devices, isolation inverters, SR latch — real strobe cadence): 3σ 7.456 mV (`tt_mismatch_27c_1.32v`) … **10.537 mV** (`tt_mismatch_125c_1.08v`), mean 8.404 mV — inside the 15 mV Target at every one of the 45 points, above the 8 mV Stretch at 27/45. Record [`20260917-060858-ea40b57`](sim/comparator-offset-transient-mc/records/20260917-060858-ea40b57.md). Front end only (DR-0001's diode-connected, loop-broken reduced sub-model, a **lower bound**: excludes the regenerative loop's own offset term — [`design/README.md`](design/README.md)): 3σ 11.61 … **18.10 mV**, mean 14.14 mV, over 15 mV at **13 of 45** points (ten 125 °C corners plus three fast-process 27 °C corners just over the line). Record [`20260916-125444-4d0cf7c`](sim/comparator-offset-mc/records/20260916-125444-4d0cf7c.md). **The verdict rests on the whole-latch number** — nothing in the topology is excluded from it, so nothing is extrapolated — and it comes out *lower* than the front-end-only number at every one of the 45 matched points: a different-operating-point/different-mismatch-sensitivity effect, not either bench being wrong ([`comparator-offset-transient-mc/README.md` → "Relationship to `comparator-offset-mc`"](sim/comparator-offset-transient-mc/README.md#relationship-to-comparator-offset-mc); DR-0002 Row 1). No whole-latch **common-mode** sweep exists yet — the MET verdict claims nothing about common-mode movement | **Monte Carlo**, confirmed as the applicable evidence path (not the sensitivity-analysis fallback): SG13G2's LV device models (`sg13_lv_nmos`/`sg13_lv_pmos`) DO ship real per-instance local-mismatch terms, confirmed both by reading `sg13g2_moslv_mod_mismatch.lib`/`sg13g2_moslv_mismatch.lib`/`cornerMOSlv.lib` and by an actual ngspice Monte Carlo testbench (N=30 draws, seeded, with a same-seed mismatch-disabled negative control showing exactly zero spread) — see [`sim/device-mismatch-confirm/`](sim/device-mismatch-confirm/) (issue #6). That fixed the *evidence path* (Monte Carlo over shipped local-mismatch models, N ≥ 200 draws per corner); the comparator-level sweeps that exercise it live at [`sim/comparator-offset-mc/`](sim/comparator-offset-mc/) (front end) and [`sim/comparator-offset-transient-mc/`](sim/comparator-offset-transient-mc/) (whole latch), both against the real DR-0001 netlist (`sim/dut.json`, `provenance: schematic`). The ratified bound itself is unchanged from the DRAFT table — engineering judgment for a calibration-free standalone comparator on this node — and re-deriving it in either direction on the first whole-latch 45-point grid was deliberately **not** done (DR-0002 Row 1). |
| Input-referred noise | ≤ 1.0 mV rms, differential, total integrated. **Compliance evidence path (ratified scoping): transient-noise runs with seeds and run counts committed**; the `.noise` number below is a ratified *reportable lower bound*, not a compliance certificate | ≤ 0.6 mV rms, differential | **NOT MET on the compliance path.** Whole latch (`comparator_dut`: real strobe, real cross-coupled regenerative pair): `TRNOISE`-injected transient decision statistics, **N = 80 trials per rung per PVT point** (3 rungs), 45/45 points, injecting the AC bench's own input-referred white density (36.27 nV/√Hz) and letting the latch set its own aperture. Implied 1σ decision noise: **grid-wide mean 1.335 mV** (min 0.889 mV (`tt_27c_1.20v`) … max 2.710 mV (`tt_125c_1.08v`)) — the summary statistic the bench's own precision analysis designates (±13 % 1σ per-corner sampling scatter at N = 80). Record [`20260921-154729-41cbc7f`](sim/comparator-transient-noise/records/20260921-154729-41cbc7f.md), `Verdict: PASS`. Front-end lower bound (reportable, not compliance): 216.7 µV rms (`ff_-40c_1.20v`) … **388.9 µV rms** (`fs_125c_1.08v`) across 45 points (nominal corner 277.8 µV over that sub-model's own 58.7 MHz band). Record [`20260916-113303-180cca7`](sim/comparator-preamp-noise/records/20260916-113303-180cca7.md). **The compliance number is itself still a lower bound** — the regenerative pair's own device noise is not injected (the DUT's black-box pin contract gives the testbench no access to internal nodes), so a strictly-more-complete measurement predicts a *higher* floor still ([`comparator-transient-noise/README.md` → "What this bench adds, and does not add"](sim/comparator-transient-noise/README.md#what-this-bench-adds-and-does-not-add-over-comparator-preamp-noise); DR-0002 Row 2) | Compliance path (whole latch): ngspice `TRNOISE` decision statistics against the un-reduced `comparator_dut` — the evidence form `CLAUDE.md` mandates for this row ("the input-referred noise floor from transient-noise runs with seeds and run counts committed"); the run count, not the seed, is the load-bearing reproducibility input. Lower bound: ngspice `.noise` analysis on a reduced (loop-broken) sub-model of the latch's input pair + tail — the same methodology `sky130-sar-adc`'s [`spec/decision-records/DR-004-comparator-topology-and-noise-budget.md`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/spec/decision-records/DR-004-comparator-topology-and-noise-budget.md) documents (excludes regeneration-phase noise; a lower bound, not a complete figure). The compliance bench lives at [`sim/comparator-transient-noise/`](sim/comparator-transient-noise/) and is calibrated against [`sim/comparator-preamp-noise/`](sim/comparator-preamp-noise/)'s own committed white-noise density — retiring the AC bench would remove the number the compliance bench is calibrated against, so both stay committed. The bound itself is unchanged from the DRAFT table — first-principles engineering judgment, and a first compliance-path measurement missing it is precisely not a basis to move it: `CLAUDE.md` forbids relaxing-to-pass, and ±13 % scatter plus a known-missing noise term is not evidence to re-derive it in either direction (DR-0002 Row 2). |
| Decision time vs. overdrive, and **metastability** | ≤ 1.5 ns at 50 mV overdrive, 1.2 V core, at **every** PVT point. Ratified metastability sub-rows (new in DR-0002): **τ ≤ 250 ps** (regeneration time constant, worst point) and **≤ 2.0 ns at 0.1 mV overdrive** | ≤ 0.8 ns at 50 mV overdrive | **Target MET at 45/45 points; Stretch NOT MET at 9/45.** 50 mV: 0.596 ns (`ff_-40c_1.08v`) … **0.850 ns** (`ss_125c_1.32v`) — the 9 misses are every `ss` point. **τ: 42.6 … 167.3 ps** (worst `ss_-40c_1.08v`), ≥ 7.63 decades of resolution at every point — **MET**. 0.1 mV: 0.910 … **1.662 ns** — **MET**. Record [`20260916-021945-36773c7`](sim/comparator-regeneration/records/20260916-021945-36773c7.md) — cited as drafted: it carries `Verdict: FAIL` on a corner-sensitivity *check floor* calibrated against the old placeholder DUT, a benign floor-calibration artifact and not a measurement or spec failure (DR-0002 "The evidence this record rests on"); the recalibrated-floor re-run of the same measurement, [`20260916-113309-180cca7`](sim/comparator-regeneration/records/20260916-113309-180cca7.md) with identical numbers, exists alongside it | Transient regeneration-time sweep vs. differential input at the target clock, methodology mirroring `sky130-sar-adc`'s [`sim/comparator-decision/run.py`](https://github.com/2AMLogic/sky130-sar-adc/blob/main/sim/comparator-decision/run.py) `regen` subcommand, run across this repo's own PVT corners with seeds and run counts committed (per `CLAUDE.md`'s metastability-as-first-class-spec-row requirement). This is a first-class spec row, not a derived afterthought: the noise floor above and this row together define the metastability characterization. The bench lives at [`sim/comparator-regeneration/`](sim/comparator-regeneration/) and runs a 3-rung overdrive ladder (50 mV / 1 mV / 0.1 mV) against the real DR-0001 netlist; τ is extracted from the (1 mV, 0.1 mV) pair as Δt/ln 10. The 1.5 ns/0.8 ns bounds are unchanged from the DRAFT table. The τ bound is new and founded on measurement plus the clock: at the ratified 33.3 MHz the 10 ns strobe gives ≥ 40 τ ≈ 17 decades of regeneration, and 250 ps is 1.5× the measured worst point, so halving `ss`-corner τ margin breaks the row rather than quietly passing it (DR-0002 Row 3). |
| **Kickback** (row **revised** by DR-0002 — see Basis) | ≤ 25 fC/side **peak transient** injected charge per decision edge — measured at the 1 kΩ / 100 fF input node (branch A of the kickback bench) as the peak net charge displaced from that node over a 30 … 45 ns window referenced to its pre-decision level, **not** the net charge retained after recovery (full condition: DR-0002 Row 4) — **and** ≤ 100 µV signal-dependent differential residue at the input nodes at the end of a 30 ns cycle against a non-charge-restoring source (1 GΩ / 1 pF). Peak single-ended excursion into the stated 1 kΩ / 100 fF drive is a **reporting requirement**, recorded at every PVT point but deliberately unbounded until a driving stage is named | ≤ 8 fC/side, **and** ≤ 30 µV residue | **Charge sub-bound CONSISTENT, NOT CERTIFIED; residue sub-bound MET; Stretch NOT MET on charge.** Q_kick is **estimated** at 8.8 … **14.3 fC/side** from `kick_1k_peak_mv × C_in` — the bench emits no charge measurement, and that estimator under-reports by ~1.3 … 2.9× because branch A's R_src·C_in = 100 ps is the same order as the 100 ps clock edge and the 42.6 … 167.3 ps regeneration τ, giving a true-value bracket of ~**11 … 41 fC/side** that straddles the 25 fC bound (derivation: DR-0002 Row 4 (b); a direct Q_kick bench key is an open item there). Residue 1.70 µV (`ff_125c_1.32v`) … **15.40 µV** (`ss_-40c_1.20v`) — **MET**, 6.5× margin, directly from a committed bench key at 45/45 points. Stretch needs 8 fC and is missed before any bias correction. Net *settled* charge on the non-restoring branch is a different quantity, 0.008 … 1.673 fC/side, and is **not** what this row bounds. **Reported peak excursion: +87.7 mV (`ss_-40c_1.08v`) … +143.3 mV (`ff_125c_1.32v`)**, negative excursion −29.3 … −40.6 mV, decision correct at 45/45. Record [`20260916-022249-36773c7`](sim/comparator-kickback/records/20260916-022249-36773c7.md) | Bench drives a realistic source impedance and records the input disturbance directly (per `CLAUDE.md`'s "kickback is measured, not assumed"), methodology mirroring `gf180-sar-adc`'s [`sim/comparator-kickback/`](https://github.com/2AMLogic/gf180-sar-adc/tree/main/sim/comparator-kickback) experiment structure, at [`sim/comparator-kickback/`](sim/comparator-kickback/) against the real DR-0001 netlist — the disturbance couples through the input pair's own intrinsic C_gd (SG13G2 PSP103 models), not a stand-in. **Why this row was revised.** DRAFT said "≤ 5 mV into 1 kΩ"; measurement put the peak 18–29× over that **at every corner**. Peak volts at an assumed node capacitance is not a property of the comparator — it is Q_kick/C_in, a property of the *driver*: "≤ 5 mV at 1 kΩ/100 fF" is arithmetically the requirement C_in ≳ 2.9 pF, and DRAFT's own Basis already conceded the 1 kΩ was "a stated planning assumption, not yet tied to any specific driving stage." It is also not reachable by redesign — 5 mV at 100 fF means ≤ 0.5 fC/side, ~29× below measured, where a double-tail latch buys ~3–5× and only a static isolating buffer (rejected by DR-0001 on headroom) goes further. The ratified row therefore states the comparator's own property (charge, plus settled signal-dependent residue) and publishes the peak rather than hiding it; the equivalence V_peak ≈ Q_kick/C_in is ratified with it so any future driver converts the bound into its own volts. The rejected alternatives — hold 5 mV and re-open DR-0001, or keep "5 mV" and quietly restate the condition as C_in ≥ 3 pF — are in DR-0002 Row 4. |
| Supply / power | 1.2 V ±10% LV core (`sg13_lv_nmos`/`sg13_lv_pmos`), −40 … 125 °C. **Stated clock rate (ratified, closing DRAFT's TBD): 33.3 MHz** (30 ns period, 10 ns strobe). No Target-column average-power bound is ratified — see Basis | ≤ 20 µW average at 33.3 MHz, **including the tail-bias reference branch** | **Supply exercised; power Stretch NOT MET.** All four experiments completed 45/45 points at 1.08 / 1.20 / 1.32 V and −40 / 27 / 125 °C. Average power **22.9 µW** (`sf_-40c_1.08v`) … **29.5 µW** (`ff_125c_1.32v`) at 33.3 MHz = static 20.22 … 20.83 µA plus switching energy 31.2 … 61.3 fJ/decision. **~95 % of it is the static tail-bias branch** (`dut_ib` = 20 µA), which `sim/dut.json` records as a carried-over harness convention, not a sizing result; switching contributes only 1.0 … 2.0 µW. Record [`20260916-021945-36773c7`](sim/comparator-regeneration/records/20260916-021945-36773c7.md) | SG13G2 ships exactly two MOS voltage flavors — 1.2 V LV core and 3.3 V HV I/O, no 1.8 V flavor — confirmed against the SG13G2 process spec and `sg13g2_moslv_mod.lib`/`sg13g2_moshv_mod.lib` via [`sg13g2-bandgap`'s own DR-0002](https://github.com/2AMLogic/sg13g2-bandgap/blob/main/spec/decision-records/0002-supply-voltage-scope.md) (a different repo's record — "DR-0002" unqualified in this README means *this* repo's target-spec ratification). The 1.2 V LV core is the Target flavor per this repo's `CLAUDE.md` ("supply/power at 1.2 V core"); a 3.3 V HV I/O flavor is scoped in only if a future decision record ratifies it (see `spec/README.md`). The 33.3 MHz clock is ratified as the rate every committed transient record in this repo was taken at, not as an independent ambition. The ≤ 20 µW stretch is unchanged from the DRAFT table and is **not** relaxed to cover the measured 22.9–29.5 µW: the miss is a parameter nobody has optimized, and freezing `dut_ib` = 20 µA into the spec would ratify an arbitrary convention. DR-0002 deliberately ratifies **no** Target-column power bound — no gm/Id or bias-point sizing study exists to found one, and inventing a number would be exactly the unevidenced claim this DR process exists to prevent (DR-0002 Row 5, and its Open items). |

**Statistical basis, stated once for the table.** Whether SG13G2's LV device
models ship real per-instance local-mismatch terms (the "strong" statistical
story) or only global-process corners (requiring the documented
sensitivity-analysis fallback) is now **confirmed**: they DO ship real
per-instance local mismatch (Pelgrom-style `agauss()` terms in
`sg13g2_moslv_mod_mismatch.lib`, wired into `cornerMOSlv.lib`'s
`mos_{tt,ss,ff,sf,fs}_mismatch` corners), confirmed by an actual Monte Carlo
testbench, not just the PDK-model reading — see
[`sim/device-mismatch-confirm/`](sim/device-mismatch-confirm/) (issue #6).
Every statistical claim in this table (offset sigma above all) therefore
uses the **Monte Carlo** evidence path, per `CLAUDE.md`'s "Offset claims
state their statistical basis."

**Ratification status.** Ratified by
[`spec/decision-records/0002-target-spec-ratification.md`](spec/decision-records/0002-target-spec-ratification.md),
which sets every row above, changes one (Kickback), and closes two scope
questions (the power row's clock rate; a bounded τ for the metastability row).
Ratification is the **two-key** act described in
[2AMLogic/2am#372](https://github.com/2AMLogic/2am/issues/372) — an EE key and
a market key, neither held by the record's author — and the merge commit of
that record's PR is the ratification record. **DR-0002's own `Status:` line
reads `proposed` even in the merged tree, and that is expected, not stale**:
status is conferred by the two-key merge commit, so the content being merged
cannot already record its own outcome. DR-0001 merged the same way. See
DR-0002 § "How this record gets ratified" for the full note.
[`spec/README.md`](spec/README.md) documents when a further DR is required
(whenever this table is set, changed, or scoped again) and how to write one;
records are append-only, so a later change supersedes DR-0002 with a
higher-numbered record rather than editing it.

**What "ratified" does and does not mean here.** It means the bounds are
binding and a corner campaign can now be scored against them. It does **not**
mean the design meets them — the missed rows say so above — nor that the
measurements are complete: the noise row's compliance-path figure is itself
still a lower bound (the regenerative stage's own device noise is not yet
injected), the offset row's whole-latch MET verdict covers the differential
axis only (no whole-latch common-mode sweep exists yet), and the kickback
charge clause rests on a biased hand estimator until the bench emits Q_kick
directly. DR-0002's Open items name each of those gaps. Nothing here is
post-layout; no layout exists.

## License

Apache-2.0.

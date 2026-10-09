# Work log

Merged pull requests and closed issues from the preceding 30 days, recorded by Guide. These entries describe repository activity, not engineering verification.

### 2026-10-09

- **PR #109**: ab: validate both arm envelopes before certifying decisions unchanged
- **PR #108**: Preserve fixture, A/B and fleet-smoke inputs before submission
- **PR #104**: grade: reject ambiguous duplicate PVT results and population summaries
- **PR #103**: grade: reject non-finite numeric evidence before corner grading
- **PR #99**: spec: DR-0003 status-only evidence update for Rows 1, 4, 5 (#93)
- **PR #98**: sim: preserve campaign inputs on rebuild (#95)
- **PR #97**: layout: klt erc supply-spec stage and T1 item 11 citation (#38)
- **PR #94**: sim: internal-noise hook and whole-latch transient-noise record with regenerative-pair injection (#81)
- **PR #91**: sim: dut_ib bias-point sweep, a Pareto basis for a Row 5 power bound (#80)
- **PR #88**: sim: whole-latch offset across a bounded common-mode band (#79)
- **PR #87**: sim: known-charge validation of the Q_kick instrument (#78)
- **PR #83**: feat(sim): klt sim corner verification of every DR-0002 row; cite T1 item 5 (unmet: noise and Q_kick Targets fail)
- **PR #77**: ci: run stdlib-only sim harness unit tests as a third job
- **PR #76**: docs(sim): backend readiness and preflight before T1 grids (#74)
- **PR #73**: layout: klt pex extraction for T1 item 7; simulation leg blocked (#61)
- **PR #72**: layout: LVS of the comparator, cite match as T1 item 4 (#60)
- **Issue #100** (closed): Auditor guard telemetry: retain main-checkout stash protection
- **Issue #106** (closed): Require complete successful decision sets for the kickback A/B control
- **Issue #105** (closed): Preserve fixture, A/B and fleet-smoke inputs before submission
- **Issue #102** (closed): Reject ambiguous duplicate PVT results and population summaries
- **Issue #101** (closed): Reject non-finite numeric evidence before corner grading
- **Issue #96** (closed): Auditor guard telemetry: worktree-write-confinement
- **Issue #93** (closed): DR-0003: status-only update of Rows 1, 4, 5 now that #78/#79/#80 evidence has landed
- **Issue #95** (closed): Preserve campaign inputs when rebuilding existing klt sim evidence
- **Issue #38** (closed): Analog power-delivery (structural) evidence for T1 item 11 — klt erc supply run + supply-carrying LVS once layout exists
- **Issue #81** (closed): Complete whole-latch transient-noise injection into the regenerative pair (internal-node hook)
- **Issue #80** (closed): Bias-point sizing study to found a Target-column power bound for DR-0002 Row 5
- **Issue #86** (closed): Guard telemetry: resolve bounded worktree variables before denying writes
- **Issue #85** (closed): Guard telemetry: retain protection against literal @path raw-field bodies
- **Issue #79** (closed): Characterize whole-latch offset across a bounded common-mode band
- **Issue #78** (closed): Measure peak per-side kickback charge with source restoration included
- **Issue #75** (closed): CI: run the stdlib-only sim harness unit tests (no PDK needed) as a third tool-light job
- **Issue #74** (closed): Document sim backend readiness and preflight before submitting T1 grids (#61-#64 blocked on OSDI v0.4 / runner version)
- **Issue #62** (closed): Corner verification: mint klt sim corner-matrix envelopes for the DR-0002 spec rows and cite them (T1 item 5)
- **Issue #60** (closed): LVS: klt lvs of the comparator layout against design/comparator.spice, cite the match (T1 item 4)

### 2026-10-08

- **PR #70**: DRC: klt drc on the comparator layout, cite clean report (T1 item 3)
- **PR #67**: feat(layout): generate and commit the StrongARM comparator GDS (T1 item 2)
- **PR #66**: Install two-key (RATIFY-KEY) reviewer variants; document convention
- **Issue #59** (closed): DRC: klt drc on the comparator layout and cite the clean report (T1 item 3)
- **Issue #58** (closed): layout: draw and commit the StrongARM comparator GDS from design/comparator.spice (T1 item 2)
- **Issue #19** (closed): Install the two-key (RATIFY-KEY) ratification reviewer variants in this repo

### 2026-10-02

- **PR #56**: docs: state ratified design/spec status in the README preamble
- **Issue #21** (closed): README preamble still says "nothing is designed yet" above a ratified spec table

### 2026-10-01

- **PR #55**: fix: skip loom:needs-capability in the shared work-finder skip source
- **Issue #54** (closed): loom:needs-capability is documented as skipped by the work finder but is in neither skip source — #19 is rediscovered as the sole Priority-2 candidate every Curator pass
- **Issue #22** (closed): Certify the offset and noise rows: transient Monte-Carlo and transient-noise benches (DR-0001 Consequence 1)

### 2026-09-26

- **PR #53**: test: discover harness unit tests in sim/selftest.sh step 0
- **PR #52**: docs: correct post-DR-0002 stale claims in comparator-offset-transient-mc README
- **PR #50**: docs: correct six post-DR-0002 stale DRAFT/unratified claims
- **Issue #51** (closed): sim/selftest.sh hardcodes its three test modules instead of discovering them — reopens #41's no-gate coverage gap
- **Issue #49** (closed): sim/comparator-offset-transient-mc/README.md still asserts PR #18 is open / DR-0002 is not yet ratified
- **Issue #48** (closed): Post-DR-0002 sweep missed six files: stale "DRAFT/unratified" claims, an open-PR-#18 banner, and a broken README anchor

### 2026-09-23

- **PR #47**: chore: remove unwired npm placeholder scripts from package.json
- **PR #46**: docs: embed fleet burndown chart in README
- **Issue #45** (closed): Remove dead npm placeholder scripts from package.json: test/lint/check:ci/check:all are unwired no-ops
- **Issue #44** (closed): README: embed the fleet burndown chart (one line)
- **Issue #35** (closed): README.md's Offset sigma row states 10/45 PVT points over 15 mV, but the cited corrected-seed record shows 13/45

### 2026-09-21

- **PR #42**: test: run harness unit tests as step 0 of sim/selftest.sh
- **PR #40**: sim: whole-latch transient-noise bench (comparator-transient-noise)
- **PR #39**: feat: machine-grade the block's T1 state via a klt signoff block manifest
- **PR #18**: Ratify the target-spec table via DR-0002 on the schematic-DUT evidence
- **Issue #41** (closed): sim/harness/tests/: unit tests executed by no gate — wire into sim/selftest.sh (or remove)
- **Issue #37** (closed): Commit a klt signoff block manifest so this block's T1 state is graded, not hand-read
- **Issue #36** (closed): Reconcile DR-0002's Row 1 (Offset sigma) with PR #33's whole-latch offset evidence before merging PR #18
- **Issue #34** (closed): DR-0002's ratified Offset σ evidence cites the pre-#32 broken-seed comparator-offset-mc record
- **Issue #24** (closed): Transient-noise bench for the input-referred noise floor (DR-0001 Consequence 1, split from #22)
- **Issue #12** (closed): Ratify target-spec table via decision record (two-key mechanism) — porting-plan next step 3

### 2026-09-17

- **PR #33**: sim: whole-latch transient Monte-Carlo offset bench (comparator-offset-transient-mc)
- **Issue #23** (closed): Transient Monte-Carlo offset bench for the whole latch (DR-0001 Consequence 1, split from #22)

### 2026-09-16

- **PR #32**: fix: use setseed (not set rndseed=) for comparator-offset-mc's Monte-Carlo seed
- **PR #31**: Remove dead ToolchainDrift exception class
- **PR #29**: fix: recalibrate two placeholder-derived corner-sensitivity floors against DR-0001
- **PR #27**: refactor: remove dead Pdk.res_corner_lib property
- **PR #25**: fix: correct placeholder-era testbench notes to describe the bound schematic DUT
- **PR #17**: Implement DR-0001 comparator schematic and swap out the placeholder DUT
- **Issue #30** (closed): Remove dead ToolchainDrift exception class in sim/harness/toolchain.py
- **Issue #28** (closed): comparator-offset-mc's `set rndseed=` does not actually seed ngspice-46's mismatch draws (use `setseed`)
- **Issue #26** (closed): Remove dead Pdk.res_corner_lib property (zero callers)
- **Issue #20** (closed): Stale placeholder-era note blocks in three tb.json files are reproduced into schematic-DUT records
- **Issue #16** (closed): Recalibrate two placeholder-derived corner-sensitivity check floors against the real DR-0001 DUT
- **Issue #11** (closed): Implement comparator schematic (design/comparator.sch) and swap out the placeholder DUT — porting-plan next step 2

### 2026-09-15

- **PR #15**: chore: remove dead git_dirty()/pdk_available() wrapper functions
- **PR #13**: docs: add DR-0001 comparator topology decision (single-tail StrongARM, no preamp)
- **Issue #14** (closed): Remove dead git_dirty()/pdk_available() wrapper functions
- **Issue #10** (closed): Decision record: select comparator topology (StrongARM latch, preamp/no-preamp) — porting-plan next step 1

### 2026-09-10

- **PR #9**: sim: stand up the PVT harness + four comparator experiment directories
- **Issue #8** (closed): sim: stand up the PVT harness + four comparator experiment directories (offset-MC, preamp-noise, regeneration, kickback) with a loudly-labelled placeholder DUT — porting-plan next steps 3–4, ported from gf180-comparator#5

### 2026-09-09

- **PR #7**: feat: confirm SG13G2 LV MOS models carry per-instance local mismatch
- **Issue #6** (closed): Confirm & record: do SG13G2 LV MOS models carry per-instance local mismatch, or only global corners? (porting-plan next step 2)

### 2026-09-07

- **Issue #5** (closed): perm-test-delete-me

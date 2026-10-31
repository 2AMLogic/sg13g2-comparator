# Work log

Merged pull requests and closed issues from the preceding 30 days, recorded by Guide. These entries describe repository activity, not engineering verification.

### 2026-10-30

- **PR #353**: refactor(sim): reuse kcli._submit_with_retry in kickback and memory runners
- **PR #352**: sim(pex): record 3-unit extracted batch sample with td_c post-layout error
- **PR #350**: sim(pex): record failed 45-unit extracted regeneration batch job
- **PR #349**: refactor(scripts): share git()/resolve_tree() across evidence checkers
- **PR #348**: refactor(sim): share CM-band source-line rewrite across bench modules
- **PR #347**: sim(pex): record stalled 45-unit extracted regeneration batch job
- **PR #345**: sim(pex): size regeneration request timeout from measured unit runtime
- **PR #343**: docs(sim): record failed full regeneration PVT batch job and refused split
- **PR #342**: fix(sim): emit pex PVT supply as corners.params and record passing batch probe
- **Issue #351** (closed): Dedupe _submit_with_retry: remove two copies of kcli._submit_with_retry
- **Issue #346** (closed): Simplify: dedupe git()/resolve_tree() across three CI check scripts
- **Issue #344** (closed): Consolidate duplicated CM-band apply_transform across cmband, cmdecision, kickback_cmband

### 2026-10-27

- **PR #338**: build: pin klayout-tools to release 0.8.0 and accept release pins in the drift guard
- **Issue #337** (closed): Bump klayout-tools pin 3a75c3ae705b → 0.8.0
- **PR #212**: sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (#165)
- **PR #171**: sim: memory/hysteresis characterization bench (paired-history switching boundary over PVT) (Closes #159)
- **Issue #165** (closed): sim: kickback residue at dut_vcm -/+50 mV as klt sim corner campaigns (evidence for DR-0004 CM-range row)
- **Issue #159** (closed): Memory / hysteresis characterization bench: does the previous decision bias the next?
- **PR #218**: sim: max-step supplement workflow for aborted CM-band offset points (#89, partial: batch run failed)

### 2026-10-26

- **Issue #322** (closed): DR-0031 is stale after #318: evidence-size exception no longer in force
- **PR #199**: PEX diagnostic: extracted-device-only leg to separate device geometry from routing RC
- **Issue #191** (closed): PEX diagnostic: separate extracted device geometry from routing RC delay

### 2026-10-25

- **PR #265**: Validate timestep smoke evidence before computing noise convergence (#263)
- **Issue #263** (closed): Validate timestep smoke evidence before computing noise convergence
- **Issue #325** (closed): Remove scripts/diagnostics: completed #188 guard handoff package, unwired

### 2026-10-24

- **PR #324**: Retire per-PR evidence-size exceptions; count evidence bytes only
- **Issue #323** (closed): Squash the 27 evidence-size exception records into one superseding record; replace the cap with the artifact store

### 2026-10-23

- **PR #321**: Evidence manifests: artifact:<key> URIs, drop the bucket setting (klt 7e3561f+)
- **Issue #320** (closed): Evidence manifests: use artifact:<key> URIs and drop the bucket setting (klt 7e3561f+)
- **PR #319**: Store new sim evidence through the artifact store; commit manifests only (#318)
- **Issue #318** (closed): Write sim evidence through the fleet artifact store; commit manifests; restore the size ceiling against manifests
- **PR #303**: refactor: publish comparison and ibsweep reports through artifacts.publish
- **Issue #302** (closed): Consolidate remaining comparison/ibsweep report writers onto artifacts.publish (parallel drift with #237)
- **PR #270**: Validate CM decision timing dimensions and physical domains
- **Issue #266** (closed): Validate CM decision timing dimensions and physical domains
- **PR #268**: Reject invalid local PVT grid inputs before simulation
- **Issue #264** (closed): Reject invalid local PVT grid inputs before simulation
- **PR #248**: estimate: resolve reference offset/yield N from committed tree metadata (#247)
- **Issue #247** (closed): Derive evidence-size estimate denominators from selected reference campaigns
- **PR #238**: Validate clock-supply probes and reject ambiguous sample identities
- **Issue #235** (closed): Validate clock-supply probes and reject ambiguous sample identities

### 2026-10-22

- **PR #276**: Mirror gf180's supplemental reverse-polarity ladder fragment (#274)
- **Issue #274** (closed): Mirror gf180's supplemental reverse-polarity ladder fragment (bench-structure parity, gf180-comparator#158/#166)
- **Issue #297** (closed): Remove scripts/diagnostics/: completed #188 guard-handoff repro, unrelated to the comparator

### 2026-10-21

- **PR #317**: test: show captured git output when sparse-checkout sh() fails
- **Issue #316** (closed): test flake: test_append_only_and_size_job_from_sparse_clone fails on append-only sim evidence
- **PR #313**: ci: make sim evidence-size check report-only while suspended
- **Issue #312** (closed): Suspend the sim/ evidence-size ceiling (report-only) until the fleet S3 evidence store lands

### 2026-10-20

- **PR #249**: Validate Monte Carlo sample populations before compliance grading
- **Issue #245** (closed): Validate actual Monte Carlo populations before compliance grading
- **PR #281**: feat: read per-PR evidence-size exception files so open PRs stop conflicting
- **Issue #278** (closed): Every evidence PR rewrites the same total-ceiling line in sim/evidence-size-budget.json

### 2026-10-17

- **PR #296**: refactor: share cm-band undo_transform between cmband and cmdecision
- **Issue #295** (closed): Remove dead _spec_meas and dedupe cmband/cmdecision undo_transform
- **PR #292**: refactor: remove three zero-caller helpers from sim harness and kltsim
- **Issue #291** (closed): Remove four zero-caller helpers in sim/harness and sim/kltsim
- **PR #290**: refactor: share fleet-cap retry and local smoke runner across klt sim drivers
- **Issue #289** (closed): Consolidate duplicated klt-sim fleet-cap retry loop (4 copies) and local smoke runner (2 copies) across campaign drivers
- **Issue #286** (closed): Remove scripts/diagnostics: delivered #188 guard-repro handoff, unreferenced

### 2026-10-15

- **PR #243**: Preserve derived campaign report pairs before regeneration (#237)
- **Issue #237** (closed): Preserve derived campaign report pairs before regeneration

### 2026-10-12

- **PR #273**: Reject mixed-geometry sizing finalists in candidate Target summaries
- **Issue #269** (closed): Reject mixed-geometry sizing finalists in candidate Target summaries
- **PR #271**: Validate bias mirror/headroom screening probes before aggregation
- **Issue #267** (closed): Validate bias mirror headroom screening probes before aggregation
- **Issue #260** (closed): Auditor process proposal: run final evidence-size preflight before requesting review

- **PR #259**: yield: re-derive the index in the engine-free consistency check
- **PR #258**: ci: run KLayout implant geometry regression in layout-reproducibility (#257)
- **PR #256**: cmband: empty reproduction is INCOMPLETE; count rejected draws per record
- **PR #254**: PDK DRC: reject incomplete deck runs before reporting clean (#253)
- **PR #251**: Validate CM-offset draw identities, probes, pairing and reproduction completeness (#250)
- **PR #246**: README claims guard: verify noise compliance verdicts (#242)
- **Issue #257** (closed): Run implant geometry regression tests in the KLayout-equipped CI job
- **Issue #255** (closed): Recompute yield index statistics during engine-free consistency checks
- **Issue #253** (closed): PDK DRC: reject incomplete deck runs before reporting clean
- **Issue #252** (closed): cmband.reproduction(): empty comparison yields vacuous REPRODUCED verdict
- **Issue #250** (closed): Validate common-mode offset draw identities, probes and reproduction completeness
- **Issue #242** (closed): Verify public noise compliance verdict statements
- **PR #241**: PEX timing compliance: require matching valid decision states
- **Issue #240** (closed): PEX timing compliance: require matching valid decision states

### 2026-10-11

- **PR #239**: noise_full: validate provenance per tn_full_* config before arithmetic (#236)
- **PR #234**: check_readme_claims: pin README kickback residue claims to the historical harness record
- **PR #233**: docs: require evidence size check on final HEAD before review (#223)
- **PR #231**: README evidence: verify common-mode offset characterization counts and ranges
- **PR #230**: CI: verify source schematics regenerate the committed comparator netlist
- **PR #229**: Supplemental DRC: count report items and reject malformed marker evidence
- **PR #227**: fix: validate the complete physical PVT grid in README evidence loaders
- **Issue #236** (closed): Bind full-noise analysis to verified configuration and submission provenance
- **Issue #232** (closed): README evidence: pin kickback residue claims to their historical measurement population
- **Issue #223** (closed): Builder preflight: check tracked sim size before requesting review
- **Issue #228** (closed): README evidence: verify common-mode offset characterization counts and ranges
- **Issue #224** (closed): CI: verify source schematics regenerate the committed comparator netlist
- **Issue #220** (closed): Supplemental DRC: count report items and reject malformed marker evidence
- **Issue #217** (closed): README evidence loaders: validate the complete physical PVT identity set

### 2026-10-11

- **PR #225**: Reject incomplete reproduction and non-finite CM probes in decision-band validation
- **PR #222**: ci: fail closed when sparse checkout omits ruff lint inputs
- **PR #221**: Preflight CM-band run submissions and report failed parts
- **PR #219**: pex: require distinct physical corners and valid delay evidence
- **PR #215**: docs: reconcile harness-unit-tests sparse row in sim/README.md with ci.yml (#187)
- **PR #214**: Layout: repair PDK-deck DRC findings pSD.b and pSD.i (#184)
- **Issue #209** (closed): Reject incomplete reproduction and non-finite CM probes in decision-band validation
- **Issue #216** (closed): CI: fail when sparse checkout omits intended Ruff input files
- **Issue #194** (closed): CM-band offset runner: preflight existing envelopes and report failed parts
- **Issue #211** (closed): PEX renderer: require distinct physical corners and valid delay evidence
- **Issue #210** (closed): Guard telemetry: retain detached reset protection unless disposal is proven
- **Issue #187** (closed): Docs: sim/README.md sparse-cone table omits harness-unit-tests' new pdk_drc inputs
- **Issue #184** (closed): Layout: repair PDK-deck DRC findings pSD.b (x10) and pSD.i (x52)

- **Issue #177** (closed): Reject ambiguous repeated ngspice output in the local PVT harness
- **Issue #178** (closed): Validate local testbench check bounds before simulation
- **Issue #180** (closed): Layout: verify physical rules outside the curated DRC deck
- **Issue #181** (closed): PEX reporting: distinguish raw measurement success from circuit compliance
- **Issue #179** (closed): Freeze local PVT source inputs before executing the grid
- **Issue #186** (closed): Unit tests for the CM-band campaign runner (retry, resubmit and append-only guards)
- **Issue #192** (closed): Noise analysis: retain shared-draw disclosures and bound grid-mean uncertainty
- **Issue #197** (closed): Preserve partial ngspice diagnostics when local PVT points time out
- **Issue #196** (closed): Record compiled OSDI model identity in local PVT evidence
- **Issue #193** (closed): README claims: verify offset and full-noise figures against their own evidence populations
- **Issue #188** (closed): Guard telemetry: package alternate-index wrapper reproduction for upstream handoff
- **Issue #203** (closed): Record runtime SPICE model-source identity in local PVT evidence
- **Issue #173** (closed): Clock-edge, strobe-width and supply-disturbance sensitivity characterization of the whole latch
- **Issue #164** (closed): sim: decision time / metastability at dut_vcm -/+50 mV as klt sim corner campaigns (evidence for DR-0004 CM-range row)
- **PR #183**: Reject ambiguous repeated ngspice output in the local PVT harness
- **PR #182**: Validate local testbench check bounds before simulation
- **PR #185**: layout: supplemental DRC against IHP's own deck (#180)
- **PR #189**: PEX delta table: separate measurement availability from compliance (#181)
- **PR #190**: harness: freeze local PVT source inputs before executing the grid (Closes #179)
- **PR #195**: test: unit tests for CM-band campaign runner retry and append-only guards
- **PR #198**: Noise analysis: retain shared-draw disclosures and bound grid-mean uncertainty
- **PR #201**: runner: preserve partial ngspice diagnostics on local PVT timeout
- **PR #202**: Record compiled OSDI model identity in local PVT evidence (#196)
- **PR #204**: README claims: verify offset and full-noise figures against their own evidence populations
- **PR #205**: feat(diagnostics): alternate-index wrapper guard reproduction for upstream handoff
- **PR #206**: harness: record runtime SPICE model-source identity in PVT evidence (#203)
- **PR #207**: sim: clock-edge, strobe-width and supply-disturbance sensitivity characterization (#173)
- **PR #208**: sim: decision time / metastability at dut_vcm -/+50 mV as klt sim campaigns (#164)

### 2026-10-10

- **Issue #174** (closed): CI guard: README spec-table figures must match the committed characterization report
- **Issue #82** (closed): Offset 3σ: klt sim per-draw campaign reads 13 % above the whole-latch record (systematic, cause unknown)
- **PR #175**: ci: guard README spec-table figures against the characterization report
- **PR #176**: analysis: klt-vs-record offset shift is 1.3 sigma once CRN is accounted for (#82)

### 2026-10-10

- **PR #170**: T1 statistical signoff: N=200 offset populations at every PVT point (Closes #167)
- **PR #169**: ci: pinned ruff F-rule static check (Closes #157)
- **Issue #167** (closed): T1 statistical signoff: larger offset populations at every PVT point
- **Issue #157** (closed): CI: pinned pyflakes-class static check over harness, kltsim and guard scripts

- **PR #158**: test: unit tests for harness PDK resolution and toolchain-pin drift
- **PR #163**: klt yield evidence for the statistical DR-0002 rows; cite T1 item 6 (unmet, undersized_sample)
- **PR #162**: Protect aggregated characterization reports from in-place replacement
- **PR #161**: signoff parity: preserve JSON container structure
- **PR #154**: grade: validate supply/temperature probe units (Closes #152)
- **PR #153**: grade: reject repeated or malformed measurement names within a corner
- **PR #148**: pex: full PVT klt pex on batch; runner klt 0.5.0 vs client 0.7.0 blocks every corner (Part of #61)
- **PR #147**: tests: unit tests for signoff parity, ERC tool, netlist generator
- **PR #146**: Cite artifact-anchored evidence for T1 items 1, 2, 9, 10; bump klt pin (#65)
- **PR #145**: Capture verified Git provenance before PVT simulation
- **PR #144**: pex: second batch re-probe, still no capacity (Part of #61)
- **Issue #156** (closed): Unit tests for harness PDK resolution and toolchain-pin drift checks
- **Issue #63** (closed): Monte Carlo: mint a klt yield report for the statistical spec rows (offset sigma) and cite it (T1 item 6)
- **Issue #155** (closed): Protect aggregated characterization reports from in-place replacement
- **Issue #149** (closed): Make signoff parity preserve JSON container structure
- **Issue #151** (closed): Guard telemetry: retain stash create redirect confinement
- **Issue #152** (closed): Validate supply and temperature probe units before accepting PVT evidence
- **Issue #150** (closed): Reject repeated measurement names within corner evidence
- **Issue #117** (closed): Unit tests for the CI-gating scripts: signoff parity, ERC judge, netlist generator
- **Issue #141** (closed): Guard decision review: ask:(^|[;&|(`[:space:]])git checkout \.
- **Issue #65** (closed): Cite artifact-anchored evidence for T1 items 1, 9 and 10 (design sources, testbenches, repo hygiene)
- **Issue #142** (closed): Capture verified Git provenance before PVT simulation

### 2026-10-10

- **PR #140**: feat(sim): T1 item 8 aggregated characterization report (schematic)
- **PR #139**: ci: bound tracked sim evidence growth and use verified sparse checkouts
- **PR #138**: ci: single source of truth and drift guard for pinned klt/KLayout build
- **PR #137**: ci: pin GitHub Actions by commit SHA (Closes #136)
- **Issue #64** (closed): Characterization: one aggregated per-spec-row report with a generic envelope (T1 item 8)
- **Issue #132** (closed): Bound tracked sim evidence growth and use verified sparse CI checkouts
- **Issue #135** (closed): CI: single source of truth and drift guard for the pinned klt/KLayout build
- **Issue #136** (closed): CI: pin third-party GitHub Actions by commit SHA, matching the klt pin policy
- **PR #133**: CI guard: enforce append-only sim evidence
- **PR #131**: pex: record 2026-10-10 batch re-probe; PVT/MC rows still not run (Part of #61)
- **PR #130**: CI: preserve started verification runs when newer commits arrive
- **PR #128**: docs: reconcile README Row 2 noise with issue #81 complete-injection campaign
- **Issue #129** (closed): CI: preserve started verification runs when newer commits arrive
- **Issue #127** (closed): Guard telemetry: retain unresolved campaign cleanup protection
- **Issue #126** (closed): Reconcile public Row 2 noise summary with the completed internal-injection campaign
- **Issue #116** (closed): CI guard: enforce append-only sim evidence (records, campaigns, corners)

### 2026-10-09

- **PR #125**: ci: check post-layout klt pex inputs are fresh against their sources
- **PR #124**: Validate sizing-screen evidence before selecting comparator finalists
- **PR #121**: sim: joint input-pair sizing study for Rows 4a and 2 (Part of #92)
- **Issue #123** (closed): CI: verify generated post-layout simulation inputs match their sources
- **Issue #122** (closed): Validate sizing-screen evidence before selecting comparator finalists
- **PR #119**: pex: record batch re-probe of PVT grid (Part of #61)
- **PR #118**: Verify saved request and invocation provenance when grading campaigns
- **PR #115**: harness: reserve unique PVT run identities before writing evidence (#110)
- **PR #114**: harness: reject non-finite measurements and invalid summaries
- **PR #113**: Post-layout klt pex: single-corner extracted run, item 7 cited (#61)
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
- **Issue #107** (closed): Verify saved request and invocation provenance when grading campaigns
- **Issue #110** (closed): Reserve unique PVT harness run identities before writing evidence
- **Issue #111** (closed): Reject overflowed measurements and invalid summaries in the PVT harness
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

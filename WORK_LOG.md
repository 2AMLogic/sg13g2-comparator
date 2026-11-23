# Work log

Merged pull requests and closed issues from the preceding 30 days, recorded by Guide. These entries describe repository activity, not engineering verification.

## Archives

- [2026-09](work_log/WORK_LOG_2026-09.md)

### 2026-11-23

- **PR #534**: fix: exclude null-valued pairs from values_compared in cmdecision and kickback reproduction checks
- **PR #520**: refactor: route kickback CM-band comparisons through artifacts.publish
- **Issue #532** (closed): Sibling values_compared paths still count null-vs-null pairs as compared values (kickback, cmdecision)
- **Issue #519** (closed): Route kickback CM-band comparison writers through artifacts.publish

### 2026-11-22

- **PR #530**: fix: count only measured pairs as compared values in the memory determinism repeat
- **PR #531**: fix: drop kickback_cmband's duplicate non-directory preflight
- **PR #528**: fix: publish supplement-report pair append-only
- **PR #526**: fix: preflight non-directory destination dirs in artifacts commit/check
- **PR #524**: fix: kickback commit_inputs refuses non-directory destination dirs
- **PR #522**: chore: ignore daemon-owned .loom/account-ranking.* dispatch state
- **PR #517**: refactor: route CM-band campaign input writers through build.commit_inputs append-only
- **PR #514**: refactor: route kickback CM-band input writers through artifacts.commit
- **PR #500**: refactor: drive netlist regeneration through pinned klt netlist, not raw xschem
- **PR #499**: fix: report insufficient evidence for empty determinism-repeat rounds
- **Issue #525** (closed): Determinism repeat counts null-vs-null measurement pairs as compared values
- **Issue #527** (closed): kickback_cmband._non_directory_ancestors is now redundant with the artifacts preflight
- **Issue #523** (closed): build.commit_inputs: campaign dir existing as a regular file raises a bare FileExistsError, not BuildError
- **Issue #521** (closed): gitignore: daemon-owned .loom/account-ranking.* trips check-main-clean for every builder
- **Issue #518** (closed): Route cmd_supplement_report's derived report pair through artifacts.publish
- **Issue #516** (closed): Route remaining CM-band input writers in cmband and cmdecision through build.commit_inputs
- **Issue #515** (closed): kickback_cmband.commit_inputs: out_dir existing as a regular file raises a bare FileExistsError, not KickbackCmBandError
- **Issue #513** (closed): Replace duplicated append-only input writers in kickback_cmband with artifacts.commit
- **Issue #495** (closed): Remove the empty-measurement fallback from the memory determinism repeat
- **Issue #489** (closed): Replace raw xschem call in design/netlist.py with klt netlist
- **PR #509**: refactor: source the transient-noise injected density from one constant
- **Issue #506** (closed): Source the 36.27 nV/√Hz bench injection from one place instead of per-module literals
- **PR #510**: fix: hash supplement envelopes from the bytes used to parse them
- **Issue #508** (closed): Hash offset supplement envelopes from the bytes used to parse them

### 2026-11-21

- **PR #501**: sim: measure matched PMOS load widths for Row 2 density and bench noise
- **Issue #498** (closed): Measure how matched PMOS load widths change input-referred density and Row 2 noise
- **PR #505**: fix: repair dangling issue-92-bias MC manifest link in corner-verification README
- **Issue #502** (closed): Broken relative link to the issue-92-bias MC manifest in sim/klt-corner-verification/README.md
- **PR #494**: docs: measure per-corner front-end density and complete the Row 2 factor split
- **PR #491**: sim: replace the unusable manual dpkg-deb recipe in build-osdi.sh with install-and-rerun
- **Issue #477** (closed): Row 2 noise: split the front-end term (density vs decision bandwidth), then a bounded three-candidate design study and a drafting-only decision record
- **Issue #488** (closed): Remove the unusable manual dpkg-deb fallback from the OSDI build diagnostic
- **PR #485**: signoff: declare item 5 spec_rows and cite per-row envelopes with gaps for ungradeable rows
- **Issue #478** (closed): Item 5: declare the DR-0002 row set under spec_rows and cite each row's envelope, replacing the single-envelope citation

### 2026-11-20

- **PR #486**: docs: characterize Row 2 decision bandwidth and prepare candidate noise measurements
- **PR #484**: fix: write sizesweep JSON and Markdown as one preflighted append-only pair
- **Issue #483** (closed): Remove the per-file sizesweep writer and preflight the report pair

### 2026-11-18

- **PR #473**: ci: report the append-only sim evidence gate on merge_group commits (merge queue readiness)

### 2026-11-17

- **PR #464**: chore(loom): resync installed Loom to v0.19.1306

### 2026-11-16

- **PR #459**: chore(loom): resync installed Loom to v0.19.1302

### 2026-11-15

- **PR #455**: fix: report Row 5a in the sizesweep finalist roll-up
- **PR #456**: refactor: share one chain-loading loop between the declared-contract loaders
- **PR #454**: fix(sim): make_delta_table reads the derived extract shape (rows[]) beside klt's delta[]
- **PR #450**: chore: remove dead repo-root package.json stub
- **PR #448**: ibsweep: grade swept-bias campaigns against the declared BIAS_PROBES superset
- **Issue #447** (closed): sizesweep finalist roll-up cannot report Row 5a, hiding a PASS->INCOMPLETE regression
- **Issue #452** (closed): No guard keeps the three copies of grade.load_campaign's chain-loading loop in sync (grade / declared_n / bias_probes)
- **Issue #445** (closed): make_delta_table.py cannot read the batch envelope shape (rows[] vs delta[]), the last gap before a 45-corner grid table renders
- **Issue #428** (closed): Remove the repo-root package.json stub: its last script invokes a Loom script deleted in v0.19.1244
- **Issue #440** (closed): --check regeneration drift: six committed report pairs no longer reproduce byte-identically on main
- **PR #449**: pin: move klayout-tools 0.9.1 -> 0.9.2, re-freeze layout evidence
- **Issue #438** (closed): Decide whether to chase the klayout-tools 0.9.2 pin (0.9.1 landed in #430 as the measured candidate)
- **PR #433**: refactor: route the kickback driver's smoke and probe submits through kcli
- **PR #443**: sim: probe the Row 4b band-edge kickback rejects with a forced DC operating point
- **PR #446**: sim: close the #92 bias/latch study -- Rows 3c/4a recoverable, Row 2 unclosed at 1.096 mV
- **PR #441**: refactor: factor the --report-dir citation preamble into one resolve_report_dir helper
- **PR #442**: refactor(sim): share the memory bench's round probe-index rule in round_mult
- **PR #444**: fix: canonicalise klt's params-supply corner ids in make_delta_table
- **PR #437**: refactor: wire REPEAT_POINT into its seven re-spelled readers, byte-identical
- **PR #434**: refactor(layout/tests): single-source the klayout stand-in module loader
- **PR #430**: build: move the klt pin from 0.8.0 to PyPI release 0.9.1
- **PR #436**: ci: drop four dead sparse-checkout patterns, add cone minimality guard
- **PR #439**: docs: state item 7 post-layout evidence as of 2026-11-14
- **Issue #431** (closed): Adopt the shared klt-sim smoke runner and retry wrapper in run_kickback_cm_band.py: two copies the Oct-17 sharing refactor missed
- **Issue #415** (closed): Probe the two Row 4b band-edge kickback rejects with a forced DC operating point
- **Issue #92** (closed): Joint input-pair sizing study to close the failing Target rows (Row 4 Q_kick, Row 2 noise)
- **Issue #423** (closed): Factor the --report-dir citation preamble into one helper beside _cite_note
- **Issue #422** (closed): Share the round probe-index rule in sim/kltsim/memory.py: one expression written six times
- **Issue #424** (closed): make_delta_table.py cannot canonicalise the corner ids klt emits for a corners.params supply axis, so every delay row reads ungraded
- **Issue #426** (closed): Decide `REPEAT_POINT` in sim/run_memory.py: wire into cmd_repeat, or drop
- **Issue #432** (closed): Dedupe the klayout stand-in module loader duplicated across layout/tests/test_erc_tool.py and test_pdk_drc.py
- **Issue #416** (closed): Bump the klayout-tools pin from 0.8.0 to the release the batch runner accepts
- **Issue #429** (closed): Remove five redundant CI sparse-checkout patterns, and guard cone minimality
- **Issue #418** (closed): Update the item 7 narrative in manifests/README.md to the current post-layout evidence

### 2026-11-14

- **PR #425**: feat(pex): measure the three ss / 125 C extracted regeneration corners
- **PR #427**: refactor: call build.py's sha256 helpers instead of module-local copies
- **PR #421**: refactor: delete eight unreferenced module-level definitions
- **PR #414**: docs: roadmap as of 2026-11-13
- **Issue #417** (closed): Measure the three unmeasured extracted regeneration corners (ss / 125 C)
- **Issue #420** (closed): Remove seven unreferenced module-level constants (none is a hashed report input)
- **Issue #419** (closed): Consolidate the triplicated sha256 helpers in sim/kltsim onto build.py

### 2026-11-10

- **PR #411**: chore: remove one-off scripts/diagnostics reproduction package
- **Issue #336** (closed): Remove scripts/diagnostics: completed #188 upstream-handoff package (~506 LOC)

### 2026-11-08

- **PR #407**: sim: probe the two Row 4b band-edge kickback rejects as a labelled supplement
- **Issue #405** (closed): Probe the two Row 4b band-edge kickback rejects (DR-0004 gate)

### 2026-11-05

- **PR #403**: sim: complete max-step supplement with vcm-p050 populations 60/60
- **PR #402**: sim: record partial max-step supplement re-run (4 of 6 populations 60/60)
- **Issue #89** (closed): sim: complete the two vcm-m050 CM-band offset points that abort (timestep too small) with a uniform tighter max step

### 2026-11-03

- **PR #400**: sim(pex): record failed extracted offset MC at tt/-40C/1.32V, extracted side lost
- **PR #399**: sim(pex): record extracted whole-latch offset MC, 48 of 60 samples at tt/125C/1.32V via batch
- **PR #398**: sim(pex): record extracted offset MC at tt/125C/1.08V, 57 of 60 samples via batch
- **PR #397**: sim(pex): record extracted offset MC at tt/-40C/1.08V, 57 of 60 samples via batch
- **PR #396**: sim(pex): record extracted offset MC at sf/-40C/1.20V, 57 of 60 samples via batch
- **PR #395**: sim(pex): record extracted offset MC at sf/125C/1.20V, 57 of 60 samples via batch
- **PR #394**: sim(pex): record extracted offset MC, 60 of 60 samples at fs/-40C/1.20V via batch

### 2026-11-02

- **PR #392**: sim(pex): record extracted offset MC at fs/125C/1.20V, 60 of 60 samples via batch

### 2026-11-01

- **PR #389**: sim(pex): record extracted whole-latch noise MC, 80 of 80 trials at ff/27C/1.32V via batch
- **PR #388**: sim(pex): record extracted whole-latch offset MC at ff/27C/1.32V (60/60) via batch
- **PR #387**: sim(pex): extracted whole-latch MC at ss/27C/1.08V (offset 60/60, noise 76/80) via batch
- **PR #386**: sim(pex): add per-point roll-up of recorded extracted Monte Carlo results
- **PR #385**: sim(pex): record extracted whole-latch noise MC at ss/-40C/1.08V, 80 of 80 trials via batch
- **PR #384**: sim(pex): record extracted whole-latch offset MC, 60 of 60 samples at ss/-40C/1.08V via batch
- **PR #383**: sim(pex): record extracted whole-latch noise MC at ff/125C/1.32V, 77 of 80 trials
- **PR #382**: sim(pex): record extracted offset MC at ff/125C/1.32V, 45 of 60 samples via batch
- **PR #380**: sim(pex): record extracted whole-latch noise MC at tt/-40C/1.20V, 80 of 80 trials via batch
- **PR #379**: sim(pex): record extracted whole-latch offset MC at tt/-40C/1.20V, 60 of 60 samples
- **PR #378**: sim(pex): record extracted whole-latch noise MC at tt/125C/1.20V, 77 of 80 trials via batch
- **PR #376**: sim(pex): record extracted whole-latch offset MC at tt/125C/1.20V, 60 of 60 samples via batch
- **PR #375**: sim(pex): record extracted whole-latch noise MC, 78 of 80 trials at tt/27C/1.08V
- **PR #374**: sim(pex): record extracted whole-latch offset MC at tt/27C/1.08V, 57 of 60 samples via batch
- **PR #372**: sim(pex): record extracted whole-latch noise MC at tt/27C/1.32V, 77 of 80 trials (Part of #61)

### 2026-10-31

- **PR #371**: sim(pex): record extracted whole-latch offset MC, N=60 at tt/27C/1.32V via sharded batch
- **PR #370**: sim(pex): record extracted whole-latch transient-noise MC at fs/27C/1.20V, 77 of 80 trials (Part of #61)
- **PR #369**: sim(pex): record extracted whole-latch offset MC at fs/27C/1.20V, 57 of 60 compared (Part of #61)
- **PR #368**: sim(pex): record extracted whole-latch transient-noise MC, N=80 at sf/27C/1.20V
- **PR #367**: sim(pex): record extracted whole-latch offset MC, N=60 at sf/27C/1.20V via sharded batch
- **PR #366**: sim(pex): record failed extracted offset MC attempt at sf/27C/1.20V (extracted side lost)
- **PR #365**: sim(pex): record extracted whole-latch noise MC, N=80 at ff/-40C/1.32V via sharded batch
- **PR #364**: sim(pex): record extracted offset MC at ff/-40C/1.32V, 57 of 60 samples (Part of #61)
- **PR #363**: sim(pex): record extracted whole-latch transient-noise MC, N=80 at ss/125C/1.08V via sharded batch
- **PR #362**: sim(pex): record extracted whole-latch offset MC, N=60 at ss/125C/1.08V via sharded batch
- **PR #361**: sim(pex): record extracted whole-latch transient-noise MC, N=80 at tt/27C/1.20V via batch
- **PR #360**: refactor(sim): reuse cmband's CM-band Condition grid in kickback_cmband
- **PR #359**: sim(pex): record extracted whole-latch offset MC at nominal point, N=60 via batch
- **PR #358**: sim(pex): express whole-latch MC requests and probe them on the batch fleet
- **PR #357**: sim(pex): record extracted 45-corner kickback grid via sharded batch
- **PR #355**: sim(pex): record sharded 45-corner extracted regeneration grid, 42 of 45 corners
- **Issue #356** (closed): Remove duplicated CM-band Condition table from kickback_cmband: reuse cmband's

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

# `sim/`

xschem + ngspice testbenches and **append-only** results, on the SG13G2
1.2 V LV core rail.

Six experiments backing the four first-class rows of
[`README.md`'s target specification](../README.md#target-specification-ratified--dr-0002)
(the offset-σ *and* noise rows each have two, deliberately — see below):

| experiment | row it backs | method |
|---|---|---|
| [`comparator-offset-mc/`](comparator-offset-mc/) | Offset σ (**lower bound**, front end only) | Monte Carlo on SG13G2's `mos_*_mismatch` per-instance local-mismatch models, `dc` sweep against the loop-broken `comparator_dut_analog` reduced sub-model |
| [`comparator-offset-transient-mc/`](comparator-offset-transient-mc/) | Offset σ (**whole latch**, strobe → decision) | Monte Carlo on the same `mos_*_mismatch` models, transient digital-staircase sweep against the un-reduced `comparator_dut` topology |
| [`comparator-preamp-noise/`](comparator-preamp-noise/) | Input-referred noise (**reportable lower bound**, front end only) | `.noise`, total integrated output noise ÷ measured DC gain, against the loop-broken `comparator_dut_analog` reduced sub-model |
| [`comparator-transient-noise/`](comparator-transient-noise/) | Input-referred noise (**compliance path**, whole latch) | `TRNOISE`-injected transient decision statistics against the un-reduced `comparator_dut`, converted to σ by probit inversion |
| [`comparator-regeneration/`](comparator-regeneration/) | Decision time vs. overdrive, **metastability** | transient overdrive ladder, τ extracted from it |
| [`comparator-kickback/`](comparator-kickback/) | **Kickback** | 1 kΩ source impedance *and* a floating high-Z input |

`comparator_dut` has no DC-resolvable operating point (DR-0001 Decision §3),
so the reduced sub-model was DR-0001's own named interim path for the offset
and noise rows (Consequence 2) rather than a design choice made from
scratch. In both pairs the reduced-sub-model bench stays committed alongside
the whole-latch one — see
[`comparator-offset-transient-mc/README.md`](comparator-offset-transient-mc/README.md#relationship-to-comparator-offset-mc)
(offset) and
[`comparator-transient-noise/README.md`](comparator-transient-noise/README.md#retain-not-retire-comparator_dut_analog)
(noise) for why retiring it was considered and rejected on each row's own
evidence.

The two noise benches are **not** peers: `CLAUDE.md` requires the noise floor
to come "from transient-noise runs with seeds and run counts committed", and
[DR-0002](../spec/decision-records/0002-target-spec-ratification.md)
([#12](https://github.com/2AMLogic/sg13g2-comparator/issues/12) /
[PR #18](https://github.com/2AMLogic/sg13g2-comparator/pull/18)) names
transient noise as that row's compliance evidence path and the `.noise`
number as a *reportable lower bound*.
`comparator-transient-noise/` is therefore the row's compliance measurement;
`comparator-preamp-noise/` is the lower bound it is calibrated against.

Metastability and kickback are first-class rows here, not appendices, per
[`CLAUDE.md`](../CLAUDE.md).

**`klt sim` corner verification (T1 item 5, issue #62).**
[`klt-corner-verification/`](klt-corner-verification/) re-measures every
DR-0002 row against the same schematic DUT as `klt sim` corner-matrix
envelopes over the full 45-point grid. It runs on the batch fleet, and
`sim/kltsim/grade.py` grades it literally against DR-0002. It is a separate
evidence trail in `klt`'s own envelope format: it does not relabel or replace
the six experiments above, whose records stay as they are. It also adds two
measurements those benches never made: a direct Q_kick (DR-0002 Row 4's open
item, validated against a known-charge fixture) and a full-cycle average
power. See its README for the verdicts and how
they differ from DR-0002's. The same directory holds the issue #80 `dut_ib` bias-point sweep
(campaign `20261009-issue80`): a Pareto table of decision time, tau, offset,
noise and power against bias, the basis for a later Row 5 power bound. It
proposes no bound.

**Whole-latch offset across a common-mode band (issue #79).**
[`comparator-offset-cm-band/`](comparator-offset-cm-band/) runs the whole-latch
offset staircase at `dut_vcm` − 50 mV, `dut_vcm` and `dut_vcm` + 50 mV as three
paired `klt sim` campaigns on the batch fleet (same seeds, same draws per
point). It is **characterization**: DR-0002 ratifies the offset row at
`dut_vcm` only and no whole-latch common-mode range, so nothing there is a
compliance verdict.

Plus one supporting confirmation, not a spec-row bench:

```
sim/device-mismatch-confirm/
                          issue #6: confirms SG13G2's LV MOS models carry
                          per-instance local mismatch (Monte Carlo evidence,
                          not just a PDK-model reading) -- see its own
                          README.md for the finding and methodology. This is
                          what makes the Monte Carlo evidence path (rather
                          than the sensitivity-analysis fallback) the right
                          one for comparator-offset-mc above.
```

> **Current status: the device under test is the DR-0001 schematic, and the
> spec table it is scored against is ratified by
> [DR-0002](../spec/decision-records/0002-target-spec-ratification.md).**
> Ratified is not met — DR-0002 records the rows the current design misses:
> the noise row at Target on the whole-latch compliance path, the decision-time
> stretch at the `ss` points, and the power stretch; the offset row's Target
> is met on the whole-latch measurement with its Stretch missed at 27/45
> points. DR-0002 also names the residual evidence gaps rather than hiding
> them: the noise compliance figure is itself still a lower bound (the
> regeneration stage's own noise is not yet injected), and the offset
> whole-latch number covers the differential axis only. `sim/dut.json` binds
> [`design/comparator.spice`](../design/comparator.spice) (`provenance:
> schematic`), regenerated from the xschem sources in
> [`design/`](../design/) per
> [`spec/decision-records/0001-comparator-topology.md`](../spec/decision-records/0001-comparator-topology.md):
> a single-tail StrongARM dynamic latch on `sg13_lv_nmos`/`sg13_lv_pmos`.
> Records made against it are no longer placeholder-banner'd, and they are
> the evidence DR-0002 rests on: the `20260916-*` re-founded and drafted-era
> records (`spec/porting-plan.md`'s third step in this chain, now taken), plus
> the whole-latch `20260917-*` / `20260921-*` records the two PRs after
> (#23 / PR #33 and #24 / PR #40) committed — folded into DR-0002's Rows 1–2
> by issue
> [#36](https://github.com/2AMLogic/sg13g2-comparator/issues/36) ahead of its
> two-key review. Their own
> Claim text still says they are "NOT evidence toward
> `README.md#target-specification`" — correct when written, superseded by
> DR-0002; `sim/` is append-only, so that text stays as-is rather than being
> rewritten. Earlier `provenance: placeholder` records made against
> [`sim/dut/placeholder_comparator.spice`](dut/) remain committed
> (append-only) and still carry their own banner. See
> [`sim/dut/README.md`](dut/README.md) for the full binding history and the
> `comparator_dut_analog` reduced-sub-model caveat.

## Cold start

Everything is stdlib Python plus ngspice; there is no virtualenv to create.

```bash
# 1. Install the pinned PDK (see sim/pdk.json for the exact release tag +
#    tarball sha256), e.g. via klayout-tools' scripts/fetch-ihp-sg13g2.sh,
#    laid out open_pdks-style as PDK_ROOT/ihp-sg13g2:
export PDK_ROOT=/path/to/pdk-root
export PDK=ihp-sg13g2

# 2. Install ngspice 46 or newer, built with OSDI support (Debian/Ubuntu:
#    apt-get install ngspice).

# 3. Build the OSDI device models (PSP103 MOS, r3_cmc resistors) IHP-Open-PDK
#    ships as Verilog-A source, not prebuilt binaries -- a one-time step per
#    PDK install, checksum-pinned OpenVAF-Reloaded compiler, no third-party
#    .osdi binary ever downloaded (sim/harness/README.md "OSDI preflight"):
sim/tools/build-osdi.sh

# 4. Verify PDK, OSDI models, tools, pins and the DUT interface contract:
python3 sim/run_corners.py --check-env

# 5. Smoke the whole command surface -- one nominal point per bench, seconds:
./sim/characterize.sh smoke

# 6. Prove the HARNESS itself works, including the sabotage negative control:
./sim/selftest.sh

# 7. Reproduce every committed record (full 45-point PVT grid per bench):
./sim/characterize.sh characterize
```

`source sim/env.sh` exports the same PDK environment the harness resolved, so
an interactive `ngspice` or `xschem` session sees exactly what the runner
does.

If your PDK lives somewhere unusual, either set `SG13G2_PDK_PATH` (or the
conventional `PDK_ROOT` + `PDK` pair) or write a git-ignored
`sim/pdk.local.json`.

## Backend readiness

Every sim-dependent item (post-layout re-run, corner matrix, Monte Carlo
yield, aggregated characterization) needs the PSP103 OSDI model to elaborate.
As of the committed pex attempt
([`comparator-pex/README.md`](comparator-pex/README.md#why-nothing-simulated))
neither backend a `klt sim` leg can run on does so:

| backend | blocker | observable symptom |
|---|---|---|
| local | ngspice-42 supports OSDI v0.3; the PDK's `psp103.osdi` targets v0.4 (`ngspice_min_major: 46` in [`toolchain.json`](toolchain.json)) | `pre_osdi` prints `NGSPICE only supports OSDI v0.3 but ".../psp103.osdi" targets v0.4!`; `--check-env` reports `toolchain: DRIFT` (floor 46, installed 42) |
| batch fleet | runner image is klt 0.5.0, client is 0.7.0, and 0.5.0 has no `osdi_preload` | `options.osdi_preload` refused for `--backend batch`; with `stage_model_inputs: true` the job fails in seconds with `batch_runner_version_mismatch` |

The batch row is a tool gap already filed upstream (klayout-tools#2901,
#2851); the local row is a worker-spec gap (ngspice version), not a klt one.

**Preflight before submitting any grid** (a 45-point submit against a broken
backend only repeats the one-corner failure 45 times):

```bash
python3 sim/run_corners.py --check-env      # toolchain must not report DRIFT
klt sim --backend batch --format json sim/comparator-pex/requests/regeneration.nominal.json > <report.json>   # one corner
```

The regeneration request sets `osdi_preload`, so today the batch probe is
refused client-side and never reaches the fleet; that refusal is the expected
failure. A pass means *unblocked* only once both the refusal and the runner
version mismatch have cleared.

**Unblocked when** either the worker spec provides ngspice >= 46 (a change to
the worker spec in 2AMLogic/2am `infra/aws/loom-worker/`, not a host change),
or the fleet runner image reaches a klt that supports `osdi_preload`.

**A batch path that does work (issue #62, 2026-10-09).** The
[`klt-corner-verification/`](klt-corner-verification/) campaign ran
the full grid on the batch fleet and produced graded envelopes. It avoids both
blockers in the table: it submits with the **CI-pinned** client (klt
`0.5.0+ge8ca621a6961`, from a venv in the worktree; the host's 0.7.0 is not
used), so client and runner versions match. It also needs no
`osdi_preload`: every netlist body carries its own `.control` block that
`pre_osdi`-loads the runner image's baked OSDI models
(`/opt/pdk/ihp-sg13g2/libs.tech/ngspice/osdi/`), which is the workaround
documented in `sim/kltsim/build.py` (klayout-tools#2666). The envelopes record
ngspice 46 on the runner. This route does not unblock the local row, and it is
not the `osdi_preload` request form the pex leg uses. Adapting the pex leg to
it is #61's call.

The same route ran the issue #81 whole-latch noise campaign
([`comparator-transient-noise-full/`](comparator-transient-noise-full/)): the
internal-noise hook it uses is documented in
[`dut/README.md`](dut/README.md) "Optional internal-noise hook".

**If a preflight fails:** record the failure verbatim as an append-only
attempt, as the committed pex attempt does. Do not relax the spec, do not pass
`--allow-toolchain-drift` to manufacture evidence, and do not fall back to a
locally launched grid.

## Characterization report (T1 item 8)

`sim/characterize.sh` is a harness; the aggregated per-row report is a separate,
simulation-free step (issue #64):

```bash
./sim/characterize.sh report          # regenerate sim/characterization/20261009-d73a9ac-schematic/
./sim/characterize.sh report check    # re-hash every indexed source; fail if anything is stale
```

Stdlib `python3` only: no PDK, ngspice, `klt` or batch submit. It reads one
explicitly named committed campaign (`REPORT_CAMPAIGN`, default
`20261009-d73a9ac`; never "newest"), grades it with the committed
`sim/kltsim/grade.py` (read-only, so the DR-0002 reduction rules are not
duplicated and the campaign is not rewritten), requires the result to equal the
campaign's committed `grading.json`, and writes `input-index.json` (evidence
paths, sha256 digests, DR-0002 bounds, DUT identity, grader digest), `report.json`,
`report.md` (every DR-0002 row and sub-bound: value, unit, Target/Stretch bound
and verdict, binding point, population, statistical basis, sources) and the
generic `envelope.json` (`t1_item: 8`). The envelope's `status` mirrors
bounded-Target compliance of the schematic DUT (today `fail`: Rows 2 and 4a),
not report generation; FAIL, INCOMPLETE, GAP, INVALID_DUT, REJECTED_EVIDENCE,
REPORTED and NOT SPECIFIED stay distinct. Stale, tampered, non-finite or
inconsistent inputs are refused and write nothing. The manifest pins the hash of
`input-index.json`; see `manifests/README.md`, "Item 8". Unit tests:
`PYTHONPATH=sim python3 -m unittest kltsim.tests.test_characterization`
(also run by the `kltsim` discover step in "What CI runs").

## Reproducing one record

Every record ends with the exact command that regenerates it. It is always:

```bash
python3 sim/run_corners.py <experiment-slug> -j 8
```

A re-run mints a **new** record; it never overwrites one already committed.
This is enforced, not assumed: see "Run-identity reservation" below.
`sim/` is an evidence trail, not a status page.

## Pinned toolchain

[`sim/toolchain.json`](toolchain.json) pins the toolchain and the harness
**checks it before simulating**, refusing to run on a mismatch (override with
`--allow-toolchain-drift`, which then stamps the drift into every record made
under it).

| pin | value | checked? |
|---|---|---|
| IHP-Open-PDK release | `0.3.0` | **exact** — the release IS the device models |
| ngspice | ≥ 46 (major), OSDI-capable | floor |
| Python | ≥ 3.9 | floor |
| xschem | recorded, not checked | nothing here invokes xschem until `design/` has a schematic |
| OpenVAF-Reloaded (OSDI compiler) | `v24.0.1mob`, checksum-pinned | checked by `sim/tools/build-osdi.sh` at build time, not by the corner runner |

PDK variant: **ihp-sg13g2**, set in [`sim/pdk.json`](pdk.json).

## Corner grid

SG13G2's `cornerMOSlv.lib` is already a self-contained global process switch
for LV MOS — no `gf180mcu`-style multi-family bundle is needed. Full
definitions and rationale, including the full divergence table from
`gf180-comparator`'s harness: [`sim/harness/README.md`](harness/README.md).

| axis | points |
|---|---|
| process | `tt`, `ff`, `ss`, `fs`, `sf` (the default `mos` set, mismatch off); the same five with mismatch on (`mos_mismatch`) for the two Monte-Carlo offset benches (`comparator-offset-mc`, `comparator-offset-transient-mc`) |
| temperature | −40 °C, 27 °C, 125 °C |
| supply | 1.08 V, 1.20 V, 1.32 V (1.2 V ± 10 %) |

**45 points**, full factorial, per recorded run. Corner ids are
`<process>_<temp>c_<supply>v`, e.g. `ss_-40c_1.08v`, `tt_mismatch_27c_1.20v`.

There is no resistor-corner promotion yet: the placeholder DUT's load is an
ideal SPICE resistor, not a PDK resistor subckt — a tracked extension point
(`sim/harness/corners.py`'s module docstring), not a silent omission.

## Directory convention

```
sim/<experiment-slug>/
  README.md                       method, provenance, and what was NOT ported
  testbench/tb.json               manifest: analyses, measurements, checks
  testbench/<name>.spice          netlist FRAGMENT (harness owns models/OSDI/.temp/.control)
  records/<record-id>.md          the evidence record   <- append-only
  records/<record-id>.json        the same, machine-readable
  corners/<record-id>/<corner-id>.log   raw ngspice output, one per PVT point
  netlist-snapshots/<record-id>.spice   DUT + fragment exactly as simulated
```

`<record-id>` is `<UTC-YYYYmmdd-HHMMSS>-<short-sha>-<token>`, where `<token>`
is 6 random hex digits (issue #110). Records minted before #110 have no
token (`<UTC-YYYYmmdd-HHMMSS>-<short-sha>`) and keep their IDs unchanged.

### Run-identity reservation (issue #110)

Every `run_corners.py` run **exclusively reserves** its record ID before it
writes any deck or log (`harness/report.py` `reserve_run`):

1. A candidate ID is minted from the timestamp, commit and a fresh token.
2. The candidate is skipped if **any** member of its bundle already exists:
   `records/<id>.md`, `records/<id>.json`, `netlist-snapshots/<id>.spice`
   or `corners/<id>/`. Orphans left by a crashed run (logs without a
   record, or a stray snapshot) occupy the ID the same as a finished record.
3. The ID is claimed with an atomic `mkdir` of `corners/<id>/` (evidence
   runs only), then of a private scratch dir `sim/.work/<slug>/<id>/`. If
   either already exists, another run owns it. This run undoes only the
   empty directory it just created and retries with a new token. After 32
   failed attempts it refuses with exit code 5 and simulates nothing.

After reservation:

- Each raw log is created with exclusive mode before the point's deck is
  written or ngspice starts, so an existing log is never replaced.
- `write_record` checks the record, JSON twin and snapshot before writing
  any of them, then creates each one exclusively. If any already exists, it
  raises `EvidenceCollision` (exit 5). The existing bundle stays
  byte-identical.
- Cleanup removes only this run's own scratch dir. It never touches another
  run's scratch, nor this run's `corners/<id>/` logs.

**Recovery is always a new run ID.** If a run is refused or crashes, do not
delete, edit or reuse the occupied bundle. Re-run the command and a fresh ID
is reserved. An interrupted run's partial `corners/<id>/` stays as an
append-only trace of the attempt. Commit it as such or leave it uncommitted,
but never write into it again.

## Record format

Every record states, in its header, everything needed to judge or reproduce
it:

- the **claim** it substantiates (or, today, that it substantiates the
  harness and not a spec row);
- the **DUT** — id, provenance (`placeholder` / `schematic` / `extracted`),
  path and sha256;
- the **testbench** fragment and manifest sha256s;
- the **commit**, flagged loudly if the working tree was dirty — a
  dirty-tree record is not citable;
  Git provenance (commit, dirty paths) is captured and verified ONCE before
  the run reserves its identity or simulates, checking every git exit code;
  the same commit is used for the record id and the record. An
  evidence-writing run **refuses to start** (exit 6) if git is missing, times
  out, fails, or returns an invalid commit. `--no-write` exploration still
  works with provenance explicitly `unknown`; evidence writes outside a
  working Git checkout therefore require no-write mode;
- the **PDK** variant and release version, and the **toolchain** observed,
  plus any accepted drift;
- the **corner matrix** actually run and how many points completed;
- for a Monte-Carlo record, the **seed, draw count and σ derivation**
  (`CLAUDE.md` requires all three);
- the full per-corner result table, the grid spread, the per-axis corner
  sensitivity, the verdict, and the reproduction command.

Raw per-corner ngspice logs are committed alongside (`.gitignore` explicitly
un-ignores `sim/*/corners/**/*.log` for this reason), so a reader can check a
number against the tool's own output rather than against a table somebody
transcribed.

## What CI runs

PDK-dependent benches are not run in CI: they need the IHP-Open-PDK
checkout plus ngspice/OpenVAF, so they stay contributor-run with their
results committed as records. The harness's own unit tests
(`sim/harness/tests/`, pure stdlib, no PDK) do run in CI as the
`harness-unit-tests` job in `.github/workflows/ci.yml`; locally:

```bash
PYTHONPATH=sim python3 -m unittest discover -t sim -s harness.tests -p 'test_*.py'
```

The same job also runs a read-only freshness check of the post-layout
`klt pex` adapter inputs (`comparator-pex/dut/`, `comparator-pex/requests/`)
against the schematic, `dut.json` and the source benches, also stdlib only.
Commands and regeneration:
[`comparator-pex/README.md`](comparator-pex/README.md#freshness-check-ci-and-intentional-regeneration).

## Append-only evidence guard

`sim/` results are append-only, and CI enforces it (issue #116): the
`append-only-evidence` job in `.github/workflows/ci.yml` runs
`scripts/check_append_only_evidence.py` (stdlib only, no PDK).

**Protected:** every file under `sim/<bench>/{records,corners,netlist-snapshots,campaigns,reports}/`
for any bench name (matched by path component), including campaign request
JSON, copied DUTs, generated decks, probes, failed attempts, and
`comparator-pex/reports/`. A protected path present at the base must exist at
the head with the same blob ID and mode; additions are always fine. Edits,
deletions, type/mode changes, and moves *away* from a protected path fail (a
move is a deletion plus an addition; moving a file *into* a protected
directory, or copying evidence unchanged, passes).

**Not protected (mutable sources):** `sim/*/testbench/`,
`sim/klt-corner-verification/benches/`, `sim/comparator-pex/{dut,requests}/`,
harness/adapter code, READMEs, manifests, and
`layout/comparator/{comparator.pex.spice,pex_report.json}`.

**Comparison modes (CI):** pull request -- `git merge-base base head` to the
actual PR head SHA; push to main -- event `before` to `after` (empty tree if
`before` is all zeros); workflow_dispatch -- `HEAD^` to `HEAD`, a last-commit
audit only. Missing revisions fail the job (exit 2), never skip. Exit 1 means
a violation or an invalid exception registry. Locally:

```bash
python3 scripts/check_append_only_evidence.py --base "$(git merge-base origin/main HEAD)" --head HEAD
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
```

**Exceptions:** there is no bypass flag or environment override. A deliberate,
justified change needs an entry in `sim/evidence-exceptions.json` *and* a
tracked decision record under `spec/decision-records/*.md` containing a fenced
`json` block with the identical authorization tuple. Each entry authorizes
exactly one old-path transition (no globs, prefixes, or traversal; unique
paths; deletions use null `new_oid`/`new_mode`):

```json
{"version": 1, "exceptions": [{
  "path": "sim/comparator-offset/records/example.json",
  "old_oid": "<40-hex blob id at base>", "old_mode": "100644",
  "new_oid": "<40-hex blob id at head, or null>", "new_mode": "100644",
  "decision_record": "spec/decision-records/0004-example.md",
  "reason": "why this evidence must change"
}]}
```

The decision record must contain a fenced json block with the same
`path`, `old_oid`, `old_mode`, `new_oid`, `new_mode`. Stale entries never
authorize a different base blob or destination. Reviewers judge the
rationale in the record as well as the change.

## Evidence size budget

Committed evidence dominates repository size, so growth is bounded by a
machine-checked contract (issue #132). The `append-only-evidence` job runs
`scripts/check_evidence_size.py --tree <target sha>` (stdlib only) against
`sim/evidence-size-budget.json`. Bulk-storage policy (compression versus
external storage) is deliberately out of scope here; this only measures and
caps growth, and never edits, moves or externalizes existing evidence.

**Accounting.** Bytes are Git blob sizes from `git ls-tree -rl <tree>` of the
named commit/tree -- not working-tree or pack sizes. The checker reports
repository-wide and `sim/` totals plus per **evidence unit**: the entry
`sim/<bench>/<records|corners|netlist-snapshots|campaigns|reports>/<name>`
(a campaign or run directory, or one record/report file). A missing or
non-numeric size fails closed (exit 2), so never use a blob filter. The checker
also refuses a partial clone up front (`extensions.partialClone` or a
`remote.<name>.promisor` remote: exit 2, naming the cause) and runs git with
`GIT_NO_LAZY_FETCH=1`, so a missing blob is an error rather than one network
round trip per blob (~97k; that is how CI run 38029844566 hung). A shallow
clone is accepted: it holds every blob of the commits it has.

**Baseline and grandfathering.** The budget file records the baseline commit
(`2c6002775...`: 97,217 blobs / 509,447,840 B repo, 96,352 blobs /
489,675,829 B under `sim/`) and the bytes of every existing unit. An existing
unit may not exceed its recorded bytes (grandfathered at exactly that size).

**Thresholds.** Allowance = 10% of baseline `sim/` bytes rounded up to the next
MiB: ceil(10% x 489,675,829 B / 1,048,576) = 47 MiB = 49,283,072 B.
* total ceiling = baseline `sim/` bytes + allowance = 538,958,901 B (the
  budget file and any other `sim/` file count toward it);
* a unit not in the baseline (a new campaign) is capped at the same 49,283,072 B.
The checker validates the derivation (percentage, operands, ceilings); changing
the percentage or resetting the baseline is a reviewed change to
`scripts/check_evidence_size.py` plus a decision record, not a quiet edit of
the JSON. Regenerate numbers for a new baseline with
`python3 scripts/check_evidence_size.py --tree <commit> --emit-budget <commit>`.

**Exceptions.** There is no bypass flag or environment override. An entry in
the budget's `exceptions` list names one exact path (`sim` for the total, or one
evidence unit; no wildcards), the exact `additional_bytes`, a `reason`, and a
tracked `spec/decision-records/*.md` containing a fenced `json` block with the
same path and bytes:

```json
{"kind": "evidence-size", "path": "sim/<bench>/campaigns/<id>", "additional_bytes": 12345678}
```

The bytes raise only that path's ceiling (baseline or new-unit) by exactly that
amount. Missing or mismatching records, extra/missing keys, wildcards,
non-positive or non-integer bytes, and duplicates fail validation.
Overage output names the path, measured bytes, ceiling and this route.

**Sparse CI checkouts.** Every job in `.github/workflows/ci.yml` checks out
only its explicit, audited inputs (non-cone patterns, never a `filter:`).
Caveat: `actions/checkout` silently adds `--filter=blob:none` whenever its
`sparse-checkout:` input is set, and an empty `filter:` cannot turn that off.
The three jobs that only read files inside their cone use that input and are
therefore blob-less partial clones, which is harmless for them. The
`append-only-evidence` job measures blob sizes, so it must be a complete clone:
its checkout has `fetch-depth: 0` and **no** `sparse-checkout:` input, and the
next step applies its patterns with `git sparse-checkout set --no-cone --stdin`
(failing with exit 2 if the clone is partial). The full fetch is small (the
repository packs to roughly 60 MiB); only the transient full working tree
costs a few seconds. Cones (each must contain the job's complete transitive
inputs):

| Job | Inputs beyond its own scripts |
|---|---|
| signoff-manifest-parity | `ci.yml`, `scripts/check_{klt_pin,signoff_report}.py`, `manifests/`, `layout/`, `design/`, the manifest-cited `sim/klt-corner-verification/campaigns/20261009-d73a9ac/kickback.envelope.json` |
| layout-reproducibility | `layout/`, `design/comparator.spice`, `manifests/klt-pin.json` |
| harness-unit-tests | `sim/{harness,kltsim,comparator-pex}/`, the `comparator-{regeneration,kickback}/testbench/` source benches, `sim/dut.json`, `sim/dut/`, `sim/klt-corner-verification/{benches/,rows.json}`, the top-level `*.json`/`*.spice` of campaign `20261009-d73a9ac`, `campaigns/20261009-issue78/fixture/`, `design/` |
| append-only-evidence | `scripts/`, `ci.yml`, `sim/evidence-{exceptions,size-budget}.json`, `spec/decision-records/` |

A new input a job starts reading must be added to its patterns in the same
change. `scripts/tests/test_sparse_checkout.py` proves the cones: it builds a
clean clone of `HEAD` per job with the same semantics `actions/checkout`
applies to that job's `with:` block (implied `blob:none` filter over `file://`
for a `sparse-checkout:` input, complete clone otherwise) and runs the job's
exact `run:` commands, including the narrowing step (tests skipping because an
input is outside the cone fail). It also asserts that every job running the
size checker gets a complete clone, and that the size step exits 2 quickly in
a `blob:none` clone. The two jobs that need the pinned `klt` run there only when the
pinned build is first on `PATH`; otherwise they are skipped locally and proven
by the real CI jobs.

Reproduce locally:

```bash
python3 scripts/check_evidence_size.py --tree HEAD
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
# pinned klt jobs too: python3 -m venv /tmp/v && /tmp/v/bin/pip install \
#   "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@<manifests/klt-pin.json commit>" klayout==0.30.10
# PATH=/tmp/v/bin:$PATH python3 -m unittest scripts.tests.test_sparse_checkout
```

## Rules

- **No claim without a testbench.** A number that is not in a record under
  `sim/` is not a result.
- **PVT corners on every recorded result.** A single-corner run is a smoke
  test and writes no evidence.
- **`sim/` is append-only.** Add records; never edit or delete one.
- **A placeholder measurement is never a spec claim.** The provenance stamp
  is the mechanism, not the etiquette.
- **Do not relax a check to make a result pass.** A check that is wrong gets
  a documented recalibration citing the record it was calibrated from — the
  convention every `min_spread_pct_by_axis` floor here already follows.

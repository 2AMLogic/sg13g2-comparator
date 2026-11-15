# Extracted regeneration at the three ss / 125 C corners via batch, 2026-11-14 (issue #417, part of #61)

Closes the unmeasured gap left by `batch-extracted-grid.regeneration.20261031.md`, which compared 42 of 45
corners and recorded **ss / 125 C / `vdd_val` 1.08, 1.2, 1.32** as having no extracted-side data. All three are
now measured on both sides. That report is unchanged; this is a separate, additive record covering only those
three corners. **Three corners are not a grid result and carry no DR-0002 verdict**; the 45-corner grid
statement stays with the 10-31 report.

Client `klt 0.9.2.dev1024+g8da9718f0cb6` (git `8da9718f0cb6140607431017e6573c531a2b1d92`), a development
build, **not** a released client: `manifests/klt-pin.json` pins `klayout-tools` 0.8.0, which the 10-31 report
measured as having no `klt pex --submit-only/--attach/--max-units-per-job`. Running out of pin is a known
condition tracked in #416, not resolved here. KLayout 0.30.13; PDK `ihp-sg13g2` `fetched:0.3.0`; deck
`sg13g2` `sha256:cf6dfeadf75bd95bf89beb0a64e06ed43b65f6ff782df10ae200ea200a73d8e9` (`released: false`).

**Nothing ran locally.** Both legs ran on the AWS Spot batch fleet (`--backend batch`, provider
`aws-batch-fleet`, `us-east-1`, `c7i.4xlarge`, `lifecycle: spot`), engine ngspice 47 on the worker
(`engine_host: worker`). `--wait-for-capacity 600` was passed on the submit, the only invocation that launches
anything; no local probe or debug corner was run at any point.

## Netlist hashes (which hash, of which artifact)

- **Extracted netlist, as extracted by this run**: sha256
  `b313a02db7afb50da9348e74baab116c9563156678d5e874564beffa27b51d47` (`extraction.netlist_sha256`), from
  `layout/comparator/comparator.gds` with `--deck sg13g2 --top comparator
  --pins clk,dout,doutb,vbias,vdd,vinn,vinp,vss`; 64 devices, 18 nets. This is byte-identical to the netlist
  the 10-31 grid run extracted, so the two records compare the same extracted artifact.
- **The committed `layout/comparator/comparator.pex.spice`** hashes sha256
  `9bd443bec862e96a3cae3bf3651506e75c8ceeb6a534789ef794c5defe58980a` and is a **different artifact**; this run
  did not read it. `klt pex` re-extracts from the GDS, it does not consume the committed netlist.
- Schematic leg `sim/comparator-pex/dut/comparator.schematic.sp`
  `sha256:884cb586218637b0e84c391791fa8025d8dae957793bed01c17d9f8d0581f23f`; testbench body
  `sim/comparator-pex/dut/tb_regeneration.sp`
  `sha256:732ab76c3df2ac89a1703d270206d34dda9b113027d6fc18845cac128d5591ba`; request
  `sha256:e7c830e844abd70155a1fc9a0617c623367783cff8de5c769385d2573d57686a`.

## Request and timeout

The committed `requests/regeneration.pvt.json` was **not** edited: it is a derived file checked by
`make_requests.py --check` and `tests/test_freshness.py`. A throwaway copy outside the repository tree
(`/tmp`, not committed) restricted `corners.process` to `ss`, `corners.temperature_c` to `[125]` and raised
`options.timeout_s` 600 -> **1800**; the supply axis (`vdd_val` 1.08, 1.2, 1.32), the netlist, all **12
measurement cards** and the OSDI preload are the committed request's, verbatim. 3 units per side.

`klt` warned that `timeout_s` 1800 x 3 units exceeds the fleet's 3600 s whole-job ceiling, so a job still
running at the ceiling would have been killed and reported `batch_job_timeout`. It did not arise: the jobs
finished in 13 s and 45 s. The bound is `timeout_s x units`, not a runtime estimate.

## Steps

1. `--submit-only` returned 0 in about 60 s with a complete manifest — 1 job per side, no sharding, so the
   client-side time cap that produced the 10-31 gap (30 shard jobs at about 20 s each) was never approached.
   **The manifest was copied before any collect**, because `--attach` consumes it (the 2026-11-03
   tt / -40 C / 1.32 V entry in `README.md` records a run that could not be re-collected after the first
   `--attach`).
2. The first `--attach` was **refused pre-flight**: `--wait-for-capacity cannot be combined with --attach:
   attach launches nothing, so there is no capacity to wait for`. The refusal consumed nothing (all manifest
   copies verified byte-identical afterwards), but it contradicts `--attach`'s own help text, which says to
   re-run *the same* `klt pex` command — see Friction below.
3. `--attach` without that one flag collected both legs.

| leg | job | state | exit | `elapsed_seconds` | corners |
|---|---|---|---|---|---|
| schematic | `klt-sim-55fa249b7bd4` | `done` | 0 | 13 | 3/3 `pass` |
| extracted | `klt-sim-48d01a80ae36` | `failed` | 4 | 45 | 3/3 `error`, from `td_c` alone; the other 11 measurements reported |

`runner_klt_version: 0.9.0`, `client_klt_version: 0.9.2.dev1024+g8da9718f0cb6`,
`runner_compatibility: match`, `runner_request_features.status: supported` (`missing: []`). The 2026-11-08
probe recorded the 0.9.0 runner *refusing* a 0.8.0 client; a 0.9.2 client is accepted, now measured rather
than inferred. No `batch_no_capacity`, no `batch_runner_version_mismatch`, no lost shard, no `unfinished` leg.

## Result (envelope `status: error`; 3 corners; 36 delta rows: 33 passed, 0 failed, 3 errored)

**All three corners produced both-side values with deltas**, for 11 of 12 measurements. `body_bias.status:
biased`. `model_mismatch.kind: count_only` (12 nmos / 12 pmos schematic vs 38 / 26 extracted, finger
decomposition). The envelope's `status: error` is the three `td_c` rows, nothing else.

| row | median | min .. max | 10-31 grid's 42 corners (median, range) |
|---|---|---|---|
| `td_a` | +142.6 % | +133.7 .. +148.4 | +189.8 % (+115.6 .. +266.5) |
| `td_b` | +134.9 % | +123.7 .. +145.7 | +185.1 % (+109.3 .. +264.1) |
| `q_dec` | -11.4 % | -14.9 .. -9.4 | -12.1 % (-24.8 .. -8.6) |
| `i_stat` | -0.1 % | -0.1 .. -0.1 | -0.1 % (-0.1 .. +0.9) |
| `vsup_v`, `da_end`, `db_end`, `dc_end` | 0.0 % | 0.0 .. 0.0 | 0.0 % |

Every one of these sits **inside** the range the other 42 corners already span, so these three corners are
not outliers; they are the same lumped-RC slowdown at a slow-process, hot corner. `*_first` percentage
deltas are artifacts of a near-zero schematic denominator and are not read as findings — use the absolute
values in the table below, as the 10-31 report does.

- **`td_c` has no extracted value at any of the three corners**: `measurement 'td_c' produced no value --
  ngspice reported: out of interval`, the same cause recorded at all 45 corners of the 10-31 grid, at the
  3-unit 10-30 sample, and in `devonly-attribution.20261011.md`. The rows are recorded **as errored**, not
  omitted and not pass/fail. Consistent with it: `dc_first` reads `low -> high: WRONG STATE` on the extracted
  side at all three corners (about 1.0 against a schematic 5e-06), i.e. the `dcn` node is already high before
  the input flip, so the decision edge falls outside the `.meas` window. Its cause is **not** re-isolated
  here.
- `da_first` / `db_first` stay `low` and `da_end` / `db_end` / `dc_end` stay `high` on both sides at all three
  corners.
- These are schematic-versus-extracted deltas on the lumped-RC model, **not** DR-0002 spec-row verdicts, and
  carry no sigma: 3 deterministic transient corners, no Monte Carlo, no seeds.

### Why the delay rows read "ungraded"

`delay_compliance_extracted` is empty and `pvt_grid_points` is 0 in the JSON. This is a **label** limitation,
not a measurement one: since `make_requests.py` moved the supply onto the `corners.params` axis (current klt
rejects `vdd_val` under `supply_v`), klt writes corner ids as `ss/novdd/125C/params:vdd_val=1.08`, which
`make_delta_table.py`'s canonical `<process>/<volts>V/<temp>C` form does not parse, so every point falls
outside the recognised grid and no bound is applied. The same is true of the 10-31 grid run's corner ids. It
does not affect any value, delta or status recorded here, and withholding a DR-0002 verdict is the correct
outcome for three corners regardless. Tracked in #424; it is not fixed in this record.

## Provenance of the table below

`make_delta_table.py --bench regeneration.ss125`. `klt pex` prefixes `delta[]` `spec_row` with the request's
filename stem only when given **more than one** testbench, so this single-request run emitted bare
measurement names; `--bench` supplies the missing bench label and nothing else (recorded as
`spec_row_prefix` in the JSON). Every value, status and delta below is klt's, unchanged. The full envelope
(about 78 KB, carries host ngspice paths) is **not committed**, per the convention of the 10-30 sample and
10-31 grid; `batch-extracted-ss125.regeneration.20261114.json` is the committed derived table of all 36 rows.

## Not established / still open

- The extracted offset and transient-noise Monte Carlo points still missing from the grid (tracked in #61) —
  untouched here.
- Any DR-0002 verdict, and the 45-corner grid statement: three corners are not a grid result. Item 7 of T1
  is **not** changed by this record; the updated item-7 citation, hash and regenerated signoff report remain
  open, as does the kickback PVT request.
- Why `td_c` does not fire on the extracted netlist. Unchanged and not re-isolated.
- The corner-id canonicalisation gap described above.

## Friction for `2AMLogic/klayout-tools` (generic)

Both filed generically against the tool, with no design detail:

- [klayout-tools#5683](https://github.com/2AMLogic/klayout-tools/issues/5683) — `klt pex --attach` refuses
  `--wait-for-capacity`, while its own help instructs the caller to *re-run the same command* with the
  manifest. A caller whose environment mandates the capacity flag on every batch submit must therefore
  construct two different command lines for one logical run, and only finds out after the jobs are submitted.
- [klayout-tools#5681](https://github.com/2AMLogic/klayout-tools/issues/5681) — `delta[]`'s `spec_row` is
  prefixed with the request stem only for a multi-testbench run and is a bare measurement name otherwise,
  with no flag to request the prefixed form. A single-testbench envelope's rows are therefore not
  self-describing: a downstream consumer cannot tell which bench a row belongs to.

## Full delta table (36 rows)

Statistical basis: none: deterministic transient measurements at 3 corner(s); no Monte Carlo, no seeds; no sigma or offset/noise compliance is implied. Corners: ss/novdd/125C/params:vdd_val=1.08, ss/novdd/125C/params:vdd_val=1.2, ss/novdd/125C/params:vdd_val=1.32.

klt status = measurement availability (both legs produced a value; no limits are set in the requests), not circuit compliance.


| row | corner | schematic | extracted | delta % (raw) | klt status (availability) | interpretation |
|---|---|---|---|---|---|---|
| regeneration.ss125.vsup_v | ss/novdd/125C/params:vdd_val=1.08 | 1.08 | 1.08 | +0.000 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.td_a | ss/novdd/125C/params:vdd_val=1.08 | 8.36464e-10 | 1.95468e-09 | +133.684 | pass | ungraded: corner outside the ratified PVT grid |
| regeneration.ss125.td_b | ss/novdd/125C/params:vdd_val=1.08 | 1.21919e-09 | 2.72676e-09 | +123.653 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.td_c | ss/novdd/125C/params:vdd_val=1.08 | 1.43685e-09 | n/a (no value) | n/a | error | ungraded: corner outside the ratified PVT grid |
| regeneration.ss125.da_first | ss/novdd/125C/params:vdd_val=1.08 | 6.99775e-06 | 6.75624e-06 | n/a: logic state | pass | low -> low: correct (expected low) |
| regeneration.ss125.db_first | ss/novdd/125C/params:vdd_val=1.08 | 1.40946e-07 | 7.71924e-06 | n/a: logic state | pass | low -> low: correct (expected low) |
| regeneration.ss125.dc_first | ss/novdd/125C/params:vdd_val=1.08 | 6.53335e-06 | 0.999999 | n/a: logic state | pass | low -> high: WRONG STATE (expected low) |
| regeneration.ss125.da_end | ss/novdd/125C/params:vdd_val=1.08 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.db_end | ss/novdd/125C/params:vdd_val=1.08 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.dc_end | ss/novdd/125C/params:vdd_val=1.08 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.i_stat | ss/novdd/125C/params:vdd_val=1.08 | -2.03626e-05 | -2.0377e-05 | -0.071 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.q_dec | ss/novdd/125C/params:vdd_val=1.08 | -1.94851e-13 | -2.13198e-13 | -9.416 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.vsup_v | ss/novdd/125C/params:vdd_val=1.2 | 1.2 | 1.2 | +0.000 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.td_a | ss/novdd/125C/params:vdd_val=1.2 | 8.3042e-10 | 2.0146e-09 | +142.600 | pass | ungraded: corner outside the ratified PVT grid |
| regeneration.ss125.td_b | ss/novdd/125C/params:vdd_val=1.2 | 1.13064e-09 | 2.65626e-09 | +134.934 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.td_c | ss/novdd/125C/params:vdd_val=1.2 | 1.30012e-09 | n/a (no value) | n/a | error | ungraded: corner outside the ratified PVT grid |
| regeneration.ss125.da_first | ss/novdd/125C/params:vdd_val=1.2 | 1.22644e-07 | 9.67998e-08 | n/a: logic state | pass | low -> low: correct (expected low) |
| regeneration.ss125.db_first | ss/novdd/125C/params:vdd_val=1.2 | 5.83119e-06 | 6.50689e-06 | n/a: logic state | pass | low -> low: correct (expected low) |
| regeneration.ss125.dc_first | ss/novdd/125C/params:vdd_val=1.2 | 5.80305e-06 | 0.999999 | n/a: logic state | pass | low -> high: WRONG STATE (expected low) |
| regeneration.ss125.da_end | ss/novdd/125C/params:vdd_val=1.2 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.db_end | ss/novdd/125C/params:vdd_val=1.2 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.dc_end | ss/novdd/125C/params:vdd_val=1.2 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.i_stat | ss/novdd/125C/params:vdd_val=1.2 | -2.0363e-05 | -2.03772e-05 | -0.070 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.q_dec | ss/novdd/125C/params:vdd_val=1.2 | -1.98425e-13 | -2.21042e-13 | -11.398 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.vsup_v | ss/novdd/125C/params:vdd_val=1.32 | 1.32 | 1.32 | +0.000 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.td_a | ss/novdd/125C/params:vdd_val=1.32 | 8.50185e-10 | 2.11199e-09 | +148.415 | pass | ungraded: corner outside the ratified PVT grid |
| regeneration.ss125.td_b | ss/novdd/125C/params:vdd_val=1.32 | 1.10219e-09 | 2.70862e-09 | +145.749 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.td_c | ss/novdd/125C/params:vdd_val=1.32 | 1.24379e-09 | n/a (no value) | n/a | error | ungraded: corner outside the ratified PVT grid |
| regeneration.ss125.da_first | ss/novdd/125C/params:vdd_val=1.32 | 4.87334e-06 | 4.7622e-06 | n/a: logic state | pass | low -> low: correct (expected low) |
| regeneration.ss125.db_first | ss/novdd/125C/params:vdd_val=1.32 | 1.15256e-07 | 7.81793e-08 | n/a: logic state | pass | low -> low: correct (expected low) |
| regeneration.ss125.dc_first | ss/novdd/125C/params:vdd_val=1.32 | 5.14885e-06 | 0.999999 | n/a: logic state | pass | low -> high: WRONG STATE (expected low) |
| regeneration.ss125.da_end | ss/novdd/125C/params:vdd_val=1.32 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.db_end | ss/novdd/125C/params:vdd_val=1.32 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.dc_end | ss/novdd/125C/params:vdd_val=1.32 | 0.999999 | 1 | n/a: logic state | pass | high -> high: correct (expected high) |
| regeneration.ss125.i_stat | ss/novdd/125C/params:vdd_val=1.32 | -2.03636e-05 | -2.03776e-05 | -0.069 | pass | ungraded (no mapped criterion) |
| regeneration.ss125.q_dec | ss/novdd/125C/params:vdd_val=1.32 | -2.03188e-13 | -2.33371e-13 | -14.855 | pass | ungraded (no mapped criterion) |

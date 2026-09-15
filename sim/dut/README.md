# `sim/dut/` — the device under test

Every testbench in `sim/` instantiates the DUT; **no testbench contains a
comparator netlist.** The binding lives in one file, [`sim/dut.json`](../dut.json),
and the harness (`sim/harness/dut.py`) includes it in every generated deck.

Today it points at [`../../design/comparator.spice`](../../design/comparator.spice) —
the real design, regenerated from the xschem sources in `design/` per
[`spec/decision-records/0001-comparator-topology.md`](../../spec/decision-records/0001-comparator-topology.md)
("DR-0001"): a single-tail (bottom-tail) StrongARM dynamic latch on
SG13G2's own `sg13_lv_nmos`/`sg13_lv_pmos` devices. The former placeholder,
[`placeholder_comparator.spice`](placeholder_comparator.spice), stays
committed (evidence is append-only, `sim/README.md`) but is no longer bound
by `sim/dut.json`.

## What is bound here today

| field | value |
|---|---|
| `id` | `comparator-dr0001` |
| `provenance` | **`schematic`** |
| `netlist` | `design/comparator.spice` (regenerated from `design/comparator*.sch` by `design/netlist.py`) |

`provenance: schematic` still does **not** mean `README.md`'s
target-specification table rows are met — that ratification is a distinct,
later act (`spec/porting-plan.md`'s third step in this three-issue chain;
see "Spec lines affected" in DR-0001). It does mean the numbers are measured
against the actual ratified topology rather than a stand-in, so
`sim/harness/report.py` no longer stamps the placeholder banner on records
produced against it.

**`comparator_dut_analog` is not this design's real front end.** Per
DR-0001's Decision §3, a bare single-tail StrongARM latch has no
DC-resolvable analog front end at all — its own input pair shares the tail
node and the regenerative loop, which has no stable operating point once
`CLK` is high and no meaning while `CLK` is low. `design/comparator_dut_analog.sch`
instead implements DR-0001's own named interim path (Consequence 2): the
same tail/input pair as the real design, but with its cross-coupled PMOS
loads replaced by diode-connected ones, breaking the positive-feedback loop
so the small-signal offset-MC and preamp-noise benches have a real DC
operating point to analyze. **Read [`../../design/README.md`](../../design/README.md)
before quoting any number measured against this sub-model** — DR-0001 and
that file both caveat it as an offset/noise *lower bound* that excludes
regeneration noise, not the design's actual noise/offset performance.

## Why a placeholder existed at all

Before DR-0001, this repo's comparator topology was not decided
(`spec/porting-plan.md` step 1, done in issue #10). The harness could not be
*proven* to work without something to simulate — "the four benches would run
once a design exists" is exactly the kind of untested claim this repo's
`CLAUDE.md` forbids ("no claim without a testbench").

So: a placeholder, loudly labelled, with real records committed against it,
and a one-line swap to the real design once the topology decision (DR-0001)
and its schematic implementation (this file's current binding) landed — the
swap this file itself documents in "Swapping in the real design" below.

**The placeholder was never a topology proposal.** Its front end was a
textbook resistively-loaded NMOS pair at unconsidered sizing; its decision
stage was *behavioural* precisely so it committed to no transistor topology
at all. Its records remain in `sim/*/records/` (append-only), each still
carrying its own `provenance: placeholder` banner, so nothing measured
against it is ever confused with a `provenance: schematic` record measured
against the real design.

## Interface contract

A DUT netlist must define these three subcircuits with these pins, in this
order. `sim/harness/dut.py` checks it textually at load time and refuses a
mismatch — a silently reordered pin list would miswire all four benches into
plausible-looking wrong answers. **This is the one thing this repo keeps
IDENTICAL to `gf180-comparator`'s own contract** — `CLAUDE.md` states this
repo is a two-PDK twin with `gf180-comparator` and the benches must stay
structurally identical.

```
.subckt comparator_dut        vinp vinn clk ibias dout doutb vdd vss
.subckt comparator_dut_analog vinp vinn     ibias aop  aon   vdd vss
.subckt comparator_dut_latch  inp  inn  clk       dout doutb vdd vss
```

| pin | meaning |
|---|---|
| `vinp` / `vinn` | differential inputs. `v(vinp) > v(vinn)` ⇒ `dout` HIGH. |
| `clk` | decision strobe. LOW = reset, HIGH = evaluate. |
| `ibias` | bias-current input pin. The testbench forces `dut_ib` into it. |
| `dout` / `doutb` | complementary decision outputs, **held** between strobes. |
| `aop` / `aon` | front-end analog outputs. `v(aop) - v(aon) = +A_v·(v(vinp) - v(vinn))`. |
| `inp` / `inn` | decision-stage inputs — driven by `aop` / `aon` inside `comparator_dut`. |
| `vdd` / `vss` | supply and ground. |

The netlist must **not** contain `.include`, `.lib`, `.temp`, `.control`,
`.endc` or `.end` — the harness owns all of those (same rule as testbench
fragments), including the OSDI `pre_osdi` preflight SG13G2's PSP103-based
models need (`sim/harness/README.md` "OSDI preflight"). Operating-point
parameters come from `sim/dut.json`'s `params` map (`dut_ib`, `dut_vcm`), not
from the netlist.

### Why the DUT is split into three subckts, not one

Two of the four experiments — [`comparator-offset-mc`](../comparator-offset-mc/)
and [`comparator-preamp-noise`](../comparator-preamp-noise/) — are
**small-signal analyses about a DC operating point** (`dc` sweeps and
`.noise`). A reset-and-regenerate decision stage has no DC operating point,
so `.noise` returns nothing usable for a full latched comparator and a DC
offset sweep is meaningless on one. This is the same constraint
`gf180-sar-adc` (and, after it, `gf180-comparator`) documents at length in
its `sim/comparator-preamp-noise/` testbench header.

Exposing the DC-resolvable front end separately is how those two benches stay
`.noise`/`dc`-based. `comparator_dut_latch` exists for the same reason from
the other side: the noise bench instantiates it with `clk` held low so the
front end's noise bandwidth is set by the capacitance it *actually* drives,
rather than by a lumped capacitor somebody invented — under-loading that node
would raise the bandwidth and so **under-report** the noise.

**This split is the one assumption the contract makes about the topology**,
and it is stated here rather than buried. If the ratified topology turns out
to have no DC-resolvable front end at all — a bare dynamic latch, say — then
`comparator_dut_analog` cannot be provided honestly, and the offset-MC and
preamp-noise benches must be re-founded on transient Monte Carlo / transient
noise instead (thousands of trials per corner rather than one deterministic
analysis). That is a known, named consequence of the topology decision,
recorded here so the decision record can *weigh* it rather than discover it.
It is not a reason to fake a front end.

## Swapping in the real design

**Done as of DR-0001's schematic-implementation issue** (`design/comparator.spice`,
bound above). The steps below are what that swap did, kept here as the
procedure for the *next* swap — a revised schematic, or a post-layout
extracted netlist:

1. Commit the netlist (e.g. `design/comparator.spice`, or an xschem-generated
   netlist) satisfying the contract above, on SG13G2's own device primitives
   (`sg13_lv_nmos`/`sg13_lv_pmos`, or their HV counterparts if a decision
   record ratifies a mixed-rail topology).
2. Edit `sim/dut.json`:

   ```json
   {
     "netlist": "../design/comparator.spice",
     "id": "comparator-dr000N",
     "provenance": "schematic",
     "params": {"dut_ib": 1e-05, "dut_vcm": 0.6}
   }
   ```

3. `python3 sim/run_corners.py --check-env` — confirms the contract is met
   (and that the OSDI device models the new netlist needs are present; see
   `sim/harness/README.md`).
4. Re-run the four experiments (`sim/characterize.sh characterize`). The
   placeholder records stay in `records/` (evidence is append-only) but every
   new record is stamped `provenance: schematic` and carries no placeholder
   banner.

For a post-layout run, set `provenance` to `extracted` and point at the
extracted netlist; the record header distinguishes the two.

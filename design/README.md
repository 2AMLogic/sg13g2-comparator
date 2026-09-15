# `design/`

Schematics (xschem) and the netlist derived from them.

## What is here

| file | role |
|---|---|
| [`comparator.sch`](comparator.sch) / [`comparator.sym`](comparator.sym) | The design core: a single-tail (bottom-tail) StrongARM dynamic latch, plus isolation inverters and a NOR SR output latch that hold `dout`/`doutb` between clock strobes — per [`spec/decision-records/0001-comparator-topology.md`](../spec/decision-records/0001-comparator-topology.md) ("DR-0001"). |
| [`comparator_dut.sch`](comparator_dut.sch) / `.sym` | Contract wrapper #1: the core plus a diode-connected tail-bias reference device on the `ibias` pin. Emits `.subckt comparator_dut` (`sim/dut/README.md`'s full-comparator contract). |
| [`comparator_dut_latch.sch`](comparator_dut_latch.sch) / `.sym` | Contract wrapper #2: the core with its tail-bias gate tied directly to `vdd` (this subcircuit's contract has no `ibias` pin at all — see `sim/dut/README.md`). Emits `.subckt comparator_dut_latch`. |
| [`comparator_dut_analog.sch`](comparator_dut_analog.sch) / `.sym` | Contract wrapper #3, and the one that needs the caveat below. Emits `.subckt comparator_dut_analog`. |
| [`comparator_netlist_top.sch`](comparator_netlist_top.sch) | Netlist-assembly cell only — instantiates all three contract wrappers once each so a single `xschem -n` run emits every required `.subckt` block (including the shared `comparator` core, emitted once). Never simulated on its own. |
| [`netlist.py`](netlist.py) | Regenerates [`comparator.spice`](comparator.spice) from the schematics above. Run `python3 design/netlist.py` after any schematic edit; `--check` fails if the committed netlist is stale. |
| [`comparator.spice`](comparator.spice) | **Derived. Do not hand-edit.** Regenerate instead. |

## Topology, in one paragraph

A tail NMOS (`MT`) mirrors the current forced into `ibias` (via a
diode-connected reference device, `comparator_dut`'s `MB`) into the tail
node; a clock-gated tail switch (`MSW`) gates that current into the
differential input pair (`M1`/`M2`) only while `CLK` is high. The input
pair's drains feed a cross-coupled NMOS/PMOS regenerative pair (`M3`–`M6`)
that resolves the small input-referred difference into a rail-to-rail
decision once `CLK` releases the CLK-gated PMOS precharge devices (`M7`–`M10`,
which hold all four internal decision nodes at `VDD` while `CLK` is low).
Two isolation inverters (`MIAP`/`MIAN`, `MIBP`/`MIBN`) buffer the internal
regeneration nodes before a NOR-gate-built SR latch (`MNAP*`/`MNAN*`/`MNBP*`/`MNBN*`)
holds `dout`/`doutb` between strobes, satisfying the interface contract's
"held between strobes" requirement (`sim/dut/README.md`). This is the
9-device single-tail class DR-0001's "Sizing rationale" section names as
its block-diagram-level starting point, plus DR-0001's own named
reset-integrity check (Consequence 5): the 4-device precharge stage here
(one per internal node, not 2) is this schematic's answer to that check —
see "Open items" below.

## `comparator_dut_analog` is a reduced sub-model, not the real front end

**Read this before quoting any number measured against
`comparator_dut_analog`.** Per DR-0001's Decision §3, a bare single-tail
StrongARM latch has **no DC-resolvable analog front end at all**: the input
pair shares the tail node and the cross-coupled regenerative loop, which has
no stable small-signal operating point once `CLK` goes high (positive
feedback prevents one) and no meaning while `CLK` is low (the front end is
simply off). `sim/dut/README.md`'s interface contract nonetheless requires a
`comparator_dut_analog` subcircuit with a DC operating point, because two of
the four benches (`comparator-offset-mc`, `comparator-preamp-noise`) are
`dc`/`.noise` analyses that need one.

`comparator_dut_analog.sch` implements DR-0001's own named interim path
(Consequence 2, itself borrowed from `sky130-sar-adc`'s DR-004): the same
tail-bias/switch/input-pair devices as the real core, but with the
cross-coupled PMOS loads (`M5`/`M6` in the core) replaced by **diode-connected**
PMOS loads (`M5A`, `M6A` — gate tied to drain, not cross-coupled) and the
tail switch's gate tied to `vdd` rather than `clk` (this sub-model has no
`clk` pin at all, per the interface contract). Diode-connecting the loads
**breaks the positive-feedback loop**, giving the pair a real, stable DC
operating point — at the cost of also removing the very mechanism
(regeneration) that determines the real design's actual offset and noise
floor.

**Consequently, any offset or noise number measured against
`comparator_dut_analog` is a lower bound on the real design's offset/noise,
not the real design's offset/noise.** It captures the input-pair and
tail-mirror mismatch/noise contributions, but excludes the regenerative
loop's own contribution entirely (by construction — the loop is broken).
This is the same caveat DR-0001 itself states and the same one `sky130-sar-adc`'s
DR-004 records for its own identical technique. Whether a future revision
re-founds `comparator-offset-mc` / `comparator-preamp-noise` on transient
Monte Carlo / transient noise instead (DR-0001 Consequence 1's alternative,
not taken by this issue) is open — see "Open items".

## Open items (named, not resolved, by this schematic)

- **Reset-integrity check.** DR-0001 Consequence 5 names the possibility
  that SG13G2's own device characteristics could reproduce the reset-phase
  instability `sky130-sar-adc`'s DR-004 Amendment A found and fixed on a
  different PDK. This schematic uses a 4-device (one per internal node)
  precharge stage, which is at least as conservative as DR-004's
  post-amendment fix; a dedicated `.op`/transient reset-integrity testbench
  across corners has not been committed here and remains future work.
- **`comparator_dut_analog` interim-vs-re-founding choice.** This issue
  takes DR-0001's diode-connected reduced-sub-model path (Consequence 2)
  rather than re-founding the offset-MC and preamp-noise benches on
  transient methodology (DR-0001 Consequence 1's alternative). That
  re-founding remains a real, not-taken option if the reduced sub-model's
  lower-bound numbers turn out to be uninformative.
- **Sizing is not gm/Id-optimized.** Device widths/lengths here are the
  round numbers DR-0001's own "Sizing rationale" section named as a
  block-diagram-level starting point (matching `sim/dut.json`'s existing
  `dut_ib`/`dut_vcm` bias convention), not the output of a gm/Id or
  noise-budget sizing study. `README.md`'s target-specification table is
  DRAFT/unratified — this issue does not claim any row is met (see
  `sim/dut/README.md` and `sim/dut.json`'s own `provenance: schematic`
  notes).

## Regenerating the netlist

```bash
python3 design/netlist.py            # writes design/comparator.spice
python3 design/netlist.py --check    # CI-style staleness check, exit nonzero if stale
```

Requires `xschem` on `PATH` and a resolvable SG13G2 PDK install (same
resolution order as `sim/harness/pdk.py`; see `sim/README.md` "Cold start").
`design/netlist.py` points `XSCHEM_USER_LIBRARY_PATH` at this directory so
xschem can resolve the hierarchical-cell symbols above (`comparator_dut.sym`
etc. live next to their `.sch`, not under the PDK's own symbol tree) — see
that script's own comments for what goes wrong without it.

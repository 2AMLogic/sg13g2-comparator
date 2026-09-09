# sim/

ngspice testbenches and append-only results.

```
sim/
  README.md              this file
  pdk.json                pinned SG13G2 PDK revision every record here traces to
  env.sh                  PDK_ROOT/PDK resolution, sourced by every testbench script
  device-mismatch-confirm/
                          issue #6: confirms SG13G2's LV MOS models carry
                          per-instance local mismatch (Monte Carlo evidence,
                          not just a PDK-model reading) -- see its own
                          README.md for the finding and methodology
```

Each experiment directory follows the append-only evidence convention: a
`testbench/` (template netlist(s)), `corners/<run-id>/` (generated
netlists + raw ngspice logs, one subdirectory per run), and
`records/<run-id>.md` (+ per-case CSVs) summarizing the result with full
provenance (PDK pin, ngspice version, seed, run count). A record is never
edited or deleted once committed — a later run adds a new `<run-id>`
rather than overwriting an old one. This mirrors `sg13g2-bandgap`'s `sim/`
convention (same PDK, same pinned release — see `pdk.json`).

Future experiments planned per `spec/porting-plan.md`'s "Next steps": a
`comparator-decision/`-equivalent (offset, decision-time-vs-overdrive,
noise, once `design/comparator.sch` exists) and a
`comparator-kickback/`-equivalent, porting methodology (not topology or
numbers) from `sky130-sar-adc` and `gf180-sar-adc` respectively.

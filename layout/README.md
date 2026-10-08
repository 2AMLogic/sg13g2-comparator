# layout/

Layout of the comparator: a generator, the GDS stream it draws, and the
one-command flow that regenerates and checks it (issue #58, T1 item 2).

| File | What it is |
|---|---|
| `comparator/comparator.gds` | **The committed stream.** One flat top cell, `comparator`, 31.46 x 76.00 um, dbu 1 nm. |
| `comparator/drc_report.json` | **Committed evidence (issue #59, T1 item 3).** The `klt drc --deck sg13g2 --top comparator` JSON envelope for the stream: `status: clean`, 0 violations. Cited by `manifests/sg13g2-comparator.json`. |
| `comparator/generate.py` | The generator. It draws the stream from a device table that it first reconciles with `design/comparator.spice`. |
| `comparator/check_stream.py` | Structural smoke test of a stream: top cell, ports, no host paths. |
| `common_sg13g2.py` | SG13G2 layer table, rule values and drawing primitives (boxes, contacts, vias). |
| `run_flow.sh` | One command that regenerates the stream and runs every check below. |

Downstream work reads the stream at `layout/comparator/comparator.gds`, top
cell `comparator`. That covers DRC #59, LVS #60, post-layout #61 and
power-delivery #38.

## Regenerating it

```bash
layout/run_flow.sh            # regenerate comparator.gds, then check it
layout/run_flow.sh --check    # leave the committed file alone; prove it reproduces
```

**Prerequisites.** You need [uv](https://docs.astral.sh/uv/) (`uvx`) and
network access to fetch the pinned tools into uv's isolated cache. The pins
are `2AMLogic/klayout-tools` @ `e8ca621a6961879cec1af60cc932c3b3d58ddcaa`
(the same pin `manifests/README.md` and CI use) and `klayout==0.30.10` (the
KLayout that klt build was tested against). Nothing is installed host-wide.
No PDK install is read: every layer number and rule value is a constant in
`common_sg13g2.py`, so the result does not depend on where, or whether, a
PDK is installed. If the pinned `klt` and `klayout` are already on `PATH`
(CI installs them with `pip`), run `KLT_NATIVE=1 layout/run_flow.sh`.

The generator alone needs only the `klayout` Python module:
`python3 layout/comparator/generate.py [-o out.gds]`.

**Stages** (`run_flow.sh`; each one fails the run on error):

1. **generate.** Before drawing, `generate.py` checks its device table
   against the `.subckt comparator` block of `design/comparator.spice`:
   - the same 24 instances, with none missing and none extra;
   - `sg13_lv_*` flavour (no ThickGateOx is drawn);
   - the same gate net, drain/source nets (as an unordered pair) and bulk;
   - the same L, and a drawn total W equal to the schematic W x m;
   - the same eight pins;
   - identical unit geometry within each matched pair.

   Any difference refuses to draw. So a schematic change the layout does not
   follow cannot regenerate silently. Each of these was checked by mutating
   the netlist: W, gate net, a dropped device, HV flavour and L were all
   refused (`--netlist` points the check at a mutated copy).
2. **reproduce.** A second run from scratch must give a byte-identical
   stream (`cmp`). The GDS is written without BGNLIB/BGNSTR timestamps and
   with a fixed shape order. Output was byte-identical on KLayout 0.30.10 and
   0.30.12, and from a checkout under a different absolute path containing
   spaces.
3. **stream.** `check_stream.py` re-reads the file and checks:
   - exactly one top cell, `comparator`, and it is non-empty;
   - each of the eight ports (`vinp vinn clk vbias dout doutb vdd vss`) has a
     `Metal3.pin` (30/2) box inside drawn Metal3 that carries a
     `Metal3.text` (30/25) label of the same name, and there are no other pins;
   - no text looks like a host path;
   - every shape is a box.
4. **connectivity self-check.** `klt extract --deck sg13g2` followed by
   `klt lvs` against the schematic, with `combine_devices` folding fingers.
   The result at the time of writing is `match`: 24/24 devices, 18/18 nets
   and 8/8 pins. This runs in a temp dir and **nothing from it is
   committed**. It checks the generator. It is **not** the LVS signoff
   evidence #60 owns.
5. **controls.** Two deliberately wrong references must give `mismatch`:
   - M3's gate rewired, which `klt lvs` reports as `device.unmatched`;
   - M1's W at 11.5u instead of 12u, which it reports as `device.property`.

   Without these, a `match` in stage 4 could not be told apart from a compare
   that sees nothing.

6. **drc.** `klt drc --deck sg13g2 --top comparator --format json` on the
   stream, run from the repo root with the repo-relative path, writing the
   committed `comparator/drc_report.json`. With `--check` it instead requires
   the committed envelope to be fresh (`klt drc --check`). The stage fails
   unless `status` is `clean`, and prints the coverage gaps (quoted in
   `manifests/README.md`).

CI runs `layout/run_flow.sh --check` on every PR. That is the
`layout-reproducibility` job in `.github/workflows/ci.yml`.

## What is drawn

Every row is centred on x = 0. From bottom to top:

| Row | Devices | Drawn as | Placement |
|---|---|---|---|
| p-tap | substrate tie, vss | contacted p+ bar | |
| R_T | MT (w=40u l=0.5u) | 8 fingers x 5.0u, merged diffusion | |
| R_SW | MSW (w=40u l=0.13u) | 8 x 5.0u, merged diffusion | |
| p-tap | vss | | |
| R_IN | M1/M2 input pair (w=12u l=0.34u) | 2 unit cells each, 4 x 3.0u | A B B A common centroid |
| R_LN | M3/M4 NMOS latch (w=3u) | 2 unit cells each, 4 x 0.75u | A B B A common centroid |
| p-tap | vss | | |
| n-tap | vdd, inside the one NWell | contacted n+ bar | |
| R_LP | M5/M6 PMOS latch (w=3u) | 2 unit cells each, 4 x 0.75u | A B B A common centroid |
| R_RST | M7/M8 (w=6u), M9/M10 (w=3u) reset | M7/M8: 2 cells, 4 x 1.5u; M9/M10: 1 cell, 2 x 1.5u | M9 M7 M8 M8 M7 M10: M7/M8 common centroid, M9/M10 mirror |
| R_OP | output PMOS: MIAP/MIBP, NOR pull-ups MNAP1/2, MNBP1/2 | one finger each, as in the schematic | mirror-symmetric (A half / B half) |
| n-tap | vdd | | |
| p-tap | vss | | |
| R_ON | output NMOS: MIAN/MIBN, MNAN1/2, MNBN1/2 | one finger each | mirror-symmetric |
| p-tap | vss | | |

The extractor therefore sees 38 nfet + 26 pfet *fingers*.
`klt lvs --combine_devices` folds them back into the schematic's 24 devices.

**Matching strategy.** This is the part to review, because offset sigma is a
ratified row.

- **Unit cells.** Every matched device is built from identical unit cells.
  A unit cell is one Activ island with two fingers sharing a central drain:
  source | gate | drain | gate | source. Islands are never merged with their
  neighbours. So every finger of A and of B has the same length of
  diffusion, the same contacts and the same neighbouring-poly distance. A
  merged ABBA strip would give the outer devices an Activ edge the inner
  ones do not have.
- **Edge dummies.** At each end of a matched row, a field-poly stripe sits
  where the next unit's outer gate would be. The end units then see the same
  poly neighbourhood as the inner ones.
- **Common centroid.** M1/M2, M3/M4, M5/M6 and M7/M8 are placed A B B A, so
  both devices' width-weighted gate centroids are at x = 0. `generate.py`
  computes this from the drawn fingers and fails if it is not exact; it
  prints the centroids. This cancels a linear gradient along x only. It is
  1-D: there is no cross-quad, so a gradient along y is not cancelled.
  M9/M10 have one cell each and are placed mirror-symmetrically (x = -5.4 /
  +5.4 um).
- **Mirrored routing.** Gate nets ride horizontal Metal2 buses below each row
  and source/drain nets ride horizontal Metal2 buses above it. Nets cross
  between rows on vertical Metal3 tracks. The A-side nets (vinp, np, ln, lnb,
  doutb) have their tracks in the left channel. Their B-side mirrors (vinn,
  nn, lp, lpb, dout) have tracks at the same distance in the right channel.
  `clk`, `vss` and `vdd` have tracks on both sides. In the four matched rows
  every bus spans the same full width, so the A and B buses have equal
  length.
- **Residual asymmetry, not hidden.** Within a row, A and B occupy different
  bus *levels*, 0.70 um apart. So one side's M1 drain strap or gate stub is
  0.70 um longer per finger than the other's. That is a small capacitance
  mismatch on np/nn and ln/lp, and between the vinp and vinn gate
  connections. Post-layout extraction (#61) should quantify it rather than
  assume it away.

## What this layout is, and is not

- **No PDK PCells.** Devices are drawn from base layers (Activ, GatPoly,
  Cont, pSD/nSD, NWell, Metal1-3, Via1-2), with the device-defining
  dimensions exact (W per finger, L) and the rule values listed in
  `common_sg13g2.py`. That follows the `2AMLogic/sg13g2-ldo` generator
  pattern. It does not reproduce every detail of IHP's PCells.
- **Finger split.** Except for the output stage, devices are drawn
  multi-finger where the schematic declares `ng=1` (see the table above).
  Total W and L match exactly. But a 4 x 0.75u device is not electrically
  identical to a 1 x 3u one: it differs in junction area/perimeter,
  length-of-diffusion and narrow-width behaviour. The schematic-level
  results under `sim/` assumed single fingers. This is a layout decision for
  matching, and its electrical cost is #61's to measure.
- **DRC.** The stream is clean against klt's *curated* `sg13g2` deck at the
  pinned build: 0 violations, committed as `comparator/drc_report.json`
  (stage 6). That deck covers a subset of the rules: width, space and
  enclosure for Activ, GatPoly, Cont, Metal1-5 and vias. Its stated coverage
  gaps (layers drawn without rules, skipped rules, deck scope) are quoted in
  `manifests/README.md`. Rules it does not check were drawn with margin, from
  IHP's SG13G2 layout rules as cited in `common_sg13g2.py`. These include:
  - Gat.c endcap;
  - Cnt.e and Cnt.f;
  - pSD enclosure;
  - NWell enclosure and spacing;
  - latch-up tap distance.

  None of these has been checked by the PDK's own deck, and there is no
  density fill or seal ring.
- **Connectivity.** The `match` in stage 4 is a self-check of this
  generator against the schematic. LVS signoff, with a committed envelope,
  is #60.
- **Bodies.** NMOS bodies are the substrate, tied to vss by five p-tap bars.
  PMOS bodies are one NWell, tied to vdd by two n-tap bars. There are no
  guard rings around the input pair or the latch.
- **Labels.** Besides the eight ports, every routed internal net carries a
  `Metal3.text` label (np, nn, ln, lp, lnb, lpb, tail, tmid). Extraction
  therefore names them, which helps debugging. Pass `--pins
  vinp,vinn,clk,vbias,dout,doutb,vdd,vss` to `klt extract` to keep only
  the real ports as pins. The series-stack nodes `na`/`nb` are shared
  diffusion with no contact and extract as anonymous nets.
- **Pins.** Each port has one pin, on the edge its track reaches.
  - Bottom edge: `vinp`, `vinn`, `vbias`, `vss`.
  - Top edge: `clk`, `doutb`, `dout`, `vdd`.

  `clk`, `vss` and `vdd` are pinned on their left track only. The right
  tracks are the same nets, joined through the buses and tap bars.

## Known tool friction

- `klt lvs` crashes when the reference file also contains subcircuits that
  instantiate the selected top. `design/comparator.spice` does: its
  `comparator_dut*` wrappers instantiate `comparator`. The tool gap is filed
  generically as
  [2AMLogic/klayout-tools#2852](https://github.com/2AMLogic/klayout-tools/issues/2852).
  `run_flow.sh` works around it by cutting the `.subckt comparator` block
  into its own temp file.

## Manifest citation (T1 item 2)

[klayout-tools#2718](https://github.com/2AMLogic/klayout-tools/issues/2718)
landed upstream (PR #2843, `3a75c3ae`). It added the artifact-anchored
generic evidence that lets `klt signoff` bind item 2 to this stream. This
repo's pinned build (`e8ca621`) predates it. Bumping that pin moves the
whole frozen report and is the first acceptance criterion of #65. So
`manifests/sg13g2-comparator.json` does not cite item 2 yet. The citation
belongs with, or right after, that pin bump.

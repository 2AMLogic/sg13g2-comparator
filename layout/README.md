# layout/

Layout of the comparator: a generator, the GDS stream it draws, and the
one-command flow that regenerates and checks it (issue #58, T1 item 2).

| File | What it is |
|---|---|
| `comparator/comparator.gds` | **The committed stream.** One flat top cell, `comparator`, 31.46 x 76.00 um, dbu 1 nm. |
| `comparator/drc_report.json` | **Committed evidence (issue #59, T1 item 3).** The `klt drc --deck sg13g2 --top comparator` JSON envelope for the stream: `status: clean`, 0 violations. Cited by `manifests/sg13g2-comparator.json`. |
| `comparator/erc_supply_spec.json`, `comparator/erc_report.json` | **Committed evidence (issue #38, T1 item 11).** The `klt erc` supply-spec request and its JSON envelope for the stream: 0 findings, nothing skipped. Cited, together with `lvs_report.json`, by `manifests/sg13g2-comparator.json`. |
| `comparator/erc_tool.py` | Derives the ERC request from `common_sg13g2.py`, judges envelopes, and builds the broken temp fixtures of the negative controls. |
| `comparator/generate.py` | The generator. It draws the stream from a device table that it first reconciles with `design/comparator.spice`. |
| `comparator/check_stream.py` | Structural smoke test of a stream: top cell, ports, no host paths. |
| `common_sg13g2.py` | SG13G2 layer table, rule values and drawing primitives (boxes, contacts, vias). |
| `run_flow.sh` | One command that regenerates the stream and runs every check below. |

Downstream work reads the stream at `layout/comparator/comparator.gds`, top
cell `comparator`. That covers DRC #59, LVS #60, post-layout #61 and
power-delivery #38 (stage 7).

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
4. **lvs.** `klt extract --deck sg13g2 --top comparator --pins <8 ports>`
   followed by `klt lvs` against the `.subckt comparator` block cut verbatim
   out of `design/comparator.spice` (never edited by hand), with
   `combine_devices` folding fingers and `reference.form: subckt-call`,
   `reference.deck: sg13g2`. This is the T1 item 4 evidence. It writes, all
   under `layout/comparator/` and all derived:

   | file | content |
   |---|---|
   | `lvs_extracted.spice` | the extracted netlist (layout side) |
   | `lvs_reference.spice` | the cut-out comparator subcircuit (reference side) |
   | `lvs_request.json` | the `klt.lvs.request/1` document; netlist paths are relative to the request file, so nothing is host-absolute |
   | `lvs_report.json` | the `klt lvs` envelope that the manifest cites |

   Result: `status: match`, engine `klayout` 0.30.10, 24/24 devices, 18/18
   nets, 8/8 pins (`vinp vinn clk vbias dout doutb vdd vss`, including the
   independent `vbias` pin and `vdd`/`vss`, each with an identical
   layout/reference entry in `net_correspondence`, which item 11 cites next to
   the stage 7 ERC envelope),
   0 mismatches, 0 warnings.

   Limits of the verdict, stated plainly:
   - `power_connectivity.status` is `unchecked`: with `subckt-call` the
     reference carries its own power pins, which take part in the ordinary
     compare, so the signal-only power check does not apply. This is **not** a
     geometric power-grid verification; `vdd`/`vss` are verified only as
     compared nets with matching device connectivity.
   - `body_verification.status` is `unchecked` (pre-extracted netlist form, so
     no deck establishes the tap convention). Body connections are not
     verified by this evidence.
   - Supply geometry is checked by stage 7 (ERC, #38); post-layout (parasitic)
     simulation is separate work (#61).
   - `provenance.input.content_hash` (the value the manifest pins) is the
     hash of the extracted netlist only. The tool does not tie it to the GDS
     or to `design/comparator.spice`, so `--check` proves those links itself
     (below).

   With `--check` the stage requires, in order: a fresh extraction and a fresh
   reference cut to be byte-identical (`cmp`) to the committed
   `lvs_extracted.spice` / `lvs_reference.spice` / `lvs_request.json` (so a
   changed GDS, schematic subcircuit or request fails); `klt lvs --check`
   (netlist hashes still match the envelope); a fresh run of the committed
   request to equal the committed envelope; and the verdict to be a complete
   match (non-empty, no `error` envelope, `status: match`, engine named,
   power verdict not `mismatch`, zero mismatches, 8/8 pins, 24/24 devices,
   all nets, the eight pins corresponding by name, no host path). An empty or
   error envelope fails.
5. **controls.** Two deliberately wrong references must give `mismatch`:
   - M3's gate rewired, which `klt lvs` reports as `device.unmatched`;
   - M1's W at 11.5u instead of 12u, which it reports as `device.property`.

   Without these, a `match` in stage 4 could not be told apart from a compare
   that sees nothing. They run in a temp dir; nothing from them is committed,
   and an empty or error report does not count as a mismatch.

6. **drc.** `klt drc --deck sg13g2 --top comparator --format json` on the
   stream, run from the repo root with the repo-relative path, writing the
   committed `comparator/drc_report.json`. With `--check` it instead requires
   the committed envelope to be fresh (`klt drc --check`). The stage fails
   unless `status` is `clean`, and prints the coverage gaps (quoted in
   `manifests/README.md`).

7. **erc.** `klt erc --deck sg13g2 --top comparator --findings-only` with the
   request `comparator/erc_supply_spec.json`, run from the repo root. This is
   the T1 item 11 evidence (with the stage 4 LVS report). The request is
   *derived*: `comparator/erc_tool.py spec` prints it from the layer table in
   `common_sg13g2.py`, the constants `generate.py` draws with, so no layer
   number is typed twice and `--check` fails if the committed request drifts.

   | declaration | content |
   |---|---|
   | conductors | GatPoly 5/0 (gate role), Metal1 8/0, Metal2 10/0, Metal3 30/0 (labels from Metal3.text 30/25) |
   | vias | Cont 6/0 (GatPoly-Metal1), Via1 19/0, Via2 29/0 |
   | `vdd`, `vss` | `kind: supply`. The two supplies of the eight-port `.subckt comparator` in `design/comparator.spice`; no other supply port exists. |
   | `vbias` | `kind: signal`, **not a supply**. It is an independent bias input port with its own Metal3 pin and its own LVS pin pair; this top does not tie it to vdd (that tie exists only in the `comparator_dut_latch` test wrapper). It is checked as one island that is not shorted to a supply. |
   | tie `nwell_vdd` | well = NWell 31/0; tap = Activ 1/0 & nSD 7/0 & Cont 6/0, i.e. the contacts on the n-tap bars; reaches Metal1; net `vdd` |

   The tie is *checked*, not degenerate: only the n-tap bars carry nSD (the
   PMOS rows carry pSD, the NMOS rows neither), so the narrowing removes the
   source/drain contacts and the run's `erc_coverage.skipped` is empty.

   Result: `erc_status: clean`, 0 findings. `vdd`, `vss` and `vbias` each
   resolve to one island, and the `nwell_vdd` tie is in `erc_coverage.checked`.

   Limits, stated plainly:
   - `klt erc` has no substrate layer to hang a tie on, so the committed
     request declares **no p-tap (substrate) tie**. The flow checks it in a
     temp fixture instead (below); that is a flow check, not cited evidence.
   - Diffusion and well are not conductors in the model. `vdd`/`vss`
     continuity is through contacts, Metal1-3 and vias only (klayout-tools
     #2180 caveat). Each supply already resolves to one island without
     diffusion, so the caveat's false positive does not occur here, and LVS (stage 4) independently matches
     the same devices and nets.
   - Taps are modelled at their contacts joined to Metal1, so a tap whose
     contacts do not land on Metal1 would be reported.
   - The `status` of the envelope is `not_checked`: `--findings-only`
     skips the antenna accumulation and `sg13g2` has no antenna table in the
     pinned `klt`. Item 11 does not grade `status`. Antenna is not claimed.
   - No `devices[]` carve-out is declared (`provenance.devices` is empty): the
     comparator has no poly resistor, MiM or other body spanning a rail pair.
   - `klt erc` has no `--check`, so freshness is checked by this flow:
     `--check` requires the request and a fresh run to reproduce the
     committed files byte-for-byte. `provenance.input.content_hash` (pinned
     by the manifest) is the GDS hash, the same value item 3 pins.

   Negative controls (temp copies of the stream only; committed geometry is
   never edited), each of which MUST give the named result:

   | mutation | expected |
   |---|---|
   | every Via2 under the leftmost vdd track removed | `erc.unconnected_net` |
   | Metal3 strap between the vdd and vss tracks | `erc.supply_short` |
   | nSD removed | `erc.missing_tie` |
   | `tap_requires` omitted from the tie | `erc_coverage.skipped` reason `degenerate_tap_declaration` |
   | substrate fixture with pSD removed | `erc.missing_tie` |

   The substrate fixture adds a scratch layer (200/0, standing for
   "everything outside NWell") to a temp stream and declares tie
   `psub_vss` = Activ & pSD & Cont on `vss`. Unmutated it must be clean with
   the tie checked: every p-tap bar reaches vss.

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
- **Connectivity.** Stage 4 is the committed LVS evidence (#60); see its
  limits above (power and body verdicts `unchecked`).
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
  into the committed `lvs_reference.spice`, derived deterministically from
  `design/comparator.spice` on every run and compared byte-for-byte in
  `--check`.
- `klt lvs --check --rerun` cannot replay a `subckt-call` report (the
  envelope does not echo `reference.form`); the flow uses cheap `--check`
  plus its own fresh-run comparison instead. Filed generically as
  [2AMLogic/klayout-tools#2907](https://github.com/2AMLogic/klayout-tools/issues/2907).

## Manifest citation (T1 item 2)

[klayout-tools#2718](https://github.com/2AMLogic/klayout-tools/issues/2718)
landed upstream (PR #2843, `3a75c3ae`). It added the artifact-anchored
generic evidence that lets `klt signoff` bind item 2 to this stream. This
repo's pinned build (`e8ca621`) predates it. Bumping that pin moves the
whole frozen report and is the first acceptance criterion of #65. So
`manifests/sg13g2-comparator.json` does not cite item 2 yet. The citation
belongs with, or right after, that pin bump.

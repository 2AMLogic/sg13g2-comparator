#!/usr/bin/env python3
"""Helpers for the supply-spec ERC stage of ``layout/run_flow.sh`` (issue #38).

    erc_tool.py spec                       print the klt erc request (JSON)
    erc_tool.py judge REPORT               accept a committed/fresh envelope
    erc_tool.py judge REPORT --expect K    negative control: require finding K
    erc_tool.py mutate KIND IN.gds OUT.gds [SPEC_OUT]
                                           write a broken temp copy of the GDS

``spec`` derives the request from ``layout/common_sg13g2.py``'s layer table,
the same constants ``generate.py`` draws with, so no layer number is typed
twice. The request declares:

* ``vdd`` and ``vss`` as ``kind: supply`` nets (the two supplies of the
  ``.subckt comparator`` ports in ``design/comparator.spice``);
* ``vbias`` as a ``kind: signal`` net: it is an independent bias *input
  port* (a pin of its own, not tied to vdd in this top), so it is checked
  only as one island and as not shorted to a supply, never as a supply;
* one n-well tie: well = NWell, tap = Activ ∩ nSD ∩ Cont on ``vdd``. Only
  the generator's n-tap bars carry nSD (the PMOS rows carry pSD, the NMOS
  rows carry neither), so the narrowing removes the PMOS/NMOS source-drain
  diffusion and the tie is *checked*, not degenerate. Taps are modelled at
  their contacts and wired to Metal1.

klt erc has no substrate layer, so the p-tap (substrate) tie is not part of
the committed request; ``mutate substrate-fixture`` builds a temp-only
stream with a synthetic scratch layer for the substrate region (everything
outside NWell) so the flow can still check that every p-tap reaches vss.
"""

from __future__ import annotations

import json
import pathlib
import sys

import klayout.db as kdb

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import common_sg13g2 as c  # noqa: E402

TOP = "comparator"
#: Scratch layer used only in temp fixtures (never in a committed stream).
SCRATCH = (200, 0)


def lay(layer: tuple[int, int]) -> str:
    return f"{layer[0]}/{layer[1]}"


def build_spec(substrate: bool = False) -> dict:
    ties = [{
        "name": "nwell_vdd", "well_layer": lay(c.L_NWELL), "tap_layer": lay(c.L_ACTIV),
        "tap_requires": [lay(c.L_NSD), lay(c.L_CONT)], "connect_to": "Metal1", "net": "vdd",
    }]
    if substrate:
        ties.append({
            "name": "psub_vss", "well_layer": lay(SCRATCH), "tap_layer": lay(c.L_ACTIV),
            "tap_requires": [lay(c.L_PSD), lay(c.L_CONT)], "connect_to": "Metal1", "net": "vss",
        })
    return {
        "stackup": [
            {"name": "GatPoly", "layer": lay(c.L_GATPOLY), "role": "gate",
             "active_layer": lay(c.L_ACTIV)},
            {"name": "Metal1", "layer": lay(c.L_METAL1)},
            {"name": "Metal2", "layer": lay(c.L_METAL2)},
            {"name": "Metal3", "layer": lay(c.L_METAL3), "label_layer": lay(c.L_METAL3_TEXT)},
        ],
        "vias": [
            {"name": "Cont", "layer": lay(c.L_CONT), "between": ["GatPoly", "Metal1"]},
            {"name": "Via1", "layer": lay(c.L_VIA1), "between": ["Metal1", "Metal2"]},
            {"name": "Via2", "layer": lay(c.L_VIA2), "between": ["Metal2", "Metal3"]},
        ],
        "nets": [
            {"name": "vdd", "kind": "supply"},
            {"name": "vss", "kind": "supply"},
            {"name": "vbias", "kind": "signal"},
        ],
        "ties": ties,
    }


def dump(spec: dict) -> str:
    return json.dumps(spec, indent=2) + "\n"


# --------------------------------------------------------------------------- #
def judge(path: str, expect: str | None) -> int:
    d = json.loads(pathlib.Path(path).read_text())
    if "error" in d or "erc_findings" not in d:
        print(f"  FAIL: {path}: error/odd envelope: {str(d)[:300]}", file=sys.stderr)
        return 1
    rules = sorted({f["rule"] if "rule" in f else f.get("id", "?") for f in d["erc_findings"]})
    cov = d["erc_coverage"]
    skipped = [s["reason"] for s in cov["skipped"]]
    if expect:
        hit = expect in json.dumps(d["erc_findings"]) or expect in skipped
        print(f"  {expect}: findings={rules} skipped={skipped}")
        return 0 if hit else 1
    bad = []
    if d["erc_status"] != "clean" or d["erc_finding_count"]:
        bad.append(f"erc_status {d['erc_status']}, findings {rules}")
    if skipped:
        bad.append(f"erc_coverage.skipped {cov['skipped']}")
    want = {'erc.net_connectivity:["vdd"]', 'erc.net_connectivity:["vss"]',
            'erc.net_connectivity:["vbias"]', 'erc.missing_tie:["nwell_vdd"]'}
    if not want <= set(cov["checked"]):
        bad.append(f"checked work missing: {sorted(want - set(cov['checked']))}")
    if d["file"].startswith("/") or "/home/" in json.dumps(d):
        bad.append("host-absolute path in envelope")
    if d["provenance"]["devices"]:
        bad.append("unexpected devices[] carve-out")
    if bad:
        print("  FAIL: " + "; ".join(bad), file=sys.stderr)
        return 1
    print(f"  erc_status: {d['erc_status']}, findings: 0, skipped: 0, "
          f"checked: {len(cov['checked'])} (vdd, vss, vbias islands; nwell_vdd tie)")
    return 0


# --------------------------------------------------------------------------- #
def mutate(kind: str, src: str, dst: str, spec_out: str | None) -> int:
    ly = kdb.Layout()
    ly.read(src)
    top = ly.cell(TOP)

    def li(layer):
        return ly.layer(kdb.LayerInfo(layer[0], layer[1]))

    def boxes(layer):
        return [(s, s.box) for s in top.shapes(li(layer)).each() if s.is_box()]

    def track(net):  # leftmost Metal3 box carrying a `net` label
        texts = [s.text for s in top.shapes(li(c.L_METAL3_TEXT)).each() if s.is_text()]
        pts = [t.trans.disp for t in texts if t.string == net]
        hits = [b for _, b in boxes(c.L_METAL3) if any(b.contains(kdb.Point(p.x, p.y)) for p in pts)]
        if not hits:
            raise SystemExit(f"no Metal3 track labelled {net}")
        return min(hits, key=lambda b: b.left)

    spec = build_spec()
    if kind == "broken-supply":
        # Sever the leftmost vdd Metal3 track from the rest: drop every Via2 under it.
        t = track("vdd")
        n = 0
        for s, b in boxes(c.L_VIA2):
            if b.inside(t):
                s.delete(); n += 1
        if not n:
            raise SystemExit("broken-supply: no Via2 under the vdd track")
    elif kind == "supply-short":
        # A Metal3 strap from the leftmost vdd track to the leftmost vss track.
        a, b = track("vdd"), track("vss")
        y = (a.bottom + a.top) // 2
        top.shapes(li(c.L_METAL3)).insert(
            kdb.Box(min(a.left, b.left), y - 500, max(a.right, b.right), y + 500))
    elif kind == "no-tap-implant":
        # Remove the nSD implant: the n-tap bars stop being taps.
        top.shapes(li(c.L_NSD)).clear()
    elif kind == "degenerate-tap":
        # Same geometry, but a tap declaration with no narrowing.
        spec["ties"][0]["tap_requires"] = []
    elif kind in ("substrate-fixture", "substrate-no-implant"):
        # Synthetic scratch layer = bbox minus NWell: the substrate region.
        bbox = kdb.Region(top.bbox().enlarged(2000, 2000))
        nwell = kdb.Region(top.begin_shapes_rec(li(c.L_NWELL)))
        top.shapes(ly.layer(kdb.LayerInfo(SCRATCH[0], SCRATCH[1]))).insert(bbox - nwell)
        spec = build_spec(substrate=True)
        if kind == "substrate-no-implant":  # p-taps lose their pSD: no substrate tap
            top.shapes(li(c.L_PSD)).clear()
    else:
        raise SystemExit(f"unknown mutation {kind}")
    opts = kdb.SaveLayoutOptions()
    opts.format = "GDS2"
    opts.gds2_write_timestamps = False
    ly.write(dst, opts)
    if spec_out:
        pathlib.Path(spec_out).write_text(dump(spec))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == "spec":
        sys.stdout.write(dump(build_spec()))
        return 0
    if len(argv) >= 2 and argv[0] == "judge":
        return judge(argv[1], argv[3] if len(argv) >= 4 and argv[2] == "--expect" else None)
    if len(argv) >= 4 and argv[0] == "mutate":
        return mutate(argv[1], argv[2], argv[3], argv[4] if len(argv) > 4 else None)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

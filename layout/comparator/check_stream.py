#!/usr/bin/env python3
"""Structural smoke test for a comparator GDS stream (issue #58).

    python3 layout/comparator/check_stream.py [layout/comparator/comparator.gds]

Re-reads the stream from disk with ``klayout.db`` and asserts, failing loudly:

* exactly one top cell, named ``comparator``, with a non-empty bounding box;
* every one of the eight schematic ports has a ``Metal3.pin`` (30/2) box that
  carries a ``Metal3.text`` (30/25) label of the same name and lies inside
  drawn ``Metal3`` (30/0) -- and there is no pin box for anything else;
* no text in the stream looks like a host path (committed artifacts must not
  carry machine-local provenance);
* every non-text shape is a box (the generator draws nothing else).

Device count and connectivity are not checked here: ``run_flow.sh`` checks
them by extracting the stream with ``klt extract`` and comparing it with
``klt lvs`` (a self-check, not the LVS signoff of issue #60).
"""

from __future__ import annotations

import pathlib
import sys

import klayout.db as kdb

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from generate import PORTS, TOP_CELL  # noqa: E402

PIN, TEXT, METAL = (30, 2), (30, 25), (30, 0)


def main(path: pathlib.Path) -> int:
    ly = kdb.Layout()
    ly.read(str(path))
    errors: list[str] = []

    tops = [c.name for c in ly.top_cells()]
    if tops != [TOP_CELL]:
        errors.append(f"top cells {tops}, expected exactly [{TOP_CELL!r}]")
        top = ly.top_cell() if tops else None
    else:
        top = ly.cell(TOP_CELL)
    if top is None or top.bbox().empty():
        errors.append("top cell is empty")
        return _report(errors, path)

    def idx(ld: tuple[int, int]) -> int | None:
        i = ly.find_layer(ld[0], ld[1])
        return i if i is not None and i >= 0 else None

    metal = kdb.Region(top.begin_shapes_rec(idx(METAL))) if idx(METAL) is not None else kdb.Region()
    metal.merge()
    pins = [s.box for s in top.shapes(idx(PIN)).each()] if idx(PIN) is not None else []
    texts = [s.text for s in top.shapes(idx(TEXT)).each() if s.is_text()] if idx(TEXT) is not None else []

    found: dict[str, int] = {}
    for box in pins:
        names = {t.string for t in texts if box.contains(t.trans.disp.to_p())}
        if len(names) != 1:
            errors.append(f"pin box {box} carries labels {sorted(names)}, expected exactly one")
            continue
        name = names.pop()
        found[name] = found.get(name, 0) + 1
        if not (kdb.Region(box) - metal).is_empty():
            errors.append(f"pin {name}: pin box {box} is not inside drawn Metal3")
    missing = sorted(set(PORTS) - set(found))
    extra = sorted(set(found) - set(PORTS))
    if missing:
        errors.append(f"ports without a pin: {missing}")
    if extra:
        errors.append(f"pins that are not schematic ports: {extra}")

    for li in ly.layer_indexes():
        for s in top.shapes(li).each():
            if s.is_text():
                t = s.text.string
                if "/" in t or "\\" in t or t.startswith("~"):
                    errors.append(f"text {t!r} looks like a path")
            elif not s.is_box():
                errors.append(f"non-box shape on {ly.get_info(li)}: {s}")

    if not errors:
        b = top.dbbox()
        print(f"  stream ok: top={TOP_CELL} bbox={b.width():.2f}x{b.height():.2f} um, "
              f"pins={' '.join(p for p in PORTS)}")
    return _report(errors, path)


def _report(errors: list[str], path: pathlib.Path) -> int:
    for e in errors:
        print(f"  FAIL {path.name}: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "comparator.gds"
    sys.exit(main(target))

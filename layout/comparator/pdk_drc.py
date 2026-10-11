#!/usr/bin/env python3
"""Supplemental physical-rule check against the PDK's own DRC deck (issue #180).

    pdk_drc.py [--pdk DIR] [--klayout BIN] [-o REPORT] [--check] [--strict]
               [--no-controls] [GDS]

Runs the committed ``comparator.gds`` through IHP's own KLayout rule deck
(``libs.tech/klayout/tech/drc/run_drc.py`` of IHP-Open-PDK, pinned by
``sim/pdk.json``: release v0.3.0), as a *second* check beside klt's curated
``sg13g2`` deck (``layout/run_flow.sh`` stage 6). It does not replace or edit
that verdict, and it never modifies the GDS.

Exit status:

* ``0``  the run completed and the report was written/verified. The report's
         ``status`` may still be ``violations``: findings are evidence, not a
         tool failure. ``--strict`` makes ``violations`` exit ``1``.
* ``1``  tool error, a failed negative control, or (``--check``) a stale
         committed report.
* ``3``  ``unavailable``: a prerequisite is missing (PDK deck, deck identity,
         KLayout binary >= 0.29.11). An unavailable result is never clean, is
         never written over the committed report, and always exits non-zero.

The report is deterministic: no timestamps, no host paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import klayout.db as kdb

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))

import common_sg13g2 as c  # noqa: E402

SCHEMA = "sg13g2-comparator.pdk-drc/1"
TOP = "comparator"
DEFAULT_GDS = HERE / "comparator.gds"
DEFAULT_REPORT = HERE / "pdk_drc_report.json"
SIM_PDK_JSON = REPO / "sim" / "pdk.json"

#: IHP-Open-PDK release this repo pins (sim/pdk.json) and what the installed
#: checkout's ``.fetched-version`` must read.
PDK_RELEASE_TAG = "v0.3.0"
PDK_FETCHED_VERSION = "0.3.0"
#: sha256 over the deck tree (see ``deck_tree_sha256``) of that release.
DECK_TREE_SHA256 = "e4a00632d87db2c9b9eef40575f1fc05bf84b9abad659068ae06ac57f9bdcc94"
DECK_REL = "libs.tech/klayout/tech/drc"
MIN_KLAYOUT = (0, 29, 11)  # the deck's own check_klayout_version()
THREADS = 2  # shared host: never more than 2

#: Rules layout/README.md discloses as never checked by the PDK deck, plus
#: the neighbouring pSD/NWell/latch-up rules. Each is reported individually.
TARGETED = (
    "Gat.c", "Cnt.e", "Cnt.f",
    "pSD.a", "pSD.b", "pSD.c", "pSD.c1", "pSD.d", "pSD.e", "pSD.i",
    "NW.a", "NW.b", "NW.b1", "NW.d", "NW.e", "NW.f1",
    "LU.a", "LU.b", "LU.c",
)

def drawn_layers(gds: pathlib.Path) -> list[str]:
    """Layer/datatype pairs that carry shapes in the stream itself."""
    ly = kdb.Layout()
    ly.read(str(gds))
    top = ly.cell(TOP)
    out = []
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        if not top.shapes(li).is_empty():
            name = c.LAYER_NAMES.get((info.layer, info.datatype))
            out.append(f"{info.layer}/{info.datatype}" + (f" {name}" if name else ""))
    return sorted(out, key=lambda x: tuple(int(v) for v in x.split()[0].split("/")))


class Unavailable(Exception):
    """A prerequisite is missing; the result is 'unavailable', never clean."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def deck_files(pdk: pathlib.Path) -> list[pathlib.Path]:
    root = pdk / DECK_REL
    skip = {"testing", "docs", "images", "__pycache__"}
    out = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and not (set(rel.parts) & skip) and p.suffix != ".pyc":
            out.append(p)
    return out


def deck_tree_sha256(pdk: pathlib.Path) -> str:
    """sha256 over ``<relpath>\\0<file sha256>\\n`` lines of the sorted deck
    tree (everything under ``libs.tech/klayout/tech/drc`` except docs, images
    and the PDK's own regression harness)."""
    root = pdk / DECK_REL
    h = hashlib.sha256()
    for p in deck_files(pdk):
        h.update(f"{p.relative_to(root).as_posix()}\0{sha256_file(p)}\n".encode())
    return h.hexdigest()


def find_pdk(arg: str | None) -> pathlib.Path:
    cands = []
    if arg:
        cands.append(pathlib.Path(arg))
    if os.environ.get("IHP_PDK_DIR"):
        cands.append(pathlib.Path(os.environ["IHP_PDK_DIR"]))
    if os.environ.get("PDK_ROOT"):
        cands.append(pathlib.Path(os.environ["PDK_ROOT"]) / "ihp-sg13g2")
    cands.append(pathlib.Path.home() / "share" / "pdk" / "ihp-sg13g2")
    for p in cands:
        if (p / DECK_REL / "run_drc.py").is_file():
            return p
    raise Unavailable(
        "pdk_deck_missing",
        "no IHP-Open-PDK ihp-sg13g2 checkout with "
        f"{DECK_REL}/run_drc.py (looked at --pdk, $IHP_PDK_DIR, "
        "$PDK_ROOT/ihp-sg13g2, ~/share/pdk/ihp-sg13g2)",
    )


def klayout_version(binary: str) -> tuple[tuple[int, ...], str]:
    try:
        out = subprocess.run(
            [binary, "-b", "-v"], capture_output=True, text=True, timeout=60
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        raise Unavailable("klayout_binary_missing", f"{binary}: {e}") from e
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?\s*$", out)
    if not m:
        raise Unavailable("klayout_binary_missing", f"unparseable version {out!r}")
    ver = tuple(int(x or 0) for x in m.groups())
    return ver, ".".join(str(x) for x in ver)


def resolve_prereqs(pdk_arg, klayout_arg):
    pdk = find_pdk(pdk_arg)
    fv = (pdk / ".fetched-version").read_text().strip() if (pdk / ".fetched-version").is_file() else ""
    if fv != PDK_FETCHED_VERSION:
        raise Unavailable(
            "deck_identity_mismatch",
            f".fetched-version is {fv!r}, sim/pdk.json pins {PDK_FETCHED_VERSION!r}",
        )
    tree = deck_tree_sha256(pdk)
    if tree != DECK_TREE_SHA256:
        raise Unavailable(
            "deck_identity_mismatch",
            f"deck tree sha256 {tree} != pinned {DECK_TREE_SHA256}",
        )
    binary = klayout_arg or os.environ.get("KLAYOUT_BIN") or shutil.which("klayout")
    if not binary:
        raise Unavailable(
            "klayout_binary_missing",
            "no `klayout` executable (set KLAYOUT_BIN or --klayout); the pip "
            "`klayout` wheel is a Python module only and cannot run the Ruby deck",
        )
    ver, ver_s = klayout_version(binary)
    if ver < MIN_KLAYOUT:
        raise Unavailable(
            "klayout_too_old",
            f"{binary} is {ver_s}; the deck requires >= "
            + ".".join(map(str, MIN_KLAYOUT)),
        )
    return pdk, binary, ver_s, fv, tree


# --------------------------------------------------------------------------- #
# Running the deck
# --------------------------------------------------------------------------- #
def run_deck(pdk: pathlib.Path, binary: str, gds: pathlib.Path, workdir: pathlib.Path):
    """Run the PDK's run_drc.py (main + maximal sets, density off) on ``gds``.

    Returns the parsed lyrdb: (executed {rule: description},
    violations {rule: [marker strings]}).
    """
    shim = workdir / "bin"
    shim.mkdir(parents=True)
    (shim / "klayout").symlink_to(pathlib.Path(binary).resolve())
    env = dict(os.environ, PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
    run_dir = workdir / "run"
    cmd = [
        sys.executable,
        str(pdk / DECK_REL / "run_drc.py"),
        f"--path={gds}",
        f"--run_dir={run_dir}",
        f"--topcell={TOP}",
        "--run_mode=deep",
        "--no_density",
        "--mp=1",
        f"--density_thr={THREADS}",
    ]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=workdir)
    dbs = sorted(run_dir.glob("*_full.lyrdb")) if run_dir.is_dir() else []
    logs = sorted(run_dir.glob("*.log")) if run_dir.is_dir() else []
    done = [p for p in logs if p.name != run_dir.name + ".log"
            and "completed in" in p.read_text(errors="replace")]
    if len(dbs) != 1 or len(done) < 2:
        raise RuntimeError(
            "PDK deck did not complete (expected one merged lyrdb and the main + "
            f"maximal logs finished; got {len(dbs)} lyrdb, {len(done)} finished logs)\n"
            + (proc.stdout + proc.stderr)[-2000:]
        )
    return parse_lyrdb(dbs[0])


def parse_lyrdb(path: pathlib.Path):
    root = ET.parse(path).getroot()
    executed = {}
    for cat in root.find("categories"):
        name = (cat.findtext("name") or "").strip("'")
        executed[name] = " ".join((cat.findtext("description") or "").split())
    violations: dict[str, list[str]] = {}
    for item in root.find("items"):
        rule = (item.findtext("category") or "").strip("'")
        vals = [" ".join((v.text or "").split()) for v in item.find("values")]
        violations.setdefault(rule, []).extend(vals)
    return executed, {k: sorted(v) for k, v in sorted(violations.items())}


# --------------------------------------------------------------------------- #
# Negative controls (temp copies only)
# --------------------------------------------------------------------------- #
def broken_copy(gds: pathlib.Path, out: pathlib.Path, kind: str) -> None:
    """Write a temp copy of ``gds`` with deliberately wrong geometry, drawn
    well clear (x >= 40 um) of the cell so it cannot disturb existing shapes."""
    ly = kdb.Layout()
    ly.read(str(gds))
    top = ly.cell(TOP)
    dbu = ly.dbu

    def box(layer, x0, y0, x1, y1):
        li = ly.layer(*layer)
        top.shapes(li).insert(
            kdb.Box(round(x0 / dbu), round(y0 / dbu), round(x1 / dbu), round(y1 / dbu))
        )

    if kind == "M1.a":  # Metal1 sliver 0.10 um wide; the minimum is 0.16
        box(c.L_METAL1, 40.0, 0.0, 40.10, 5.0)
    elif kind == "Gat.c":  # GatPoly crossing Activ with a 0.05 um endcap; minimum 0.18
        box(c.L_ACTIV, 40.0, 10.0, 41.0, 11.0)
        box(c.L_GATPOLY, 40.4, 9.95, 40.6, 11.5)
    else:
        raise ValueError(kind)
    ly.write(str(out))


CONTROLS = ("M1.a", "Gat.c")


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def build_report(gds, executed, violations, ver_s, fv, tree, controls):
    n_viol = sum(len(v) for v in violations.values())
    targeted = []
    for rule in TARGETED:
        targeted.append(
            {
                "rule": rule,
                "description": executed.get(rule, ""),
                "executed": rule in executed,
                "violations": len(violations.get(rule, [])),
            }
        )
    return {
        "schema": SCHEMA,
        "status": "violations" if n_viol else "clean",
        "scope": (
            "standalone top cell `comparator` only (no seal ring, no pads, no "
            "fill, no hierarchy above it). Rules are 'executed' when the deck "
            "emitted a result category for them; a rule whose layers are not "
            "drawn here executed vacuously (see `drawn_layers`)."
        ),
        "gds": {
            "path": gds.relative_to(REPO).as_posix() if gds.is_relative_to(REPO) else gds.name,
            "sha256": sha256_file(gds),
            "top": TOP,
            "drawn_layers": drawn_layers(gds),
        },
        "deck": {
            "source": "IHP-GmbH/IHP-Open-PDK",
            "release_tag": PDK_RELEASE_TAG,
            "fetched_version": fv,
            "pinned_by": "sim/pdk.json",
            "entrypoint": f"{DECK_REL}/run_drc.py",
            "tree_sha256": tree,
            "rule_sets": ["main", "sg13g2_maximal (extra rules; PDK states these are not fully verified)"],
        },
        "tool": {"klayout": ver_s},
        "invocation": (
            "run_drc.py --path=<gds> --topcell=comparator --run_mode=deep "
            f"--no_density --mp=1 --density_thr={THREADS}"
        ),
        "rules": {
            "executed_count": len(executed),
            "violated": [
                {
                    "rule": r,
                    "description": executed.get(r, ""),
                    "count": len(m),
                    "markers": m,
                }
                for r, m in violations.items()
            ],
            "violation_count": n_viol,
            "targeted": targeted,
        },
        "skipped": [
            {"rule_set": "density", "reason": "switched off (--no_density): needs chip-level fill; a standalone cell has none, so a density result would be meaningless here"},
            {"rule_set": "antenna", "reason": "not enabled (no --antenna)"},
            {"rule_set": "precheck", "reason": "not enabled (no --precheck_drc)"},
            {"rule_set": "seal ring / pad / bump / top-metal / MiM / inductor / HBT / Schottky rules", "reason": "executed vacuously: the layers are not drawn in this cell"},
        ],
        "negative_controls": controls,
        "not_covered": [
            "latch-up and antenna beyond what the deck emitted above",
            "density / fill and seal ring (chip-level)",
            "LVS, ERC, extraction (separate flow stages)",
            "foundry signoff: this is IHP's open deck, not a foundry-signed runset",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gds", nargs="?", default=str(DEFAULT_GDS))
    ap.add_argument("--pdk", help="IHP-Open-PDK ihp-sg13g2 directory")
    ap.add_argument("--klayout", help="KLayout >= 0.29.11 executable (else $KLAYOUT_BIN, else PATH)")
    ap.add_argument("-o", "--output", default=str(DEFAULT_REPORT))
    ap.add_argument("--check", action="store_true", help="require the committed report to be reproduced; write nothing")
    ap.add_argument("--strict", action="store_true", help="exit 1 when the status is `violations`")
    ap.add_argument("--no-controls", action="store_true", help="skip the negative controls")
    a = ap.parse_args()
    gds = pathlib.Path(a.gds).resolve()
    out = pathlib.Path(a.output)

    try:
        pdk, binary, ver_s, fv, tree = resolve_prereqs(a.pdk, a.klayout)
    except Unavailable as e:
        print(json.dumps({"schema": SCHEMA, "status": "unavailable", "reason": e.reason,
                          "detail": e.detail, "gds": {"sha256": sha256_file(gds)}}, indent=2))
        print(f"UNAVAILABLE ({e.reason}): {e.detail}", file=sys.stderr)
        return 3

    before = sha256_file(gds)
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        executed, violations = run_deck(pdk, binary, gds, td / "committed")
        controls = []
        if not a.no_controls:
            for kind in CONTROLS:
                tmp = td / f"broken_{kind.replace('.', '_')}.gds"
                broken_copy(gds, tmp, kind)
                ex2, v2 = run_deck(pdk, binary, tmp, td / f"ctl_{kind.replace('.', '_')}")
                ok = kind in ex2 and kind in v2 and kind not in violations
                controls.append({
                    "mutation": {"M1.a": "Metal1 sliver 0.10 um wide", "Gat.c": "GatPoly endcap 0.05 um over a scratch Activ"}[kind],
                    "expected_rule": kind,
                    "observed_violations": len(v2.get(kind, [])),
                    "committed_violations_of_rule": len(violations.get(kind, [])),
                    "result": "fails_as_expected" if ok else "NOT_DETECTED",
                })
    if sha256_file(gds) != before:
        print("FAIL: the GDS changed during the run", file=sys.stderr)
        return 1
    bad = [x for x in controls if x["result"] != "fails_as_expected"]
    report = build_report(gds, executed, violations, ver_s, fv, tree, controls)
    text = json.dumps(report, indent=2, sort_keys=False) + "\n"

    print(f"PDK deck {PDK_RELEASE_TAG} on KLayout {ver_s}: {report['status']}, "
          f"{report['rules']['violation_count']} marker(s) in "
          f"{len(report['rules']['violated'])} rule(s), "
          f"{report['rules']['executed_count']} rules executed")
    for v in report["rules"]["violated"]:
        print(f"  {v['rule']}: {v['count']}  {v['description']}")
    for x in controls:
        print(f"  control {x['expected_rule']}: {x['result']}")
    if bad:
        print("FAIL: a negative control was not detected; the deck run proves nothing", file=sys.stderr)
        return 1

    if a.check:
        if not out.is_file() or out.read_text() != text:
            print(f"FAIL: {out} is stale or missing; rerun without --check and commit", file=sys.stderr)
            return 1
        print(f"committed {out.name} reproduces")
    else:
        out.write_text(text)
        print(f"wrote {out}")
    return 1 if (a.strict and report["status"] == "violations") else 0


if __name__ == "__main__":
    sys.exit(main())

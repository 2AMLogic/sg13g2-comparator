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
* ``1``  tool error, a malformed or incomplete deck run (exit status that is
         not the deck's verdict, empty or partial rule inventory; nothing is
         written), a failed negative control, or (``--check``) a stale
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

#: Emission contract of the pinned deck for the invocation in ``run_deck``
#: (issue #253). A KLayout ``output('<name>', ...)`` call creates its report
#: category whether or not it yields markers, so these are the categories the
#: merged lyrdb must declare whenever both rule sets ran to completion. Derived
#: statically from the deck tree pinned by ``DECK_TREE_SHA256``: every
#: ``output`` call with a literal rule name whose enclosing blocks are only
#: switches this invocation turns on -- the table gates (main => FEOL, BEOL,
#: PIN, FORBIDDEN), ``unless PRECHECK_DRC``, ``RECOMMENDED`` /
#: ``$recommendedRules`` (run_drc.py passes ``no_recommended=false``),
#: ``CONNECTIVITY_RULES``, ``$fillerRules`` / ``$latchUpRules`` (default true)
#: and the maximal deck's immediately invoked ``-> do ... end.()`` lambdas.
#: Not required: names built in loops or helper ``def``s (M2..M5, V2..V4,
#: fillers, offgrid, angle, forbidden, pin, Seal.b/Pad.fR/Slt.e1 and the like:
#: emitted, but their names are computed), Seal.l (only when an EdgeSeal
#: boundary exists) and MIM.gR (only above a MIM area), plus everything behind
#: switches this invocation leaves off (density, antenna, precheck).
#: ``layout/tests/test_pdk_drc.py`` re-derives both sets from a local pinned
#: checkout when one is present.
REQUIRED_CATEGORIES = {
    "main": tuple("""
        M1.a M1.b M1.e M1.f M1.g M1.i V1.a V1.b V1.c TV1.a TV1.b TV1.c TV1.d
        TM1.a TM1.b TM1Fil.c TM1Fil.a1 TV2.a TV2.b TV2.c TV2.d TM2.a TM2.b
        TM2.bR TM2Fil.c TM2Fil.a1 Pas.a Pas.b Pas.c Seal.n Seal.k Seal.m MIM.c
        MIM.d Padc.a Padc.b Padc.c padc.f Pad.m Pad.i Padb.a Padb.b Padb.c
        padb.f Padb.d LBE.a LBE.b LBE.b1 LBE.c LBE.d LBE.h pSD.c1 Cnt.a Cnt.b
        Cnt.c Cnt.c.digibnd Cnt.c.SRAM Cnt.d Cnt.e Cnt.g1 Cnt.g2 CntB.b1
        CntB.h1 NW.b NW.b1 NW.f1 NW.f1.digibnd PWB.e PWB.e1 PWB.f PWB.f1 NBL.b
        NBL.c NBL.d NBL.e NBL.f Act.a Act.b AFil.c1 AFil.c AFil.d AFil.e
        AFil.j TGO.f Gat.a Gat.b Gat.d Gat.a1 Gat.a2 Gat.g GFil.d GFil.e
        GFil.i npn13G2.bR npn13G2L.cR npn13G2V.cR Sdiod.b Sdiod.c Sdiod.d
        Sdiod.e LU.b
    """.split()),
    "sg13g2_maximal": tuple("""
        NW.a NW.c NW.c1 NW.d NW.d1 NW.e NW.e1 NW.f PWB.a PWB.b PWB.c NBL.a
        NBLB.a NBLB.b NBLB.c NBLB.d Act.c Act.d Act.e AFil.a AFil.a1 AFil.b
        AFil.i TGO.a TGO.b TGO.c TGO.d TGO.e Gat.a3 Gat.a4 Gat.b1 Gat.c Gat.e
        Gat.f GFil.a GFil.b GFil.c GFil.f GFil.j pSD.a pSD.b pSD.c pSD.d
        pSD.d1 pSD.e pSD.f pSD.g pSD.i pSD.i1 pSD.j pSD.j1 pSD.k pSD.l pSD.m
        pSD.n nSDB.a nSDB.b nSDB.c nSDB.e EXTB.a EXTB.b EXTB.c Sal.a Sal.b
        Sal.c Sal.d Sal.e Cnt.b1 Cnt.f Cnt.g Cnt.h Cnt.j CntB.a CntB.a1 CntB.b
        CntB.b2 CntB.c CntB.d CntB.e CntB.f CntB.g CntB.g1 CntB.g2 CntB.h
        CntB.j M1.c M1.c1 M1.d M2.c M2.c1 M2.d M3.c M3.c1 M3.d M4.c M4.c1 M4.d
        M5.c M5.c1 M5.d M1Fil.a1 M1Fil.b M1Fil.d M2Fil.a1 M2Fil.b M2Fil.d
        M3Fil.a1 M3Fil.b M3Fil.d M4Fil.a1 M4Fil.b M4Fil.d M5Fil.a1 M5Fil.b
        M5Fil.d V1.b1 V1.c1 V2.b1 V2.c1 V3.b1 V3.c1 V4.b1 V4.c1 TM1Fil.a
        TM1Fil.b TM1Fil.d TM2Fil.a TM2Fil.b TM2Fil.d npnG2.b npnG2.c
        npnG2.d.N_Activ npnG2.d.NWell npnG2.d.PWell_block npnG2.d.nBuLay
        npnG2.d.nSD_block npnG2.d1 npnG2.d2 npnG2.e npn13G2.a npn13G2L.a
        npn13G2L.b npn13G2V.a npn13G2V.b Rsil.a Rsil.b Rsil.c Rsil.d Rsil.e
        Rsil.f Rppd.a Rppd.b Rppd.c Rppd.d Rppd.e Rhi.a Rhi.b Rhi.c Rhi.d
        Rhi.e Rhi.f nmosi.b nmosi.c nmosi.d nmosi.f nmosi.g Sdiod.a Pad.aR
        Pad.a1 Pad.bR Pad.d Pad.dR Pad.d1R Pad.gR Pad.jR Pad.kR Padc.d
        Seal.a_Activ Seal.a_pSD Seal.a_Metal1 Seal.a_Metal2 Seal.a_Metal3
        Seal.a_Metal4 Seal.a_Metal5 Seal.a_TopMetal1 Seal.a_TopMetal2 Seal.c
        Seal.c1.Via1 Seal.c1.Via2 Seal.c1.Via3 Seal.c1.Via4 Seal.c2 Seal.c3
        Seal.d.Cont Seal.d.Via1 Seal.d.Via2 Seal.d.Via3 Seal.d.Via4
        Seal.d.TopVia1 Seal.d.TopVia2 Seal.e Seal.f.Activ Seal.f.pSD
        Seal.f.Metal1 Seal.f.Metal2 Seal.f.Metal3 Seal.f.Metal4 Seal.f.Metal5
        Seal.f.TopMetal1 Seal.f.TopMetal2 MIM.a MIM.b MIM.e MIM.f MIM.g MIM.h
        LU.a LU.c LU.c1 LU.d LU.d1 Slt.a.M1 Slt.b.M1 Slt.c.M1 Slt.e.M1
        Slt.f.M1 Slt.h1 Slt.a.M2 Slt.b.M2 Slt.c.M2 Slt.e.M2 Slt.f.M2 Slt.h2.M2
        Slt.a.M3 Slt.b.M3 Slt.c.M3 Slt.e.M3 Slt.f.M3 Slt.h2.M3 Slt.a.M4
        Slt.b.M4 Slt.c.M4 Slt.e.M4 Slt.f.M4 Slt.h2.M4 Slt.a.M5 Slt.b.M5
        Slt.c.M5 Slt.e.M5 Slt.f.M5 Slt.g.M5 Slt.h2.M5 Slt.a.TM1 Slt.b.TM1
        Slt.c.TM1 Slt.e.TM1 Slt.f.TM1 Slt.g.TM1 Slt.h3 Slt.a.TM2 Slt.b.TM2
        Slt.c.TM2 Slt.e.TM2 Slt.f.TM2 Slt.h4 NW.c1.dig NW.d1.dig NW.e1.dig
        LBE.b2 LBE.e.dfPad LBE.e.Passiv LBE.f
    """.split()),
}

#: run_drc.py's own verdict lines (check_drc_results) and the exit status it
#: pairs with each: 0 = completed without violations, 1 = completed with
#: violations. Exit 1 is also every error path of run_drc.py, so a 1 counts as
#: "violations" only together with markers and the deck's own verdict line.
DECK_VERDICT = {
    0: "KLayout DRC Check Passed: No DRC violations detected",
    1: "KLayout DRC Check Failed: Violations were detected",
}

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
    violations {rule: [marker = list of value strings]}).
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
    output = (proc.stdout or "") + (proc.stderr or "")
    # run_drc.py names its outputs <layout stem>_<topcell>_<table>.{log,lyrdb}
    # and merges the per-table databases into <stem>_<topcell>_full.lyrdb.
    stem = f"{pathlib.Path(gds).resolve().stem}_{TOP}"
    db = run_dir / f"{stem}_full.lyrdb"
    unfinished = []
    for rule_set in REQUIRED_CATEGORIES:
        log = run_dir / f"{stem}_{rule_set}.log"
        if not log.is_file() or "completed in" not in log.read_text(errors="replace"):
            unfinished.append(rule_set)
    if proc.returncode not in DECK_VERDICT or not db.is_file() or unfinished:
        raise IncompleteRun(
            f"PDK deck did not complete (exit status {proc.returncode}; merged "
            f"lyrdb {'present' if db.is_file() else 'missing'}; unfinished rule "
            f"sets: {', '.join(unfinished) or 'none'})\n" + output[-2000:]
        )
    executed, violations = parse_lyrdb(db)
    check_inventory(executed)
    check_exit_status(proc.returncode, violations, output)
    return executed, violations


class MalformedReport(ValueError):
    """The deck's lyrdb cannot be interpreted; it must never certify clean."""


class IncompleteRun(RuntimeError):
    """The deck run did not demonstrably complete with the pinned deck's rule
    inventory (issue #253); its output must never certify clean."""


def check_inventory(executed) -> None:
    """Refuse an empty rule inventory or one missing any category the pinned
    deck always emits for this invocation (``REQUIRED_CATEGORIES``)."""
    if not executed:
        raise IncompleteRun("empty rule inventory: the deck declared no rule categories")
    problems = []
    for rule_set, rules in REQUIRED_CATEGORIES.items():
        missing = [r for r in rules if r not in executed]
        if missing:
            problems.append(
                f"{len(missing)} of {len(rules)} required {rule_set} categories "
                f"missing ({', '.join(missing[:5])}{', ...' if len(missing) > 5 else ''})"
            )
    if problems:
        raise IncompleteRun("incomplete rule inventory: " + "; ".join(problems))


def check_exit_status(returncode: int, violations, output: str) -> None:
    """Refuse an exit status that is not run_drc.py's verdict for the parsed
    database: 0 with no markers, 1 with markers, each with the deck's own
    verdict line. Exit 1 without markers is one of its error paths."""
    n = sum(len(v) for v in violations.values())
    expected = 1 if n else 0
    if returncode != expected:
        raise IncompleteRun(
            f"deck exit status {returncode} does not match its lyrdb ({n} marker(s) "
            f"=> {expected})\n" + output[-2000:]
        )
    if DECK_VERDICT[returncode] not in output:
        raise IncompleteRun(
            f"deck exit status {returncode} without its verdict line "
            f"{DECK_VERDICT[returncode]!r}\n" + output[-2000:]
        )


def parse_lyrdb(path: pathlib.Path):
    """Parse a lyrdb into (executed {rule: description}, violations
    {rule: [marker]}). One XML <item> is one marker, a list of all its
    non-blank values; counts are derived from markers, never from values.
    Anything uninterpretable raises MalformedReport."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        raise MalformedReport(f"{path}: unreadable lyrdb: {e}") from e
    cats = root.find("categories")
    items = root.find("items")
    if cats is None:
        raise MalformedReport(f"{path}: missing <categories> container")
    if items is None:
        raise MalformedReport(f"{path}: missing <items> container")
    executed = {}
    for i, cat in enumerate(cats):
        name = (cat.findtext("name") or "").strip().strip("'").strip()
        if not name:
            raise MalformedReport(f"{path}: category #{i} has a blank name")
        if name in executed:
            raise MalformedReport(f"{path}: duplicate category declaration {name!r}")
        executed[name] = " ".join((cat.findtext("description") or "").split())
    if not executed:
        raise MalformedReport(f"{path}: empty <categories>: the deck emitted no rule inventory")
    violations: dict[str, list[list[str]]] = {}
    for i, item in enumerate(items):
        rule = (item.findtext("category") or "").strip().strip("'").strip()
        if not rule:
            raise MalformedReport(f"{path}: item #{i} has a blank category")
        if rule not in executed:
            raise MalformedReport(f"{path}: item #{i} references undeclared category {rule!r}")
        vals_el = item.find("values")
        if vals_el is None:
            raise MalformedReport(f"{path}: item #{i} ({rule}) has no <values> container")
        vals = [" ".join((v.text or "").split()) for v in vals_el]
        vals = [v for v in vals if v]
        if not vals:
            raise MalformedReport(f"{path}: item #{i} ({rule}) has no usable values")
        violations.setdefault(rule, []).append(vals)
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
    check_inventory(executed)  # never a report, clean or not, from a partial run
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


def refuse(e: Exception) -> int:
    """The single failure path for deck output that cannot be evidence."""
    what = "malformed deck report" if isinstance(e, MalformedReport) else "incomplete deck run"
    print(f"FAIL: {what}, nothing written: {e}", file=sys.stderr)
    return 1


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
        try:
            executed, violations = run_deck(pdk, binary, gds, td / "committed")
        except (MalformedReport, IncompleteRun) as e:
            return refuse(e)
        controls = []
        if not a.no_controls:
            for kind in CONTROLS:
                tmp = td / f"broken_{kind.replace('.', '_')}.gds"
                broken_copy(gds, tmp, kind)
                try:
                    ex2, v2 = run_deck(pdk, binary, tmp, td / f"ctl_{kind.replace('.', '_')}")
                except (MalformedReport, IncompleteRun) as e:
                    return refuse(e)
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
    try:
        report = build_report(gds, executed, violations, ver_s, fv, tree, controls)
    except IncompleteRun as e:
        return refuse(e)
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

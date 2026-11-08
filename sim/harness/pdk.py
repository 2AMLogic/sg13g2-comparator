"""IHP SG13G2 PDK discovery.

No PDK path is ever hardcoded into a netlist or a testbench. Everything
resolves through this module so the harness runs unchanged on a developer
box, a CI runner, or a fresh agent container.

Resolution order (first hit wins):

1. ``SG13G2_PDK_PATH``  -- absolute path to the *variant* directory (the one
                           containing ``libs.tech/``), e.g.
                           ``~/share/pdk/ihp-sg13g2``.
2. ``PDK_ROOT`` (+ ``PDK``, default ``ihp-sg13g2``) -- the conventional
                           open_pdks-shaped pair this repo's ``sim/env.sh``
                           already resolves.
3. ``sim/pdk.local.json`` -- machine-local override, git-ignored.
4. ``sim/pdk.json``      -- committed defaults: variant + search roots.
5. Built-in search roots -- the same prefixes ``sim/env.sh`` tries:
   ``/usr/share/pdk``, ``/usr/local/share/pdk``, ``~/share/pdk``,
   ``~/.ciel``, ``~/.volare``.

Ported from ``2AMLogic/gf180-comparator``'s ``sim/harness/pdk.py`` (itself
ported from ``2AMLogic/gf180-sar-adc``). ADAPTED FOR SG13G2, structurally:

- gf180mcu's ``pdk.py`` resolves a monolithic ``sm141064.ngspice`` model file
  plus a ``design.ngspice`` global-switch include that must be loaded ahead
  of every corner section. **IHP-Open-PDK has no equivalent global-switch
  include** -- each corner ``.LIB`` block in ``cornerMOSlv.lib`` /
  ``cornerRES.lib`` is self-contained (confirmed by reading the installed
  checkout: no ``sw_stat_global`` / ``sw_stat_mismatch`` style switch exists
  anywhere in ``libs.tech/ngspice/models/*.lib``), so there is no
  ``design_include`` property here at all -- see ``harness/runner.py``.
- gf180mcu's LV/HV MOS models are ordinary SPICE ``.model`` cards, usable the
  moment the corner ``.lib`` is included. **SG13G2's PSP103-based MOS models
  (and its ``r3_cmc``-based resistor models) are Verilog-A, compiled to OSDI
  shared libraries that must be ``pre_osdi``-loaded before any
  ``sg13_lv_nmos``/``sg13_lv_pmos``/``rhigh``/... subcircuit can be
  instantiated.** ``Pdk.missing_osdi()`` / ``REQUIRED_OSDI`` exist for this
  reason and have no gf180mcu counterpart; ``sim/tools/build-osdi.sh``
  (ported from ``sg13g2-opamp/sim/tools/build-osdi.sh``) is how a missing set
  gets built. See ``sim/harness/README.md``'s divergence table.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"

DEFAULT_VARIANT = "ihp-sg13g2"

# Search roots used when nothing else pins the PDK down. Same order as
# sim/env.sh's own fallback chain, so `source sim/env.sh` and this module
# always agree on where the PDK lives.
BUILTIN_SEARCH_ROOTS = (
    "/usr/share/pdk",
    "/usr/local/share/pdk",
    "~/share/pdk",
    "~/.ciel",
    "~/.volare",
)

#: OSDI shared libraries this repo's testbenches load via ``pre_osdi``
#: (sim/tools/build-osdi.sh builds exactly these four). ``psp103``/
#: ``psp103_nqs`` back sg13_lv_nmos/sg13_lv_pmos (and their HV counterparts);
#: ``r3_cmc`` backs every PDK resistor subcircuit (``rhigh``/``rppd``/
#: ``rsil``); ``mosvar`` backs the PDK's varactor. All four are required for
#: --check-env even though today's placeholder DUT only instantiates the
#: first three, because a DUT swap must not silently need a rebuild.
REQUIRED_OSDI: tuple[str, ...] = ("psp103.osdi", "psp103_nqs.osdi", "r3_cmc.osdi", "mosvar.osdi")

#: Machine-local receipt sim/tools/build-osdi.sh writes next to its outputs.
OSDI_RECEIPT = ".build-osdi-receipt.json"
_RECEIPT_KEYS = ("compiler", "platform", "build_flags", "sources", "pdk_release_marker")


class OsdiIdentityError(RuntimeError):
    """A required OSDI binary is missing or unreadable: it has no byte identity."""


def osdi_identity(osdi_dir: Path) -> dict:
    """Issue #196: path-independent SHA-256 identity of the REQUIRED_OSDI bytes.

    ``inventory_sha256`` is the sha256 of ``sha256sum``-style lines
    (``<hex>  <name>``, sorted by name). Equal hashes mean equal bytes, nothing
    more: they do not prove a compiler version or PDK authenticity, and they
    say nothing about loadability (``build-osdi.sh --check``). Missing or
    unreadable files raise :class:`OsdiIdentityError`, never a partial result.
    """
    files = {}
    for name in REQUIRED_OSDI:
        try:
            files[name] = hashlib.sha256((osdi_dir / name).read_bytes()).hexdigest()
        except OSError as exc:
            raise OsdiIdentityError(f"{name}: {exc.strerror or exc}") from exc
    lines = "".join(f"{h}  {n}\n" for n, h in sorted(files.items()))
    return {"inventory_sha256": hashlib.sha256(lines.encode()).hexdigest(),
            "files": files, "build_provenance": _build_provenance(osdi_dir, files)}


def _build_provenance(osdi_dir: Path, files: dict) -> dict:
    """Attribution from build-osdi.sh's receipt only if it names exactly these bytes."""
    try:
        receipt = json.loads((osdi_dir / OSDI_RECEIPT).read_text())
        outputs = receipt["outputs"]
        if {n: outputs.get(n) for n in files} != files:
            return {"status": "unknown", "reason": "receipt output hashes do not match these bytes"}
    except FileNotFoundError:
        return {"status": "unknown", "reason": f"no {OSDI_RECEIPT} (not built by build-osdi.sh here)"}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {"status": "unknown", "reason": f"unusable receipt: {exc!r}"}
    return {"status": "receipt", **{k: receipt.get(k, "unknown") for k in _RECEIPT_KEYS}}


#: Issue #203: the inventoried runtime SPICE model-source tree, relative to the
#: variant directory. Recorded verbatim so evidence states its own scope.
MODEL_SOURCE_TREE = "libs.tech/ngspice/models"
MODEL_SOURCE_SCOPE_NOTE = (
    "whole-tree inventory: equal hashes mean byte-identical files under this tree, "
    "not PDK authenticity; it also changes when an unused model file changes and is "
    "not the exact dependency closure of the selected .LIB sections")

# `.include`/`.inc`/`.lib <file> [section]` -- a disclosure scan for references
# that leave the tree, NOT a dependency parser (a one-token `.lib name` is a
# section header and is skipped).
_SPICE_REF_RE = re.compile(rb"^[ \t]*\.(inc\w*|lib)[ \t]+(\S+)([ \t]+\S+)?", re.I | re.M)


class ModelSourceIdentityError(RuntimeError):
    """A runtime SPICE model source is unreadable or outside the inventory scope."""


def _inside(path: str, root: str) -> bool:
    return os.path.commonpath([path, root]) == root


def model_source_identity(models_dir: Path, roots: tuple = ()) -> dict:
    """Issue #203: path-independent SHA-256 inventory of the SPICE model tree.

    Every file under ``models_dir`` (recursively, symlinks to files followed and
    hashed as the bytes ngspice would read) is hashed; ``inventory_sha256`` is
    the sha256 of sorted ``<hex>  <relative/posix/path>`` lines, so the same
    tree at two absolute paths has the same identity. ``scope`` discloses what
    the inventory does NOT cover: symlinks leaving the tree, symlinked
    directories outside it (not descended), and ``.include``/``.lib`` file
    references that resolve outside the tree or to no inventoried file --
    ``scope.complete`` is false whenever any of those exist. ``roots`` (the
    corner libraries decks reference) must lie inside the inventory.
    Unreadable, vanishing or non-regular files raise
    :class:`ModelSourceIdentityError`, never a partial result.
    """
    root = os.path.realpath(models_dir)

    def _fail(exc: OSError, where: str = "") -> None:
        name = where or os.path.relpath(exc.filename or root, root)
        raise ModelSourceIdentityError(f"{name}: {exc.strerror or exc}") from exc

    if not os.path.isdir(root):
        raise ModelSourceIdentityError(f"{MODEL_SOURCE_TREE}: not a directory")
    files: dict[str, str] = {}
    links: dict[str, str] = {}
    uninventoried: list[str] = []
    contents: dict[str, tuple[str, bytes]] = {}
    for dirpath, dirnames, filenames in os.walk(root, onerror=_fail):
        dirnames.sort()
        for name in list(dirnames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                dirnames.remove(name)  # never descended; its real path is walked if in-tree
                rel = Path(os.path.relpath(full, root)).as_posix()
                target = os.path.realpath(full)
                if _inside(target, root):
                    links[rel] = "in-tree:" + Path(os.path.relpath(target, root)).as_posix()
                else:
                    links[rel] = "outside-tree"
                    uninventoried.append(rel + "/")
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = Path(os.path.relpath(full, root)).as_posix()
            if os.path.islink(full):
                target = os.path.realpath(full)
                links[rel] = ("in-tree:" + Path(os.path.relpath(target, root)).as_posix()
                              if _inside(target, root) else "outside-tree")
            try:
                if not stat.S_ISREG(os.stat(full).st_mode):
                    raise ModelSourceIdentityError(f"{rel}: not a regular file")
                with open(full, "rb") as fh:
                    data = fh.read()
            except OSError as exc:
                _fail(exc, rel)
            files[rel] = hashlib.sha256(data).hexdigest()
            contents[rel] = (dirpath, data)

    references = []
    for rel, (dirpath, data) in sorted(contents.items()):
        for match in _SPICE_REF_RE.finditer(data):
            if match.group(1).lower() == b"lib" and match.group(3) is None:
                continue  # `.LIB section` header, not a file reference
            ref = match.group(2).strip(b"\"'").decode("utf-8", "replace")
            target = os.path.realpath(os.path.join(dirpath, os.path.expanduser(ref)))
            if not _inside(target, root):
                references.append({"from": rel, "ref": ref, "reason": "outside tree"})
            elif Path(os.path.relpath(target, root)).as_posix() not in files:
                references.append({"from": rel, "ref": ref, "reason": "not in inventory"})

    root_rels = []
    for lib in roots:
        target = os.path.realpath(lib)
        rel = Path(os.path.relpath(target, root)).as_posix() if _inside(target, root) else None
        if rel not in files:
            raise ModelSourceIdentityError(
                f"{Path(lib).name}: deck-referenced library is not inside the inventoried "
                f"{MODEL_SOURCE_TREE} tree")
        root_rels.append(rel)

    lines = "".join(f"{h}  {n}\n" for n, h in sorted(files.items()))
    outside_links = sorted(k for k, v in links.items() if v == "outside-tree")
    return {
        "inventory_sha256": hashlib.sha256(lines.encode()).hexdigest(),
        "files": dict(sorted(files.items())),
        "scope": {
            "kind": "whole-tree",
            "tree": MODEL_SOURCE_TREE,
            "roots": root_rels,
            "complete": not (outside_links or uninventoried or references),
            "links": dict(sorted(links.items())),
            "outside_tree_links": outside_links,
            "uninventoried_dirs": sorted(uninventoried),
            "uninventoried_references": references,
            "note": MODEL_SOURCE_SCOPE_NOTE,
        },
    }

INSTALL_HINT = """\
IHP SG13G2 PDK not found.

Fetch the pinned release (see sim/pdk.json for the exact tag + sha256),
e.g. via klayout-tools' scripts/fetch-ihp-sg13g2.sh, laid out
open_pdks-style as <root>/ihp-sg13g2:

    export PDK_ROOT=/path/to/pdk-root      # parent of ihp-sg13g2/
    export PDK=ihp-sg13g2

...or point the harness directly at the variant directory:

    export SG13G2_PDK_PATH=/path/to/ihp-sg13g2   # has libs.tech/

...or commit-free machine-local config in sim/pdk.local.json:

    {"variant": "ihp-sg13g2", "search_roots": ["/my/pdks"]}

See sim/README.md and sim/harness/README.md "Cold start" for the full
bootstrap, including building the OSDI device models (sim/tools/build-osdi.sh).
"""


class PdkNotFound(RuntimeError):
    """Raised when no usable IHP SG13G2 install can be located."""


@dataclass(frozen=True)
class Pdk:
    """A located IHP SG13G2 install."""

    path: Path          # .../ihp-sg13g2
    variant: str        # ihp-sg13g2
    source: str         # how we found it (for provenance in records)

    @property
    def ngspice_dir(self) -> Path:
        return self.path / "libs.tech" / "ngspice"

    @property
    def models_dir(self) -> Path:
        return self.ngspice_dir / "models"

    @property
    def osdi_dir(self) -> Path:
        return self.ngspice_dir / "osdi"

    @property
    def mos_corner_lib(self) -> Path:
        """The MOS process-corner bundle: ``.LIB mos_tt`` / ``mos_tt_mismatch`` / ..."""
        return self.models_dir / "cornerMOSlv.lib"

    @property
    def version(self) -> str:
        """The release tag recorded in the install's own ``.fetched-version``.

        Mirrors ``sim/device-mismatch-confirm/README.md``'s confirmation
        method: this repo's fetch tooling (klayout-tools'
        ``fetch-ihp-sg13g2.sh``) stamps the release tag into this file on
        every fetch.
        """
        marker = self.path / ".fetched-version"
        if marker.is_file():
            text = marker.read_text().strip()
            if text:
                return text
        return "unknown"

    def provenance(self) -> dict:
        return {
            "path": str(self.path),
            "variant": self.variant,
            "release_version": self.version,
            "discovered_via": self.source,
        }

    def missing_osdi(self) -> list[str]:
        """OSDI shared libraries named in ``REQUIRED_OSDI`` that are absent."""
        return [name for name in REQUIRED_OSDI if not (self.osdi_dir / name).is_file()]


def _is_valid_variant_dir(path: Path) -> bool:
    return (path / "libs.tech" / "ngspice" / "models" / "cornerMOSlv.lib").is_file()


def _load_config() -> dict:
    """Merge sim/pdk.json with sim/pdk.local.json (local wins)."""
    config: dict = {}
    for name in ("pdk.json", "pdk.local.json"):
        candidate = SIM_DIR / name
        if candidate.is_file():
            try:
                config.update(json.loads(candidate.read_text()))
            except json.JSONDecodeError as exc:  # pragma: no cover - config typo
                raise RuntimeError(f"{candidate} is not valid JSON: {exc}") from exc
    return config


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def find_pdk(variant: str | None = None) -> Pdk:
    """Locate an IHP SG13G2 install, or raise :class:`PdkNotFound`."""
    config = _load_config()
    variant = variant or os.environ.get("PDK") or config.get("variant") or DEFAULT_VARIANT

    direct = os.environ.get("SG13G2_PDK_PATH")
    if direct:
        path = _expand(direct)
        if not _is_valid_variant_dir(path):
            raise PdkNotFound(
                f"SG13G2_PDK_PATH={direct} does not look like an ihp-sg13g2 variant "
                f"directory (expected {path}/libs.tech/ngspice/models/cornerMOSlv.lib).\n\n"
                + INSTALL_HINT
            )
        return Pdk(path=path, variant=path.name, source="SG13G2_PDK_PATH")

    tried: list[str] = []

    pdk_root = os.environ.get("PDK_ROOT")
    if pdk_root:
        path = _expand(pdk_root) / variant
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            return Pdk(path=path, variant=variant, source="PDK_ROOT")

    roots = list(config.get("search_roots") or ()) + list(BUILTIN_SEARCH_ROOTS)
    for root in roots:
        path = _expand(root) / variant
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            return Pdk(path=path, variant=variant, source=f"search_root:{root}")

    raise PdkNotFound(
        "Looked for ihp-sg13g2 variant %r in:\n  %s\n\n%s"
        % (variant, "\n  ".join(tried), INSTALL_HINT)
    )

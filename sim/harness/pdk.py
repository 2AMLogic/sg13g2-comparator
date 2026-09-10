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

import json
import os
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
    def res_corner_lib(self) -> Path:
        """The resistor process-corner bundle: ``.LIB res_typ`` / ``res_typ_mismatch`` / ..."""
        return self.models_dir / "cornerRES.lib"

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


def pdk_available(variant: str | None = None) -> bool:
    try:
        find_pdk(variant)
    except PdkNotFound:
        return False
    return True

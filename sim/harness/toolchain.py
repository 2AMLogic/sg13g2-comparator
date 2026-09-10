"""Pinned-toolchain check.

``sim/toolchain.json`` pins the exact IHP-Open-PDK release the device models
must come from, plus floors for ngspice and Python. The pins are **checked
before any PVT point is simulated**, not merely recorded afterwards: a
different PDK release is a different set of device models, so a record
taken under one release is not comparable with a record taken under
another, and nothing in the resulting numbers would look wrong.

Ported from ``2AMLogic/gf180-comparator``'s ``sim/harness/toolchain.py``
(itself ported from ``2AMLogic/gf180-sar-adc``). ADAPTED: the pin is named
``pdk_release`` here (SG13G2 has no "open_pdks commit hash" concept --
``sim/pdk.json`` pins an IHP-Open-PDK release tag + tarball sha256 instead,
and ``harness/pdk.py``'s ``Pdk.version`` reads the installed checkout's own
``.fetched-version`` marker, e.g. ``"0.3.0"``). A new ``openvaf_tag`` field
is RECORDED, NOT CHECKED, mirroring gf180-comparator's treatment of
``xschem_tag``: ``sim/tools/build-osdi.sh`` is what actually pins and
verifies the OpenVAF-Reloaded compiler (checksum, not just a tag), and that
happens outside the corner runner, at OSDI-build time -- the runner only
consumes the resulting ``.osdi`` files (see ``harness/pdk.py``'s
``missing_osdi()`` / ``REQUIRED_OSDI``).
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN_JSON = REPO_ROOT / "sim" / "toolchain.json"


class ToolchainDrift(RuntimeError):
    """A pinned tool version does not match what is installed."""


@dataclass
class Toolchain:
    pins: dict
    observed: dict = field(default_factory=dict)
    drift: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "pins": {k: v for k, v in self.pins.items() if not k.startswith("_")},
            "observed": self.observed,
            "drift": list(self.drift),
        }


def load_pins(path: Path = TOOLCHAIN_JSON) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"no toolchain pin file at {path}")
    return json.loads(path.read_text())


def _ngspice_major(version_banner: str) -> int | None:
    match = re.search(r"ngspice-(\d+)", version_banner)
    return int(match.group(1)) if match else None


def check(pdk_version: str, ngspice_banner: str, path: Path = TOOLCHAIN_JSON) -> Toolchain:
    """Compare the pins against what is actually installed.

    Returns a :class:`Toolchain` whose ``drift`` list is empty when every
    checked pin matches. The caller decides whether drift is fatal (it is, by
    default -- ``--allow-toolchain-drift`` overrides and stamps the drift into
    the record).
    """
    pins = load_pins(path)
    observed = {
        "pdk_release": pdk_version,
        "ngspice": ngspice_banner,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    drift: list[str] = []

    pinned_pdk = pins.get("pdk_release")
    if pinned_pdk and pdk_version != pinned_pdk:
        drift.append(
            f"pdk_release: pinned {pinned_pdk}, installed {pdk_version} -- "
            "the release IS the device models; records taken under a "
            "different release are not comparable with the ones already in sim/"
        )

    pinned_ng = pins.get("ngspice_min_major")
    major = _ngspice_major(ngspice_banner)
    if pinned_ng is not None:
        if major is None:
            drift.append(f"ngspice: could not parse a major version from {ngspice_banner!r}")
        elif major < int(pinned_ng):
            drift.append(f"ngspice: pinned floor {pinned_ng}, installed major {major}")

    pinned_py = pins.get("python_min")
    if pinned_py:
        want = tuple(int(p) for p in str(pinned_py).split("."))
        if sys.version_info[: len(want)] < want:
            drift.append(f"python: pinned floor {pinned_py}, running {platform.python_version()}")

    # observed["pdk_release"] is what the record header shows; expose it as
    # {"open_pdks": ...}-shaped too would be misleading naming carried over
    # from gf180-comparator, so this module does not do that.
    observed["ngspice"] = ngspice_banner
    return Toolchain(pins=pins, observed=observed, drift=drift)


def xschem_banner() -> str:
    """Best-effort xschem version string. Recorded, never checked (see json)."""
    try:
        out = subprocess.run(
            ["xschem", "--version"], capture_output=True, text=True, check=False, timeout=20
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "not installed"
    text = (out.stdout + out.stderr).strip()
    return text.splitlines()[0].strip() if text else "unknown"

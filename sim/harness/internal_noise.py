"""Optional internal-noise hook (issue #81): per-device TRNOISE sources.

The DUT pin contract (``sim/dut/README.md``) is a black box: a testbench
fragment can only reach ``vinp``/``vinn``, so noise it injects there never
includes the regenerative pair's own thermal noise. This module lets a
testbench manifest request noise sources on NAMED internal devices of the
DUT, without touching the DUT netlist or its pin contract.

HOOK OFF BY DEFAULT. ``compose_deck`` calls :func:`emit_internal_noise` only
when ``tb.json`` carries an ``internal_noise`` block; with the key absent
nothing is emitted and the composed deck is byte-identical to the pre-hook
one (asserted in ``tests/test_internal_noise.py``).

MECHANISM. ngspice's PSP103 OSDI devices have no TRNOISE parameter, so a
device's channel thermal noise is modelled as a noise CURRENT source across
its drain/source, built from two elements per device and instance::

    Vinz_<inst>_<dev> inz_<inst>_<dev> 0 dc 0 trnoise(NA TS 0 0)
    Binz_<inst>_<dev> <drain> <source> I = 'v(inz_..)*sqrt((temper+273.15)/300.15)<gate>'

The voltage source carries a white TRNOISE process (1 V standing for 1 A);
the B source maps it to a current, rescales the amplitude with the live
corner temperature (``temper``; no dependence on a harness ``.param``, so the
same text works inside a ``klt sim`` body), and optionally phase-gates it.

The one-sided density is ``S = sqrt(4 k T gamma g)`` A/rtHz, ``g`` being the
small-signal conductance the manifest states for that device (gm for a
device in saturation, gds0 for one in triode). ngspice's TRNOISE density is
``NA*sqrt(2*TS)`` (sim/comparator-transient-noise/README.md "NA/TS
calibration"), so ``NA = S(300.15 K) / sqrt(2*TS)``. ``g`` is a single
stated value per device (sim/dut/README.md "Optional internal-noise hook"
gives the calibration approach and its stated error).

A device that is off for part of the cycle (the cross-coupled pair during
reset, the reset devices during evaluate) can be PHASE-GATED: the B source
is multiplied by ``v(clk)/v(vdd)`` (``evaluate``) or ``1 - v(clk)/v(vdd)``
(``reset``).

White noise only (NALPHA = NAMP = 0), consistent with the existing bench's
"Why white only".

Everything here is a PURE function of its arguments (no files, no ngspice),
so it is testable stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass

BOLTZMANN = 1.380649e-23

#: Keys a manifest ``internal_noise`` block may carry.
BLOCK_KEYS = (
    "subckt", "inner", "instances", "ts", "scale", "devices",
    "rails", "clk_node", "vdd_node",
)
#: Keys a per-device entry may carry.
DEVICE_KEYS = ("g", "gamma", "phase")
PHASES = ("always", "evaluate", "reset")


class InternalNoiseError(ValueError):
    """The ``internal_noise`` request is malformed or names unknown devices."""


@dataclass(frozen=True)
class DeviceTerminals:
    name: str
    drain: str
    gate: str
    source: str
    bulk: str


def parse_subckt_devices(netlist_text: str, subckt: str) -> dict[str, DeviceTerminals]:
    """MOS instance lines (``X<name> d g s b model ...``) of ``subckt``,
    keyed by upper-cased instance name."""
    found: dict[str, DeviceTerminals] = {}
    inside = False
    for raw in netlist_text.splitlines():
        line = raw.strip()
        low = line.lower()
        if low.startswith(".subckt"):
            tokens = low.split()
            inside = len(tokens) > 1 and tokens[1] == subckt.lower()
            continue
        if low.startswith(".ends"):
            inside = False
            continue
        if not inside or not line or line.startswith("*"):
            continue
        tokens = line.split()
        if tokens[0][0].upper() == "X" and len(tokens) >= 6 and "=" not in "".join(tokens[1:5]):
            found[tokens[0].upper()] = DeviceTerminals(
                tokens[0].upper(), tokens[1].lower(), tokens[2].lower(),
                tokens[3].lower(), tokens[4].lower(),
            )
    if not found:
        raise InternalNoiseError(f"subckt {subckt!r} not found (or has no devices) in the DUT netlist")
    return found


def parse_subckt_pins(netlist_text: str, subckt: str) -> tuple[str, ...]:
    for raw in netlist_text.splitlines():
        tokens = raw.strip().lower().split()
        if len(tokens) > 1 and tokens[0] == ".subckt" and tokens[1] == subckt.lower():
            return tuple(t for t in tokens[2:] if "=" not in t)
    raise InternalNoiseError(f"subckt {subckt!r} not found in the DUT netlist")


def validate_block(block: dict) -> None:
    """Structural validation of the manifest block (no DUT needed)."""
    unknown = sorted(set(block) - set(BLOCK_KEYS))
    if unknown:
        raise InternalNoiseError(
            f"internal_noise has unknown key(s) {', '.join(unknown)}; known: {', '.join(BLOCK_KEYS)}"
        )
    for key in ("subckt", "inner", "instances", "ts", "devices", "rails"):
        if key not in block:
            raise InternalNoiseError(f"internal_noise is missing required key {key!r}")
    if not block["instances"]:
        raise InternalNoiseError("internal_noise.instances must name at least one DUT instance")
    if not (float(block["ts"]) > 0):
        raise InternalNoiseError("internal_noise.ts must be > 0")
    if float(block.get("scale", 1.0)) < 0:
        raise InternalNoiseError("internal_noise.scale must be >= 0")
    for name, spec in block["devices"].items():
        extra = sorted(set(spec) - set(DEVICE_KEYS))
        if extra:
            raise InternalNoiseError(f"device {name}: unknown key(s) {', '.join(extra)}")
        if not float(spec.get("g", 0)) > 0:
            raise InternalNoiseError(f"device {name}: 'g' (siemens) must be > 0")
        if not float(spec.get("gamma", 1.0)) > 0:
            raise InternalNoiseError(f"device {name}: 'gamma' must be > 0")
        if spec.get("phase", "always") not in PHASES:
            raise InternalNoiseError(f"device {name}: phase must be one of {', '.join(PHASES)}")


def _node(prefix: str, node: str, rails: dict[str, str]) -> str:
    """Top-level name of ``node`` of the inner subckt instance at ``prefix``.

    A node that is a pin of the inner subckt is NOT ``prefix.node`` in a
    flattened deck (the pin is wired to the parent's net), so only the rails
    the manifest maps explicitly may be used as a terminal; any other pin
    cannot be resolved here and is refused rather than guessed.
    """
    if node in rails:
        return rails[node]
    return f"{prefix}.{node}"


#: Reference temperature (K) at which the emitted TRNOISE amplitude is
#: computed; the B-source below rescales by sqrt(T/T_REF) at run time.
T_REF_K = 300.15


def na_at_tref(g: float, gamma: float, ts: float, scale: float) -> float:
    """TRNOISE NA (unit-A/V amplitude) giving ``scale*sqrt(4 k T_REF gamma g)``
    A/rtHz, via the relation S = NA*sqrt(2*TS)."""
    return scale * (4 * BOLTZMANN * T_REF_K * gamma * g / (2 * ts)) ** 0.5


def density_a_rthz(g: float, gamma: float, temp_c: float) -> float:
    """4kT*gamma*g one-sided density, A/rtHz (for reporting/tests)."""
    return (4 * BOLTZMANN * (temp_c + 273.15) * gamma * g) ** 0.5


def emit_internal_noise(block: dict, dut_text: str) -> list[str]:
    """Netlist lines for the requested internal noise sources.

    ``block`` is the manifest's ``internal_noise`` dict; ``dut_text`` the DUT
    netlist text (used only to resolve device terminals and to reject
    unknown device names / unresolvable pin terminals). An empty/None block
    returns ``[]`` (hook off).
    """
    if not block:
        return []
    validate_block(block)
    subckt = block["subckt"]
    devices = parse_subckt_devices(dut_text, subckt)
    pins = set(parse_subckt_pins(dut_text, subckt))
    rails = {str(k).lower(): str(v) for k, v in block["rails"].items()}
    ts = float(block["ts"])
    scale = float(block.get("scale", 1.0))
    clk_node = block.get("clk_node", "clk")
    vdd_node = block.get("vdd_node", "vdd")

    for dev_name in block["devices"]:
        if dev_name.upper() not in devices:
            raise InternalNoiseError(
                f"unknown device {dev_name!r} in subckt {subckt!r}; "
                f"known: {', '.join(sorted(devices))}"
            )

    out = [
        "* ---- internal-noise hook (sim/dut/README.md 'Optional internal-noise hook') ----",
        f"* devices={','.join(block['devices'])}  ts={ts!r}  scale={scale!r}  (white, channel thermal)",
    ]
    for inst in block["instances"]:
        prefix = f"{str(inst).lower()}.{str(block['inner']).lower()}"
        for dev_name, spec in block["devices"].items():
            term = devices[dev_name.upper()]
            terminals = []
            for node in (term.drain, term.source):
                if node in pins and node not in rails:
                    raise InternalNoiseError(
                        f"device {dev_name}: terminal {node!r} is a pin of {subckt!r} with no "
                        "entry in internal_noise.rails, so its top-level net is unknown"
                    )
                terminals.append(_node(prefix, node, rails))
            drain, source = terminals
            g = float(spec["g"])
            gamma = float(spec.get("gamma", 1.0))
            phase = spec.get("phase", "always")
            na = na_at_tref(g, gamma, ts, scale)
            tag = f"{str(inst).lower()}_{dev_name.lower()}"
            gate = {
                "always": "",
                "evaluate": f"*v({clk_node})/v({vdd_node})",
                "reset": f"*(1-v({clk_node})/v({vdd_node}))",
            }[phase]
            out.append(f"Vinz_{tag} inz_{tag} 0 dc 0 trnoise({na:.9e} {ts!r} 0 0)")
            out.append(
                f"Binz_{tag} {drain} {source} I = "
                f"'v(inz_{tag})*sqrt((temper+273.15)/{T_REF_K!r}){gate}'"
            )
    out.append("")
    return out

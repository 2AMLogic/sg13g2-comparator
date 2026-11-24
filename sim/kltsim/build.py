"""Compose ``klt sim`` netlist bodies and request documents.

A body is self-contained on purpose: the schematic DUT
(``design/comparator.spice``, bound by ``sim/dut.json``) is inlined
verbatim between markers that carry its SHA-256, so

* the envelope's own ``provenance.input.content_hash`` (the hash of the
  body ``klt sim`` simulated) transitively pins the exact DUT bytes, and
* ``kltsim.grade`` can re-derive, from the committed body alone, that the
  DUT inside it is today's ``design/comparator.spice`` and not a stale copy
  or the retired placeholder.

It also means the body needs no ``.include`` closure, so the pinned
``klt``'s ``batch`` backend (which uploads exactly one netlist file) ships
everything the deck needs.

TWO DEVIATIONS FROM ``klt sim``'s NETLIST-BODY CONVENTION, both forced:

1. **A ``.control`` block in the body that ``pre_osdi``-loads the PDK's
   OSDI device models.** SG13G2's ``sg13_lv_nmos``/``sg13_lv_pmos`` are
   PSP103 Verilog-A, loadable only by the ngspice control command
   ``pre_osdi``. The pinned ``klt`` (``2AMLogic/klayout-tools`` @
   ``e8ca621``) has no request field for it (``options.osdi_preload`` came
   later, klayout-tools#2513) and its generated ``.control`` block has no
   extension point, so the body is the only place it can go -- the same
   workaround ``sg13g2-bandgap`` verified on ngspice 46
   (klayout-tools#2666). The OSDI directory is host-specific: the batch
   image's ``/opt/pdk`` for committed campaign bodies, the local PDK for a
   local smoke run.
2. **Supply-tracking clocks** (in the bench circuits, not here): ``klt
   sim`` sweeps supply with ``alter <source>=<V>``, which does not reach a
   ``.param``-valued pulse amplitude. See each bench circuit's header.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from harness import internal_noise as internal_noise_mod

from . import artifacts as artifacts_mod
from .benches import MODELS, SUPPLIES_V, TEMPERATURES_C, Bench

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"
EXPERIMENT_DIR = SIM_DIR / "klt-corner-verification"
BENCH_DIR = EXPERIMENT_DIR / "benches"
DUT_JSON = SIM_DIR / "dut.json"

#: Every OSDI model the PDK's ngspice install ships, loaded whether or not
#: today's DUT instantiates it -- same policy as sim/harness/pdk.py's
#: REQUIRED_OSDI, so a DUT change never silently needs a new body shape.
OSDI_MODELS = ("psp103.osdi", "psp103_nqs.osdi", "r3_cmc.osdi", "mosvar.osdi")

#: The batch-runner image's baked PDK root (2AMLogic/2am
#: infra/aws/batch-image-pins.env BAKED_PDK_ROOT) and the variant's OSDI
#: directory under it (the ihp-sg13g2 artifact compiles psp103/psp103_nqs/
#: r3_cmc/mosvar into it).
BATCH_OSDI_DIR = "/opt/pdk/ihp-sg13g2/libs.tech/ngspice/osdi"

DUT_BEGIN = "* ==== BEGIN DUT"
DUT_END = "* ==== END DUT"

#: Study-only structural candidate netlists (issue #497): matched
#: integration-node capacitance on the input-pair drains. ``design/
#: comparator.spice`` itself is never edited; a candidate is that file plus
#: one matched capacitor pair in the latch core and one in the loop-broken
#: reduced sub-model, and both build and grade re-derive the candidate from
#: TODAY's base bytes, so it can never silently drift from the schematic it
#: modifies.
CANDIDATES_DIR = SIM_DIR / "comparator-integration-capacitance" / "candidates"

#: Body-header marker naming the structural candidate a body was built from
#: (issue #497). ``kltsim.grade`` verifies the embedded DUT against the named
#: reference FILE (an independent path + sha256), not just against the body.
CANDIDATE_MARKER = (
    "*   CANDIDATE NETLIST (issue #497 integration-capacitance study; "
    "design/comparator.spice untouched):")

#: The matched capacitors a candidate adds, per subckt: (instance, node)
#: pairs -- each capacitor runs from its node to the subckt's ``vss`` rail --
#: plus the header comment. Equal value per side by construction.
_CANDIDATE_CAPS = {
    "comparator": (
        (("C497P", "np"), ("C497N", "nn")),
        ("* issue #497: matched integration-node capacitance, per side, "
         "node to the vss rail"),
    ),
    "comparator_dut_analog": (
        (("C497AP", "aon"), ("C497AN", "aop")),
        ("* issue #497: the same per-side capacitance at the loop-broken "
         "model's integration\n* nodes (np maps to aon, nn maps to aop)"),
    ),
}

#: the SPICE capacitance values a candidate may declare (verbatim tokens)
_CAP_VALUE_RE = re.compile(r"[0-9.]+e-?[0-9]+|[0-9.]+[pfn]F?", re.IGNORECASE)


def _subckt_ends_insert(text: str, insertions: dict) -> str:
    """``text`` with each subckt's block of ``insertions`` added immediately
    before its ``.ends`` line (only the named subckts; everything else
    byte-identical)."""
    out: list[str] = []
    subckt = None
    for line in text.split("\n"):
        if line.startswith(".subckt "):
            subckt = line.split()[1]
        elif line.startswith(".ends") and subckt in insertions:
            out.extend(insertions[subckt])
            subckt = None
        out.append(line)
    return "\n".join(out)


def compose_candidate_netlist(cap: str, dut_json: Path = DUT_JSON) -> str:
    """``design/comparator.spice`` plus the matched per-side integration-node
    capacitors ``cap`` (a verbatim SPICE value, e.g. ``"2f"``): the exact
    bytes a committed candidate netlist must hold."""
    if not isinstance(cap, str) or not _CAP_VALUE_RE.fullmatch(cap.strip()):
        raise BuildError(f"candidate capacitance {cap!r} is not a plain SPICE value")
    binding = load_dut_binding(dut_json)
    base = binding["_netlist_path"].read_text(encoding="utf-8")
    insertions = {
        name: list(comment.split("\n")) + [f"{inst} {node} vss {cap.strip()}"
                                           for inst, node in pairs]
        for name, (pairs, comment) in _CANDIDATE_CAPS.items()
    }
    return _subckt_ends_insert(base, insertions)


def candidate_caps(text: str) -> dict[str, str]:
    """The per-side capacitance a candidate text declares per subckt, e.g.
    ``{"comparator": "2f", "comparator_dut_analog": "2f"}`` (``{}`` when the
    text declares none). Only capacitor lines of the exact generated shape
    (``C<inst> <node> vss <value>`` on the studied nodes) count."""
    caps: dict[str, str] = {}
    subckt = None
    for line in text.split("\n"):
        if line.startswith(".subckt "):
            subckt = line.split()[1]
        elif subckt in _CANDIDATE_CAPS:
            for inst, node in _CANDIDATE_CAPS[subckt][0]:
                prefix = f"{inst} {node} vss "
                if line.startswith(prefix) and " " not in line[len(prefix):]:
                    caps[subckt] = line[len(prefix):]
    return caps


def check_candidate_netlist(text: str, dut_json: Path = DUT_JSON) -> str:
    """The per-side capacitance value of a candidate netlist, after verifying
    it IS today's DUT plus exactly the two matched capacitor pairs and
    nothing else. Raises ``BuildError`` naming the deviation otherwise."""
    caps = candidate_caps(text)
    if set(caps) != set(_CANDIDATE_CAPS):
        raise BuildError(
            "candidate netlist must declare the matched capacitor pair in both "
            "`.subckt comparator' (np/nn) and `.subckt comparator_dut_analog' "
            f"(aon/aop); found {sorted(caps) or 'none'}")
    values = set(caps.values())
    if len(values) != 1:
        raise BuildError(
            f"candidate capacitance differs across sides or subckts: {sorted(caps.items())}")
    value = next(iter(values))
    if compose_candidate_netlist(value, dut_json) != text:
        raise BuildError(
            "candidate netlist is not today's design/comparator.spice plus exactly "
            "the two matched capacitor pairs (re-derived bytes differ; the base "
            "DUT or the candidate changed since it was written)")
    return value


def cap_to_farads(value: str) -> float:
    """A SPICE capacitor value to farads (``f``/``p``/``n`` suffixes and
    plain e-notation)."""
    token = value.strip()
    scale = {"f": 1e-15, "p": 1e-12, "n": 1e-9}
    if token[-1:].lower() in scale:
        return float(token[:-1]) * scale[token[-1:].lower()]
    if token[-1:].upper() == "F":  # bare farads
        return float(token[:-1])
    return float(token)


def candidate_netlist_path(name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name or ""):
        raise BuildError(f"candidate name {name!r} is not a plain file name")
    return CANDIDATES_DIR / f"{name}.spice"


def load_candidate(name: str, dut_json: Path = DUT_JSON) -> tuple[str, Path, bytes]:
    """Resolve a named candidate to ``(name, path, bytes)``, refusing a name
    that is unknown, or whose file is not today's DUT plus exactly the
    matched capacitors."""
    path = candidate_netlist_path(name)
    if not path.is_file():
        raise BuildError(f"unknown candidate {name!r}: {path} does not exist")
    text = path.read_text(encoding="utf-8")
    check_candidate_netlist(text, dut_json)
    return name, path, text.encode("utf-8")


def extract_candidate(body_text: str) -> dict:
    """The structural candidate a body declares (``{"name": ..., "path": ...,
    "sha256": ...}``, the sha256 of the candidate FILE's bytes), or ``{}``."""
    for line in body_text.split("\n"):
        if line.startswith(CANDIDATE_MARKER):
            out = {}
            for item in line[len(CANDIDATE_MARKER):].split():
                key, sep, value = item.partition("=")
                if sep:
                    out[key] = value
            return out
    return {}


class BuildError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def load_dut_binding(dut_json: Path = DUT_JSON) -> dict:
    """Read sim/dut.json and refuse anything but the schematic DUT."""
    binding = json.loads(Path(dut_json).read_text(encoding="utf-8"))
    if binding.get("provenance") != "schematic":
        raise BuildError(
            f"sim/dut.json provenance is {binding.get('provenance')!r}, not "
            "'schematic': this campaign measures the ratified schematic DUT "
            "only (a placeholder or extracted binding is a different claim)"
        )
    netlist = (Path(dut_json).parent / binding["netlist"]).resolve()
    if not netlist.is_file():
        raise BuildError(f"DUT netlist {netlist} does not exist")
    binding["_netlist_path"] = netlist
    return binding


def compose_fixture_body(bench: Bench) -> str:
    """Body of a DUT-free instrument fixture: header + the circuit only.

    No OSDI ``.control`` block and no DUT: the deck instantiates no PDK
    device, so nothing needs loading (and nothing is hidden in an include).
    """
    circuit_path = BENCH_DIR / bench.circuit
    circuit_text = circuit_path.read_text(encoding="utf-8")
    circuit_rel = circuit_path.relative_to(REPO_ROOT).as_posix()
    return "\n".join([
        f"* {bench.name} -- klt sim netlist BODY (sim/klt-corner-verification, issue #78)",
        "* GENERATED by `python3 sim/run_klt_corner_verification.py fixture` -- do not edit.",
        f"*   circuit: {circuit_rel}  sha256={sha256_bytes(circuit_text.encode('utf-8'))}",
        "*   no DUT, no OSDI: an ideal-current-source known-charge fixture.",
        "*",
        circuit_text.rstrip("\n"),
        "",
    ])


def compose_fixture_request(bench: Bench, netlist_name: str) -> dict:
    """A single-unit, local-backend request (one corner: tt / 1.2 V / 27 C;
    the deck has no DUT so the corner is immaterial)."""
    request = compose_request(bench, netlist_name, "local")
    request["_comment"][0] = (
        f"sg13g2-comparator -- klt sim request, fixture `{bench.name}` (issue #78)."
    )
    request["corners"] = {
        "process": list(bench.process_sections),
        "supply_v": {key: [1.2] for key in bench.supply_keys},
        "temperature_c": [27],
    }
    return request


#: Marker of a body header line that declares structural (geometry)
#: overrides applied to the inlined DUT (issue #92). ``kltsim.grade``
#: re-applies exactly these to today's design/comparator.spice and requires
#: the embedded DUT to equal the result, so a sizing candidate is accepted
#: as "today's DUT plus the stated geometry" and nothing else.
GEOMETRY_MARKER = "*   GEOMETRY OVERRIDE (issue #92 sizing study; design/comparator.spice untouched):"

#: instance fields the sizing study may override. Only instances of the
#: top-level `comparator` subcircuit (the DR-0001 latch), never the bias
#: mirror or the dut wrapper.
GEOMETRY_FIELDS = ("w", "l")


def parse_geometry(items) -> dict:
    """``["XM1.w=16u", ...]`` -> ``{"XM1.w": "16u"}`` (values kept verbatim)."""
    out = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or "." not in key or not value:
            raise BuildError(f"geometry override {item!r}: expected INSTANCE.field=VALUE")
        out[key.strip()] = value.strip()
    return out


def apply_geometry(dut_text: str, geometry: dict) -> str:
    """Return ``dut_text`` with ``INSTANCE.w|l=VALUE`` applied to instances of
    the ``comparator`` subcircuit. Refuses unknown instances/fields, so a
    typo cannot silently leave the DUT unchanged."""
    lines = dut_text.split("\n")
    in_top = False
    remaining = dict(geometry)
    for index, line in enumerate(lines):
        if line.startswith(".subckt "):
            in_top = line.split()[1] == "comparator"
        elif line.startswith(".ends"):
            in_top = False
        if not in_top or not line.startswith("X"):
            continue
        inst = line.split()[0]
        for key in [k for k in remaining if k.split(".", 1)[0] == inst]:
            field = key.split(".", 1)[1]
            if field not in GEOMETRY_FIELDS:
                raise BuildError(f"geometry override {key!r}: field must be one of {GEOMETRY_FIELDS}")
            new, count = re.subn(rf"(\s{field}=)\S+", rf"\g<1>{remaining[key]}", line, count=1)
            if count != 1:
                raise BuildError(f"geometry override {key!r}: instance has no {field}= field")
            line = new
            del remaining[key]
        lines[index] = line
    if remaining:
        raise BuildError(
            f"geometry override of {sorted(remaining)}: no such instance in `.subckt comparator`")
    return "\n".join(lines)


def extract_geometry(body_text: str) -> dict:
    """The geometry overrides a body declares (``{}`` when none)."""
    for line in body_text.split("\n"):
        if line.startswith(GEOMETRY_MARKER):
            return parse_geometry(line[len(GEOMETRY_MARKER):].split())
    return {}


PARAM_MARKER = "*   OVERRIDE (issue #80 sweep; sim/dut.json untouched):"


def extract_param_overrides(body_text: str) -> dict:
    """The ``sim/dut.json`` param overrides a body declares (``{}`` when none),
    as ``{"dut_ib": "1.5e-05"}`` (values kept verbatim)."""
    for line in body_text.split("\n"):
        if line.startswith(PARAM_MARKER):
            out = {}
            for item in line[len(PARAM_MARKER):].split(","):
                key, sep, value = item.strip().partition("=")
                if sep:
                    out[key] = value.strip("'\"")
            return out
    return {}


def compose_body(bench: Bench, osdi_dir: str, dut_json: Path = DUT_JSON,
                 param_overrides: dict | None = None,
                 geometry_overrides: dict | None = None,
                 candidate: tuple[str, Path] | None = None) -> str:
    """``param_overrides`` replaces named ``sim/dut.json`` operating-point
    parameters in the emitted ``.param`` lines only (issue #80's bias-point
    sweep). The file itself is never edited, and each override is stated in
    the body header so it is visible in the hashed netlist.

    ``geometry_overrides`` (issue #92) rewrites instance w/l fields inside
    ``.subckt comparator`` only, declared in the body header the same way.

    ``candidate`` (issue #497) is ``(name, path)`` of a study-only structural
    candidate netlist that replaces ``design/comparator.spice`` as the inlined
    DUT (geometry still applies on top). The candidate must BE today's DUT
    plus exactly the matched integration-node capacitors, verified here and
    again at grading against the file's own bytes."""
    binding = load_dut_binding(dut_json)
    params = dict(binding.get("params") or {})
    for key in (param_overrides or {}):
        if key not in params:
            raise BuildError(f"override of {key!r}: not a sim/dut.json param")
    params.update(param_overrides or {})
    dut_path: Path = binding["_netlist_path"]
    base_bytes = dut_path.read_bytes()
    dut_bytes = base_bytes
    cand_name = cand_rel = None
    cand_bytes: bytes | None = None
    if candidate is not None:
        cand_name, cand_path = candidate[0], Path(candidate[1])
        cand_text = cand_path.read_text(encoding="utf-8")
        check_candidate_netlist(cand_text, dut_json)
        cand_bytes = cand_text.encode("utf-8")
        dut_bytes = cand_bytes
        try:
            cand_rel = cand_path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:  # a test fixture outside the repo
            cand_rel = str(cand_path)
    if geometry_overrides:
        dut_bytes = apply_geometry(dut_bytes.decode("utf-8"), geometry_overrides).encode("utf-8")
    dut_text = dut_bytes.decode("utf-8")
    circuit_path = BENCH_DIR / bench.circuit
    circuit_text = circuit_path.read_text(encoding="utf-8")
    try:
        dut_rel = dut_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:  # a test fixture outside the repo
        dut_rel = dut_path.name
    circuit_rel = circuit_path.relative_to(REPO_ROOT).as_posix()

    lines = [
        f"* {bench.name} -- klt sim netlist BODY (sim/klt-corner-verification, issue #62)",
        "* GENERATED by `python3 sim/run_klt_corner_verification.py build` -- do not edit;",
        "* edit the inputs below and rebuild.",
        f"*   circuit: {circuit_rel}  sha256={sha256_bytes(circuit_text.encode('utf-8'))}",
        f"*   DUT:     {dut_rel}  sha256={sha256_bytes(dut_bytes)}",
        f"*            sim/dut.json id={binding.get('id')} provenance={binding.get('provenance')}",
        f"*   OSDI:    {osdi_dir}",
    ]
    if param_overrides:
        lines.append(
            "*   OVERRIDE (issue #80 sweep; sim/dut.json untouched): "
            + ", ".join(f"{k}={v!r}" for k, v in sorted(param_overrides.items()))
        )
    if cand_bytes is not None:
        lines.append(CANDIDATE_MARKER
                     + f" name={cand_name} path={cand_rel} sha256={sha256_bytes(cand_bytes)}")
    if geometry_overrides:
        lines.append(GEOMETRY_MARKER + " "
                     + " ".join(f"{k}={v}" for k, v in sorted(geometry_overrides.items())))
        if cand_bytes is None:
            lines.append(f"*   base DUT (unmodified) sha256={sha256_bytes(base_bytes)}")
        else:
            lines.append(f"*   base candidate {cand_name} (unmodified) sha256={sha256_bytes(cand_bytes)}")
    lines += [
        "*",
        "* klt sim netlist-body convention: no .lib / .temp / analysis / .end here --",
        "* klt sim generates those per corner around an .include of this file. The",
        "* .control block below is the one deliberate deviation (see",
        "* sim/kltsim/build.py): SG13G2's MOS models are OSDI and must be",
        "* pre_osdi-loaded before the circuit is parsed, and the pinned klt has no",
        "* request field for that.",
        ".control",
    ]
    lines += [f"pre_osdi {osdi_dir.rstrip('/')}/{name}" for name in OSDI_MODELS]
    lines += [".endc", "", "* ---- DUT operating point (sim/dut.json params) ----"]
    for key, value in sorted(params.items()):
        lines.append(f".param {key}={value!r}")
    if bench.params:
        lines += ["", "* ---- bench parameters (sim/kltsim/benches.py) ----"]
        for key, value in sorted(bench.params.items()):
            lines.append(f".param {key}={value!r}")
    dut_block_rel = dut_rel if cand_bytes is None else cand_rel
    lines += [
        "",
        f"{DUT_BEGIN} {dut_block_rel} sha256={sha256_bytes(dut_bytes)} ====",
        dut_text.rstrip("\n"),
        f"{DUT_END} ====",
        "",
        circuit_text.rstrip("\n"),
        "",
    ]
    if bench.internal_noise:
        # Optional hook (issue #81): sources on named internal devices.
        lines += internal_noise_mod.emit_internal_noise(bench.internal_noise, dut_text)
    return "\n".join(lines)


def extract_dut_block(body_text: str) -> tuple[str | None, str | None, str | None]:
    """Return (declared_path, declared_sha256, embedded_text) from a body.

    ``(None, None, None)`` when the body carries no DUT block at all.
    """
    begin = end = None
    lines = body_text.split("\n")
    for index, line in enumerate(lines):
        if begin is None and line.startswith(DUT_BEGIN):
            begin = index
        elif begin is not None and line.startswith(DUT_END):
            end = index
            break
    if begin is None or end is None:
        return None, None, None
    header = lines[begin][len(DUT_BEGIN):].strip().rstrip("=").strip()
    parts = header.split()
    declared_path = parts[0] if parts else None
    declared_sha = None
    for part in parts[1:]:
        if part.startswith("sha256="):
            declared_sha = part.split("=", 1)[1]
    embedded = "\n".join(lines[begin + 1:end]) + "\n"
    return declared_path, declared_sha, embedded


def compose_request(
    bench: Bench, netlist_name: str, backend: str, processes: tuple[str, ...] | None = None
) -> dict:
    corners: dict = {
        "process": list(processes or bench.process_sections),
        "supply_v": {key: list(SUPPLIES_V) for key in bench.supply_keys},
        "temperature_c": list(TEMPERATURES_C),
    }
    request: dict = {
        "_comment": [
            f"sg13g2-comparator -- klt sim request, bench `{bench.name}` (issue #62).",
            "GENERATED by `python3 sim/run_klt_corner_verification.py build`; the",
            "committed copy is byte-for-byte what was submitted.",
            bench.description,
            "limits encode DR-0002 TARGET bounds and validity gates only; Stretch",
            "verdicts are graded by sim/kltsim/grade.py from the same per-corner",
            "values (see sim/kltsim/benches.py).",
        ],
        "engine": "ngspice",
        "netlist": netlist_name,
        "netlist_source": "schematic",
        "backend": backend,
        "models": dict(MODELS),
        "corners": corners,
        "analysis": dict(bench.analysis),
        "measurements": [m.request_entry() for m in bench.measurements],
        "options": {"timeout_s": bench.timeout_s, "keep_artifacts": True},
    }
    if bench.monte_carlo is not None:
        request["monte_carlo"] = dict(bench.monte_carlo)
    if backend == "batch" and bench.hosts > 1:
        request["remote"] = {"hosts": bench.hosts}
    return request


def part_tags(bench: Bench) -> list[str]:
    """Request-part tags for a bench: one request per bench, or (for a bench
    with ``split_by_process``) one per process corner, so each part fits one
    batch job's wall-clock limit and is retried on its own."""
    if not bench.split_by_process:
        return [bench.name]
    return [f"{bench.name}.{section}" for section in bench.process_sections]


def plan_bench_inputs(
    bench: Bench,
    out_dir: Path,
    *,
    target: str,
    osdi_dir: str | None = None,
    split: bool = True,
    param_overrides: dict | None = None,
    geometry_overrides: dict | None = None,
    candidate: tuple[str, Path] | None = None,
) -> tuple[Path, list[Path], list[tuple[Path, bytes]]]:
    """Compose (without writing) ``<bench>.body.spice`` and its request(s).

    Returns ``(body_path, request_paths, files)`` where ``files`` is every
    ``(destination, bytes)`` pair, body first.

    ``target`` is ``batch`` (the committed campaign form: OSDI from the
    batch image, ``backend: batch``) or ``local`` (a single-corner smoke
    form against this host's PDK; never committed). With ``split`` (the
    default) a ``split_by_process`` bench gets one request per process
    corner, all sharing the one body. ``candidate`` (issue #497) inlines a
    named structural candidate netlist as the DUT instead of the schematic.
    """
    if target not in ("batch", "local"):
        raise BuildError(f"unknown target {target!r}")
    if target == "batch":
        osdi_dir = BATCH_OSDI_DIR
    elif not osdi_dir:
        raise BuildError("a local build needs --osdi-dir (this host's PDK OSDI directory)")
    body_name = f"{bench.name}.body.spice"
    body_path = out_dir / body_name
    files: list[tuple[Path, bytes]] = [(
        body_path,
        compose_body(bench, osdi_dir, param_overrides=param_overrides,
                     geometry_overrides=geometry_overrides,
                     candidate=candidate).encode("utf-8"),
    )]
    backend = "batch" if target == "batch" else "local"
    requests: list[Path] = []
    if split and bench.split_by_process:
        for tag, section in zip(part_tags(bench), bench.process_sections):
            request = compose_request(bench, body_name, backend, processes=(section,))
            requests.append(out_dir / f"{tag}.request.json")
            files.append((requests[-1], (json.dumps(request, indent=2) + "\n").encode("utf-8")))
    else:
        request = compose_request(bench, body_name, backend)
        requests.append(out_dir / f"{bench.name}.request.json")
        files.append((requests[-1], (json.dumps(request, indent=2) + "\n").encode("utf-8")))
    return body_path, requests, files


def commit_inputs(files: list[tuple[Path, bytes]]) -> list[Path]:
    """Append-only write of a complete, precomputed input set.

    Preflight first: every destination that already exists must hold exactly
    the proposed bytes, else the whole set is rejected (``BuildError`` naming
    each conflicting input and pointing at a new campaign ID) before ANY file
    is touched. A destination directory that is not a real directory, or that
    sits under a non-directory ancestor, is rejected the same way (issue
    #523) rather than escaping as a bare ``FileExistsError`` /
    ``NotADirectoryError``. Identical files are reused without a write;
    absent files are created with exclusive creation (``x``), so a
    concurrent writer cannot be clobbered between check and write. Returns
    the paths newly created.
    """
    try:
        return artifacts_mod.commit(
            files,
            differs="existing content differs from the proposed content",
            dup="selected benches propose two different contents")
    except artifacts_mod.ArtifactConflict as exc:
        if exc.concurrent:
            raise BuildError(
                f"{exc.conflicts[0]}; use a NEW campaign ID") from None
        raise BuildError(
            "refusing to rebuild: campaign inputs are append-only evidence and "
            "nothing was written. Conflicting input(s):\n  "
            + "\n  ".join(exc.conflicts)
            + "\nThe DUT, its parameters or a bench definition changed since this "
            "campaign's inputs were built. Rebuild under a NEW campaign ID "
            "(`build --campaign <new-id>`) instead of replacing these files."
        ) from None


def write_bench_inputs(
    bench: Bench,
    out_dir: Path,
    *,
    target: str,
    osdi_dir: str | None = None,
    split: bool = True,
    param_overrides: dict | None = None,
    geometry_overrides: dict | None = None,
    candidate: tuple[str, Path] | None = None,
) -> tuple[Path, list[Path]]:
    """Write a bench's inputs, OVERWRITING (disposable smoke directories and
    the fleet-smoke scratch path only). Campaign builds use
    :func:`plan_bench_inputs` + :func:`commit_inputs` instead."""
    body_path, requests, files = plan_bench_inputs(
        bench, out_dir, target=target, osdi_dir=osdi_dir, split=split,
        param_overrides=param_overrides, geometry_overrides=geometry_overrides,
        candidate=candidate)
    out_dir.mkdir(parents=True, exist_ok=True)
    for path, data in files:
        path.write_bytes(data)
    return body_path, requests

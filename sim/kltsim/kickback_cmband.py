"""Kickback residue across a bounded input common-mode band (issue #165).

CHARACTERIZATION FOR THE CANDIDATE DR-0004 COMMON-MODE ROW, NOT RATIFICATION.
Every kickback record to date runs at ``dut_vcm`` only. This module builds,
validates and grades three deterministic ``klt sim`` corner campaigns of the
issue #62 ``kickback`` bench at ``dut_vcm`` -/+ 50 mV and at ``dut_vcm`` (the
reproduction gate), and compares them per PVT point.

CONDITION. The bench is unchanged in every respect but one source line

    vcm  cm 0 dc {dut_vcm}              (note the two spaces in the body)

which becomes

    .param vcm_delta=<delta>
    vcm cm 0 dc {dut_vcm+vcm_delta}

for all three conditions, the nominal one included (``vcm_delta=0.0``). The
match is whitespace tolerant and must hit exactly ONE line (zero or several
is an error). This is deliberately a separate transform from
``cmband.apply_transform``, which rewrites the offset bench's single-space
line and builds a Monte-Carlo bench; the kickback bench is deterministic
(``tran 5p 60n``, no Monte Carlo, no seeds).

VALIDITY. A grid point is VALID only if its corner reported, exactly once,
every measurement the reference request names with a finite value; did not
error; carries supply and temperature probes that match the corner; carries
a ``vcm_meas`` probe equal to the condition's common mode; and passed the
three decision-correctness gates. A charge-limit (``qkick_fc``) failure does
NOT invalidate a point: the Q_kick sub-bound is already NOT MET at nominal
(DR-0003), is not part of the candidate row's hold list, and is reported
beside the residue, never folded into it. A rejected point is named with its
reason; nothing is substituted for it.

GRADING. Only valid ``kick_sigdep_uv`` values are graded, against the
unchanged ratified Row 4 residue Target (<= 100 uV) and Stretch (<= 30 uV).
A condition with fewer than 45 valid points is INCOMPLETE, never MET.

REPRODUCTION GATE. ``vcm-nom`` must equal the issue #62 campaign's kickback
envelope on every ORIGINAL measurement value (exact float equality) at all
45 PVT keys, with matching model library, engine, analysis, corner grid,
original measurement cards and limits, and declared circuit/DUT hashes. The
added probe and the new netlist/invocation metadata are excluded. If it
fails, the series is excluded from DR-0004 evidence.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import build as build_mod
from . import grade as grade_mod
from .benches import KICKBACK, Meas, PROCESSES, SUPPLIES_V, TEMPERATURES_C

EXPERIMENT_DIR = build_mod.SIM_DIR / "comparator-kickback-cm-band"
SERIES_DIR = EXPERIMENT_DIR / "campaigns"

BENCH_NAME = KICKBACK.name  # "kickback" (grade.py looks the bench up by name)
TAG = BENCH_NAME
BODY_NAME = f"{BENCH_NAME}.body.spice"

REFERENCE_CAMPAIGN = "20261009-d73a9ac"
REFERENCE_DIR = build_mod.EXPERIMENT_DIR / "campaigns" / REFERENCE_CAMPAIGN

#: Match the one common-mode source whatever the spacing.
VCM_RE = re.compile(r"^vcm\s+cm\s+0\s+dc\s+\{dut_vcm\}\s*$")
VCM_LINE_CM = "vcm cm 0 dc {dut_vcm+vcm_delta}"
CONDITION_MARK = "* ---- CM-band condition (issue #165):"

#: Ratified DR-0002 Row 4 residue bounds (unchanged; quoted, not edited).
RESIDUE_TARGET_UV = 100.0
RESIDUE_STRETCH_UV = 30.0
RESIDUE = "kick_sigdep_uv"
GATES = ("dout_1k_end", "dout_float_small_end", "dout_float_big_end")
REPORTED = ("kick_sigdep_uv", "qkick_p_fc", "qkick_n_fc", "qkick_fc", "kick_1k_peak_mv",
            "kick_cm_uv")

VCM_PROBE = Meas("vcm_meas", ".meas tran vcm_meas find v(cm) at=5n", "V", role="probe")
VCM_TOL_V = 1e-6


class KickbackCmBandError(RuntimeError):
    pass


@dataclass(frozen=True)
class Condition:
    name: str
    delta_v: float

    def vcm_v(self) -> float:
        base = float((build_mod.load_dut_binding().get("params") or {})["dut_vcm"])
        return round(base + self.delta_v, 9)


CONDITIONS = (
    Condition("vcm-m050", -0.05),
    Condition("vcm-nom", 0.0),
    Condition("vcm-p050", 0.05),
)
NOMINAL = "vcm-nom"


def condition(name: str) -> Condition:
    for cond in CONDITIONS:
        if cond.name == name:
            return cond
    raise KickbackCmBandError(f"unknown condition {name!r}; known: {[c.name for c in CONDITIONS]}")


def expected_keys() -> list[tuple[str, float, float]]:
    """The 45 grid points, in the reference request's order."""
    return [(p, round(float(v), 6), float(t))
            for p in PROCESSES for v in SUPPLIES_V for t in TEMPERATURES_C]


def key_str(key) -> str:
    return f"{key[0]}/{key[1]:.3f}V/{key[2]:g}C"


# --------------------------------------------------------------------------- #
# body + request
# --------------------------------------------------------------------------- #


def bench_for(cond: Condition):
    """The #62 kickback bench plus the ``vcm_meas`` probe; nothing else."""
    return dataclasses.replace(
        KICKBACK, measurements=KICKBACK.measurements + (VCM_PROBE,),
        description=(
            f"CHARACTERIZATION (issue #165), condition {cond.name}: kickback residue at input "
            f"common mode dut_vcm{cond.delta_v * 1e3:+.0f} mV. Unchanged issue #62 kickback "
            "bench except the common-mode source and one added probe."))


def apply_transform(body: str, cond: Condition) -> str:
    lines = body.split("\n")
    hits = [i for i, line in enumerate(lines) if VCM_RE.match(line)]
    if len(hits) != 1:
        raise KickbackCmBandError(
            f"expected exactly one common-mode source line (vcm cm 0 dc {{dut_vcm}}) in the "
            f"kickback body, found {len(hits)}")
    i = hits[0]
    lines[i:i + 1] = [
        f"{CONDITION_MARK} {cond.name}, input common mode = dut_vcm + vcm_delta",
        f".param vcm_delta={cond.delta_v!r}",
        VCM_LINE_CM,
    ]
    if len(lines) < 3:
        raise KickbackCmBandError("kickback body has no header")
    lines[0] = (f"* {BENCH_NAME} -- klt sim netlist BODY (sim/comparator-kickback-cm-band, "
                f"issue #165) condition={cond.name} vcm_delta={cond.delta_v!r}")
    lines[1] = ("* GENERATED by `python3 sim/run_kickback_cm_band.py build` from the issue #62 "
                "kickback body (sim/kltsim/kickback_cmband.py) -- do not edit;")
    return "\n".join(lines)


def undo_transform(body: str) -> str:
    """Inverse of the line rewrite (header lines 0/1 excepted) -- tests/audit.
    The restored source line is the canonical single-space form."""
    out = []
    for line in body.split("\n"):
        if line.startswith(CONDITION_MARK) or line.startswith(".param vcm_delta="):
            continue
        out.append("vcm cm 0 dc {dut_vcm}" if line == VCM_LINE_CM else line)
    return "\n".join(out)


def compose_body(cond: Condition, osdi_dir: str = build_mod.BATCH_OSDI_DIR) -> str:
    return apply_transform(build_mod.compose_body(KICKBACK, osdi_dir), cond)


def condition_metadata(cond: Condition) -> dict:
    return {
        "issue": 165,
        "name": cond.name,
        "vcm_delta_v": cond.delta_v,
        "vcm_v": cond.vcm_v(),
        "scope": "characterization for candidate DR-0004 CM row (no ratified CM range)",
    }


def _reference_order(measurements: list[dict]) -> list[dict]:
    """Order the measurement cards exactly as the reference (#62) request has
    them, the added probe last. The committed reference was generated before
    benches.py's Q_kick cards were reordered; the cards are identical but the
    request must be the reference's own, not a lookalike. Any content
    difference (not just order) is an error."""
    ref = json.loads((REFERENCE_DIR / f"{TAG}.request.json").read_text(encoding="utf-8"))
    ordered = list(ref["measurements"]) + [VCM_PROBE.request_entry()]
    key = lambda m: json.dumps(m, sort_keys=True)  # noqa: E731
    if sorted(map(key, ordered)) != sorted(map(key, measurements)):
        raise KickbackCmBandError(
            "the kickback bench's measurement cards differ in content from the reference "
            f"request {REFERENCE_CAMPAIGN}; refusing to build a non-identical campaign")
    return ordered


def compose_request(cond: Condition, body_name: str = BODY_NAME, backend: str = "batch") -> dict:
    bench = bench_for(cond)
    request = build_mod.compose_request(bench, body_name, backend)
    request["measurements"] = _reference_order(request["measurements"])
    request["_comment"] = [
        f"sg13g2-comparator -- klt sim request, CM-band kickback condition `{cond.name}` "
        "(issue #165).",
        "GENERATED by `python3 sim/run_kickback_cm_band.py build`; the committed copy is "
        "byte-for-byte what was submitted.",
        bench.description,
        "Grid, analysis, measurements and limits are the issue #62 kickback bench's, "
        "unchanged, plus the vcm_meas probe. Deterministic: no monte_carlo.",
    ]
    request["_condition"] = condition_metadata(cond)
    return request


def input_bytes(cond: Condition, osdi_dir: str = build_mod.BATCH_OSDI_DIR,
                backend: str = "batch") -> dict[str, bytes]:
    """File name -> exact bytes of the body and the request for a condition."""
    return {
        BODY_NAME: compose_body(cond, osdi_dir).encode("utf-8"),
        f"{TAG}.request.json": (json.dumps(compose_request(cond, BODY_NAME, backend), indent=2)
                                + "\n").encode("utf-8"),
    }


def write_condition_inputs(cond: Condition, out_dir: Path, **kw) -> list[Path]:
    """Write body + request; refuse to change anything already there."""
    files = input_bytes(cond, **kw)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = out_dir / name
        if path.exists() and path.read_bytes() != data:
            raise KickbackCmBandError(
                f"{path} exists and differs -- campaign evidence is append-only; use a new --series")
    paths = []
    for name, data in files.items():
        path = out_dir / name
        if not path.exists():
            path.write_bytes(data)
        paths.append(path)
    return paths


# --------------------------------------------------------------------------- #
# validity
# --------------------------------------------------------------------------- #


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _num(index: dict, name: str):
    m = index.get(name)
    if m is None or m.get("value") is None:
        return None
    try:
        return grade_mod.finite(m["value"], name)
    except grade_mod.NonFiniteError:
        return None


def point_problem(corner: dict, vcm_v: float, required: list[str]) -> str | None:
    """Why this corner's numbers cannot be trusted, or None."""
    problem = grade_mod._corner_problems(corner, BENCH_NAME, list(GATES))
    if problem:
        return problem
    index, bad = grade_mod.measurement_index(corner)
    if bad:
        return bad
    probe = index.get(VCM_PROBE.name)
    if probe is None or probe.get("value") is None:
        return "common-mode probe vcm_meas missing"
    try:
        pv = grade_mod.finite(probe["value"], "vcm_meas")
    except grade_mod.NonFiniteError as exc:
        return f"invalid numeric evidence: {exc}"
    if abs(pv - vcm_v) > VCM_TOL_V:
        return f"common-mode probe vcm_meas={probe['value']} V is not the condition's {vcm_v} V"
    for name in required:
        if _num(index, name) is None:
            return f"measurement {name} missing or not finite"
    return None


def load_points(envelope: dict) -> tuple[dict, list[str]]:
    """key -> corner for the expected grid; plus structural findings
    (duplicates, unplaceable and off-grid corners)."""
    seen: dict[tuple, list[dict]] = {}
    notes: list[str] = []
    for corner in envelope.get("corners") or []:
        if corner.get("monte_carlo") is not None:
            notes.append(f"unexpected Monte-Carlo corner {corner.get('corner_id')}")
            continue
        key = grade_mod._corner_key(corner)
        if key is None:
            notes.append(f"unplaceable corner {corner.get('corner_id')}")
            continue
        seen.setdefault(key, []).append(corner)
    grid = set(expected_keys())
    for key in sorted(seen, key=str):
        if key not in grid:
            notes.append(f"off-grid corner {key_str(key)}")
    for key, v in sorted(seen.items(), key=lambda kv: str(kv[0])):
        if len(v) > 1:
            notes.append(f"duplicate result for {key_str(key)}: "
                         f"{sorted(str(c.get('corner_id')) for c in v)}; no result selected")
    return {k: v[0] for k, v in seen.items() if len(v) == 1}, notes


def required_measurements() -> list[str]:
    return [m.name for m in KICKBACK.measurements]


def evaluate_condition(cond: Condition, envelope: dict) -> dict:
    """Per-point validity + values, and condition-level residue statistics."""
    corners, notes = load_points(envelope)
    dupes = {n.split(" for ")[1].split(":")[0] for n in notes if n.startswith("duplicate")}
    vcm_v = cond.vcm_v()
    required = required_measurements()
    points = []
    for key in expected_keys():
        label = key_str(key)
        corner = corners.get(key)
        entry = {"key": label, "process": key[0], "supply_v": key[1], "temperature_c": key[2],
                 "valid": False, "reason": None, "corner_status": None, "values": {},
                 "qkick_limit_failed": None}
        if label in dupes:
            entry["reason"] = "ambiguous duplicate PVT result, no value selected"
        elif corner is None:
            entry["reason"] = "grid point not in the envelope"
        else:
            entry["corner_status"] = corner.get("status")
            problem = point_problem(corner, vcm_v, required)
            index, _ = grade_mod.measurement_index(corner)
            if index:
                entry["values"] = {n: _num(index, n) for n in (*REPORTED, "vcm_meas")}
                q = index.get("qkick_fc")
                entry["qkick_limit_failed"] = (None if q is None else q.get("status") != "pass")
            if problem:
                entry["reason"] = problem
            else:
                entry["valid"] = True
        points.append(entry)
    valid = [p for p in points if p["valid"]]
    resid = [(p["values"][RESIDUE], p["key"]) for p in valid]
    stats = {
        "points_expected": len(points), "points_valid": len(valid),
        "rejected": [{"key": p["key"], "reason": p["reason"]} for p in points if not p["valid"]],
        "structural_notes": notes,
        "residue_uv": {
            "min": min(resid)[0] if resid else None, "min_at": min(resid)[1] if resid else None,
            "max": max(resid)[0] if resid else None, "max_at": max(resid)[1] if resid else None,
        },
    }
    for name in ("qkick_p_fc", "qkick_n_fc", "qkick_fc", "kick_1k_peak_mv"):
        vals = [(p["values"][name], p["key"]) for p in valid]
        stats[name] = {"min": min(vals)[0] if vals else None,
                       "max": max(vals)[0] if vals else None}
    stats["qkick_limit_failures"] = sum(1 for p in valid if p["qkick_limit_failed"])
    stats["verdict"] = grade_residue(stats)
    return {"condition": cond.name, "vcm_v": vcm_v, "vcm_delta_v": cond.delta_v,
            "envelope_status": envelope.get("status"), "points": points, **stats}


def grade_residue(stats: dict) -> dict:
    """Residue-only verdict (the fleet's aggregate status is not consulted)."""
    n_ok, n_all = stats["points_valid"], stats["points_expected"]
    mx = stats["residue_uv"]["max"]
    if n_ok != n_all or stats["structural_notes"]:
        return {"target": "INCOMPLETE", "stretch": "INCOMPLETE",
                "basis": f"{n_ok}/{n_all} valid points; rejected points are named, not repaired"}

    def v(bound):
        return "MET" if mx <= bound else "NOT MET"
    return {"target": v(RESIDUE_TARGET_UV), "stretch": v(RESIDUE_STRETCH_UV),
            "basis": f"max over {n_all}/{n_all} valid points = {mx} uV vs Target "
                     f"<= {RESIDUE_TARGET_UV:g} uV / Stretch <= {RESIDUE_STRETCH_UV:g} uV"}


# --------------------------------------------------------------------------- #
# nominal reproduction gate
# --------------------------------------------------------------------------- #

_DECLARED = re.compile(r"^\*\s+(circuit|DUT):\s+(\S+)\s+sha256=([0-9a-f]{64})", re.M)


def declared_hashes(body_text: str) -> dict:
    return {m.group(1): (m.group(2), m.group(3)) for m in _DECLARED.finditer(body_text)}


def _strip_request(req: dict, drop_probe: bool) -> dict:
    out = {k: v for k, v in req.items() if k not in ("_comment", "_condition", "netlist")}
    if drop_probe:
        out["measurements"] = [m for m in out["measurements"] if m["name"] != VCM_PROBE.name]
    return out


def reproduction_check(nominal_env: dict, nominal_request: dict, nominal_body: str,
                       ref_env: dict, ref_request: dict, ref_body: str) -> dict:
    """Original-measurement equality at every PVT key plus provenance match.
    ``ok`` is False on ANY discrepancy; every discrepancy is listed."""
    problems: list[str] = []
    if _strip_request(nominal_request, True) != _strip_request(ref_request, False):
        problems.append("request (grid, analysis, models, measurements, limits, options) "
                        "differs from the reference beyond the added probe")
    if declared_hashes(nominal_body) != declared_hashes(ref_body):
        problems.append("declared circuit/DUT hashes differ from the reference body")
    for field in ("engine", "engine_version", "models_lib_sha256", "netlist_source"):
        a = (nominal_env.get("environment") or {}).get(field)
        b = (ref_env.get("environment") or {}).get(field)
        if a != b:
            problems.append(f"environment.{field}: {a!r} != reference {b!r}")
    nom, n_notes = load_points(nominal_env)
    ref, r_notes = load_points(ref_env)
    problems += [f"nominal: {n}" for n in n_notes] + [f"reference: {n}" for n in r_notes]
    names = [m["name"] for m in ref_request["measurements"]]
    compared = 0
    mismatches = []
    for key in expected_keys():
        a, b = nom.get(key), ref.get(key)
        if a is None or b is None:
            problems.append(f"{key_str(key)}: missing in {'nominal' if a is None else 'reference'}")
            continue
        ai, abad = grade_mod.measurement_index(a)
        bi, bbad = grade_mod.measurement_index(b)
        if abad or bbad:
            problems.append(f"{key_str(key)}: unreliable measurement list ({abad or bbad})")
            continue
        for name in names:
            x, y = ai.get(name), bi.get(name)
            if x is None or y is None:
                problems.append(f"{key_str(key)}: {name} missing")
                continue
            compared += 1
            if x.get("value") != y.get("value") or x.get("status") != y.get("status"):
                mismatches.append({"key": key_str(key), "measurement": name,
                                   "nominal": x.get("value"), "reference": y.get("value"),
                                   "nominal_status": x.get("status"),
                                   "reference_status": y.get("status")})
    return {"ok": not problems and not mismatches, "values_compared": compared,
            "expected_values": len(expected_keys()) * len(names),
            "mismatches": mismatches, "problems": problems}


# --------------------------------------------------------------------------- #
# comparison (offline, deterministic)
# --------------------------------------------------------------------------- #


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _remote(env: dict) -> dict:
    r = (env.get("environment") or {}).get("remote") or {}
    return {k: r.get(k) for k in ("provider", "job_id", "instance_type", "lifecycle", "state")}


def compare_series(series: Path, reference_dir: Path = REFERENCE_DIR) -> dict:
    conds, envs = {}, {}
    for cond in CONDITIONS:
        cdir = series / cond.name
        env_path = cdir / f"{TAG}.envelope.json"
        if not env_path.is_file():
            raise KickbackCmBandError(f"missing envelope {env_path}")
        envs[cond.name] = _load(env_path)
        c = evaluate_condition(cond, envs[cond.name])
        c["inputs"] = {"body_sha256": _sha(cdir / BODY_NAME),
                       "request_sha256": _sha(cdir / f"{TAG}.request.json"),
                       "envelope_sha256": _sha(env_path)}
        inv = cdir / f"{TAG}.invocation.json"
        if inv.is_file():
            invocation = _load(inv)
            c["invocation"] = {k: invocation.get(k) for k in
                               ("klt_version", "env", "request_sha256", "exit_code",
                                "started_utc", "finished_utc", "envelope_sha256")}
            c["invocation"]["request_sha256_matches"] = (
                invocation.get("request_sha256") == c["inputs"]["request_sha256"])
        c["remote"] = _remote(envs[cond.name])
        conds[cond.name] = c
    nom = conds[NOMINAL]
    repro = reproduction_check(
        envs[NOMINAL], _load(series / NOMINAL / f"{TAG}.request.json"),
        (series / NOMINAL / BODY_NAME).read_text(encoding="utf-8"),
        _load(reference_dir / f"{TAG}.envelope.json"),
        _load(reference_dir / f"{TAG}.request.json"),
        (reference_dir / f"{TAG}.body.spice").read_text(encoding="utf-8"))
    per_point = []
    for i, key in enumerate(expected_keys()):
        row = {"key": key_str(key)}
        for name, c in conds.items():
            p = c["points"][i]
            row[name] = {"valid": p["valid"], "reason": p["reason"], **p["values"]}
            if name != NOMINAL and p["valid"] and nom["points"][i]["valid"]:
                row[name]["residue_delta_vs_nom_uv"] = round(
                    p["values"][RESIDUE] - nom["points"][i]["values"][RESIDUE], 6)
        per_point.append(row)
    usable = repro["ok"]
    return {
        "issue": 165, "series": series.name, "reference_campaign": reference_dir.name,
        "residue_target_uv": RESIDUE_TARGET_UV, "residue_stretch_uv": RESIDUE_STRETCH_UV,
        "reproduction": repro,
        "series_usable_for_dr0004": usable,
        "conditions": {n: {k: v for k, v in c.items() if k != "points"} for n, c in conds.items()},
        "per_point": per_point,
    }


def _f(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def render_markdown(result: dict) -> str:
    r = result["reproduction"]
    out = ["# Kickback residue across the input common-mode band (issue #165)", "",
           "Characterization for the candidate DR-0004 CM row; not ratification. "
           f"Residue graded against the unchanged Row 4 Target <= {result['residue_target_uv']:g} uV, "
           f"Stretch <= {result['residue_stretch_uv']:g} uV. Q_kick and peak excursion are "
           "reported, not graded here.", "",
           f"Series `{result['series']}`; reference campaign `{result['reference_campaign']}`.", "",
           "## Nominal reproduction gate", "",
           f"**{'PASS' if r['ok'] else 'FAIL'}**: {r['values_compared']}/{r['expected_values']} "
           f"original measurement values compared exactly at 45 PVT keys; "
           f"{len(r['mismatches'])} value mismatch(es), {len(r['problems'])} other problem(s).", ""]
    for p in r["problems"]:
        out.append(f"- {p}")
    for m in r["mismatches"][:50]:
        out.append(f"- {m['key']} {m['measurement']}: {m['nominal']} vs reference {m['reference']}")
    if not result["series_usable_for_dr0004"]:
        out += ["", "**This series is EXCLUDED from DR-0004 evidence (reproduction failed).**"]
    out += ["", "## Per condition", "",
            "| condition | vcm (V) | valid | residue min ... max (uV) | Target | Stretch | "
            "Q_kick max (fC) | qkick limit fails | peak max (mV) | fleet job |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for n, c in result["conditions"].items():
        ru = c["residue_uv"]
        out.append(
            f"| `{n}` | {c['vcm_v']} | {c['points_valid']}/{c['points_expected']} | "
            f"{_f(ru['min'])} ({ru['min_at']}) ... {_f(ru['max'])} ({ru['max_at']}) | "
            f"{c['verdict']['target']} | {c['verdict']['stretch']} | "
            f"{_f(c['qkick_fc']['max'])} | {c['qkick_limit_failures']} | "
            f"{_f(c['kick_1k_peak_mv']['max'], 1)} | {c['remote'].get('job_id')} |")
    out += ["", "Q_kick per side (min ... max over valid points, fC):", "",
            "| condition | p side | n side |", "|---|---|---|"]
    for n, c in result["conditions"].items():
        out.append(f"| `{n}` | {_f(c['qkick_p_fc']['min'])} ... {_f(c['qkick_p_fc']['max'])} | "
                   f"{_f(c['qkick_n_fc']['min'])} ... {_f(c['qkick_n_fc']['max'])} |")
    for n, c in result["conditions"].items():
        if c["rejected"] or c["structural_notes"]:
            out += ["", f"### Rejected points, `{n}`", ""]
            out += [f"- {x['key']}: {x['reason']}" for x in c["rejected"]]
            out += [f"- {x}" for x in c["structural_notes"]]
    names = list(result["conditions"])
    out += ["", "## Per PVT point: residue (uV), Q_kick (fC), peak (mV)", "",
            "| point | " + " | ".join(f"{n} resid | {n} Q | {n} peak" for n in names) + " |",
            "|---|" + "---|---|---|" * len(names)]
    for row in result["per_point"]:
        cells = []
        for n in names:
            d = row[n]
            if d["valid"]:
                cells += [_f(d.get(RESIDUE)), _f(d.get("qkick_fc")), _f(d.get("kick_1k_peak_mv"), 1)]
            else:
                cells += [f"REJECTED ({d['reason']}); unvalidated residue {_f(d.get(RESIDUE))}", "-", "-"]
        out.append(f"| {row['key']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"

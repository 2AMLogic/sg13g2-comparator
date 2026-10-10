"""`klt yield` evidence for the statistical DR-0002 rows (issue #63, T1 item 6).

Stdlib only. Reads a committed `klt sim` campaign (default: the whole-latch
campaign ``20261009-d73a9ac``), validates it with the existing
`kltsim.grade` machinery (saved request/invocation hash chain, supply and
temperature probes, validity gates, duplicate/malformed measurement lists),
derives one ``klt yield`` sample-set document per statistical row with **one
measurement per PVT point** (process/supply/temperature populations are never
pooled), runs the pinned native ``klt yield`` engine, and writes an indexed,
append-only campaign directory.

What the reports establish, and what they do not (see sim/klt-yield/README.md):

* Row 1 (offset): the per-draw empirical fraction of ``vos_mv`` draws inside
  the +/-15 mV Target, with a Clopper-Pearson interval, per PVT point. This is
  NOT the ratified quantization-corrected 3-sigma statistic, which the index
  carries beside it (recomputed here and cross-checked against the grader).
* Row 2 (noise): the per-rung fraction of trials that resolve in the correct
  direction at +/-od_x (a Bernoulli hit fraction), reported with no yield
  target. It is NOT the ratified input-referred noise sigma (probit-slope
  statistic, also carried beside it).

Nothing here edits a source envelope; derived documents are new files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import build as build_mod
from . import grade
from . import benches as BENCH_MODS
from .benches import BENCHES

REPO_ROOT = build_mod.REPO_ROOT
SOURCE_CAMPAIGN = "sim/klt-corner-verification/campaigns/20261009-d73a9ac"
OUT_ROOT = "sim/klt-yield/campaigns"
DEFAULT_CAMPAIGN_ID = "20261010-d73a9ac"
PIN_FILE = "manifests/klt-pin.json"
SMOKE_CONTROL = "smoke/offset_mc-mismatch-vs-negctrl.envelope.json"
INDEX_SCHEMA = "sg13g2-comparator/klt-yield-index/1"

#: Row 1: the per-draw +/-15 mV window is the Target the bench itself encodes.
OFFSET = {"row_id": "1", "bench": "offset_mc", "measurement": "vos_mv", "prefix": "vos_mv"}
#: Row 2: hit_plus is correct when the decision is high (>= 0.5); hit_minus
#: when it is low (<= 0.5). hit_zero is the injection guard, not a trial
#: with a correct answer, so it is not a yield measurement.
NOISE = {"row_id": "2", "bench": "transient_noise"}
NOISE_MEASUREMENTS = (
    ("hit_plus", {"min": 0.5}),
    ("hit_minus", {"max": 0.5}),
)
ROWS_BOTH = ("1", "2")
ROWS_OFFSET = ("1",)
MIN_USABLE = 2  # klt yield's own hard floor; below this no interval exists


class YieldInputError(Exception):
    """The source evidence cannot support a yield analysis (fail closed)."""


class EngineError(Exception):
    """The native `klt yield` engine is absent, wrong, or failed."""


# --------------------------------------------------------------------------- #
# generic helpers
# --------------------------------------------------------------------------- #


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def dumps(obj) -> str:
    """Deterministic, strict (no NaN/Infinity) JSON with a trailing newline."""
    return json.dumps(grade.json_safe(obj), indent=2, allow_nan=False, sort_keys=False) + "\n"


def load_pin(repo_root: Path = REPO_ROOT) -> dict:
    return json.loads((repo_root / PIN_FILE).read_text(encoding="utf-8"))


def default_klt_command(pin: dict) -> list[str]:
    """The documented pinned invocation: the git-pinned build plus the
    `yield` extra (the prebuilt wheel does not cover the pinned commit, so
    the native extension is built from source and needs a Rust toolchain)."""
    spec = f"klayout-tools[yield] @ git+https://github.com/{pin['klt_repo']}@{pin['klt_commit']}"
    return ["uvx", "--from", spec, "klt"]


# --------------------------------------------------------------------------- #
# population extraction
# --------------------------------------------------------------------------- #


@dataclass
class Population:
    """One PVT point's Monte-Carlo draws for one measurement."""

    point: str                       # grid label, e.g. tt_-40c_1.08v
    corner_id: str                   # klt's base corner id (no /mc suffix)
    measurement: str
    unit: str | None
    expected_n: int
    values: list[float] = field(default_factory=list)       # usable, sample order
    value_indices: list[int] = field(default_factory=list)  # sample_index of each usable value
    seeds: list[int | None] = field(default_factory=list)   # seed of each ATTEMPTED sample
    excluded: list[dict] = field(default_factory=list)       # {sample_index, category, reason}

    @property
    def attempted(self) -> int:
        return len(self.values) + len(self.excluded)

    def count(self, category: str) -> int:
        return sum(1 for e in self.excluded if e["category"] == category)


def _bench_gates(bench_name: str) -> list[str]:
    return [m.name for m in BENCHES[bench_name].measurements if m.role == "gate"]


def collect_populations(bench: grade.BenchEvidence, measurement: str, unit: str | None,
                        grid: dict, expected_n: int, *, binary: bool = False,
                        independence: bool = False) -> dict[str, Population]:
    """Per grid point, the validated Monte-Carlo population of ``measurement``.

    Deterministic (non-sampled) corners are ignored. Every sampled corner is
    accounted for: usable, ``errored`` (no value / simulator error) or
    ``inconclusive`` (a value exists but the existing grading contract does
    not trust it: failed probe or gate, malformed or duplicate measurement
    list, non-finite or wrong-unit value, or a repeated raw noise draw).
    Raises :class:`YieldInputError` for structural problems (chain
    problems, duplicate sample indices, a missing or wrong-size population)
    rather than analysing a partial set.
    """
    if bench.chain_problems:
        raise YieldInputError(f"{bench.name}: rejected evidence: {bench.chain_problems[0]}")
    if not bench.envelopes:
        raise YieldInputError(f"{bench.name}: no envelopes in the source campaign")
    gates = _bench_gates(bench.name)
    spec = BENCHES[bench.name]
    indep_names = tuple(spec.probes.get("independence") or ()) if independence else ()
    grid_labels = {}
    for key in grade.grid_keys(grid):
        grid_labels[(key[0], round(key[1], 6), key[2])] = grade.key_label(key)

    grouped: dict[tuple, list[tuple[str, dict]]] = {}
    for tag, env in bench.envelopes:
        for corner in env.get("corners") or []:
            if not isinstance(corner, dict) or corner.get("monte_carlo") is None:
                continue
            key = grade._corner_key(corner)
            if key not in grid_labels:
                raise YieldInputError(
                    f"{bench.name}: sampled corner {corner.get('corner_id')!r} is outside the grid")
            grouped.setdefault(key, []).append((tag, corner))

    pops: dict[str, Population] = {}
    for key, label in grid_labels.items():
        corners = grouped.get(key)
        if not corners:
            raise YieldInputError(f"{bench.name}: no Monte-Carlo population for {label}")
        base_ids = {c["corner_id"].rsplit("/mc", 1)[0] for _, c in corners}
        if len(base_ids) != 1:
            raise YieldInputError(f"{bench.name}: {label} maps to several base corners {sorted(base_ids)}")
        pop = Population(label, base_ids.pop(), measurement, unit, expected_n)
        corners = sorted(corners, key=lambda tc: _sample_index(tc[1], bench.name))
        indices = [_sample_index(c, bench.name) for _, c in corners]
        if len(set(indices)) != len(indices):
            raise YieldInputError(f"{bench.name}: {label} reports a sample index more than once "
                                  "(duplicate population)")
        draws: dict[tuple, int] = {}
        if indep_names:
            for _, c in corners:
                d = grade._independence_draw(c, indep_names)
                if None not in d:
                    draws[d] = draws.get(d, 0) + 1
        for (_, corner), idx in zip(corners, indices):
            mc = corner["monte_carlo"]
            seed = mc.get("seed") if isinstance(mc, dict) else None
            pop.seeds.append(seed if isinstance(seed, int) and not isinstance(seed, bool) else None)
            _classify_sample(pop, corner, idx, bench.name, gates, binary, indep_names, draws)
        if pop.attempted != expected_n:
            raise YieldInputError(
                f"{bench.name}: {label} has {pop.attempted} draws, the ratified basis is "
                f"N = {expected_n}")
        if len(pop.values) < MIN_USABLE:
            raise YieldInputError(
                f"{bench.name}: {label} has {len(pop.values)} usable draws of {pop.attempted} "
                f"(klt yield needs at least {MIN_USABLE})")
        pops[label] = pop
    return pops


def _sample_index(corner: dict, bench_name: str) -> int:
    mc = corner.get("monte_carlo")
    idx = mc.get("sample_index") if isinstance(mc, dict) else None
    if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0:
        raise YieldInputError(f"{bench_name}: corner {corner.get('corner_id')!r} has no valid "
                              f"monte_carlo.sample_index ({idx!r})")
    return idx


def _classify_sample(pop: Population, corner: dict, idx: int, bench_name: str, gates: list[str],
                     binary: bool, indep_names: tuple, draws: dict) -> None:
    def exclude(category: str, reason: str) -> None:
        pop.excluded.append({"sample_index": idx, "category": category, "reason": reason})

    if corner.get("status") == "error":
        return exclude("errored", grade._corner_problems(corner, bench_name, gates) or "errored")
    problem = grade._corner_problems(corner, bench_name, gates)
    if problem:
        return exclude("inconclusive", problem)
    index, bad = grade.measurement_index(corner)
    if bad:
        return exclude("inconclusive", bad)
    entry = index.get(pop.measurement)
    if entry is None or entry.get("value") is None:
        return exclude("errored", f"measurement {pop.measurement} not reported")
    try:
        value = grade.finite(grade.convert(grade.finite(entry["value"], pop.measurement),
                                           entry.get("unit"), pop.unit), pop.measurement)
    except (grade.UnitError, grade.NonFiniteError) as exc:
        return exclude("inconclusive", str(exc))
    if binary and value not in (0.0, 1.0):
        return exclude("inconclusive", f"{pop.measurement}={value!r} is not a 0/1 trial outcome")
    if indep_names:
        d = grade._independence_draw(corner, indep_names)
        if None in d:
            return exclude("inconclusive", "raw-noise independence probe missing")
        if draws.get(d, 0) > 1:
            return exclude("inconclusive", "repeats another sample's raw noise draw at this point")
    pop.values.append(value)
    pop.value_indices.append(idx)


# --------------------------------------------------------------------------- #
# sample-set documents
# --------------------------------------------------------------------------- #


def _sorted_points(pops: dict[str, Population]) -> list[Population]:
    return list(pops.values())  # grid order (insertion order of grid_keys)


def offset_limits(spec_bench=None) -> dict:
    meas = next(m for m in BENCHES[OFFSET["bench"]].measurements if m.name == OFFSET["measurement"])
    limits = dict(meas.limits or {})
    if set(limits) != {"min", "max"}:
        raise YieldInputError("offset_mc vos_mv declares no +/-Target window")
    return limits


def control_shift(limits: dict) -> float:
    """A forced offset that pushes every nominal draw of a +/-L window past
    the limit by construction: 2 L (> L + max|draw| for any in-window draw)."""
    return 2.0 * max(abs(limits["min"]), abs(limits["max"]))


def sample_set(pops: dict[str, Population], *, prefix: str, unit: str | None,
               limits_for: dict, with_control: bool = False) -> dict:
    """The klt yield sample-set document: one measurement per PVT point.

    ``limits_for`` is ``{"min":..,"max":..}`` for one measurement name
    (offset) or a mapping not used here. Excluded draws are carried as the
    ``errored`` / ``inconclusive`` counts, never silently dropped.
    """
    measurements = []
    for pop in _sorted_points(pops):
        entry = {
            "name": f"{prefix}@{pop.point}",
            "unit": unit,
            "samples": list(pop.values),
            "errored": pop.count("errored"),
            "inconclusive": pop.count("inconclusive"),
            "limits": dict(limits_for),
            "source_corners": [pop.corner_id],
        }
        if with_control:
            shift = control_shift(limits_for)
            shifted = [v + shift for v in pop.values]
            lo, hi = limits_for["min"], limits_for["max"]
            if any(lo <= v <= hi for v in shifted):
                raise YieldInputError(f"{pop.point}: derived control is not over-limit")
            entry["negative_control"] = {
                "samples": shifted,
                "description": (f"synthetic over-limit control: the nominal draws of this point "
                                f"plus a forced {shift:g} {unit or ''} offset (2 x the limit)"),
            }
        measurements.append(entry)
    return {"measurements": measurements}


def noise_sample_set(per_rung: dict[str, dict[str, Population]]) -> dict:
    measurements = []
    for name, limits in NOISE_MEASUREMENTS:
        for pop in _sorted_points(per_rung[name]):
            measurements.append({
                "name": f"{name}@{pop.point}",
                "unit": "1",
                "samples": list(pop.values),
                "errored": pop.count("errored"),
                "inconclusive": pop.count("inconclusive"),
                "limits": dict(limits),
                "source_corners": [pop.corner_id],
            })
    return {"measurements": measurements}


# --------------------------------------------------------------------------- #
# ratified statistics (carried beside the yield numbers, never replaced by them)
# --------------------------------------------------------------------------- #


def ratified_offset_3sigma(pop: Population, step_mv: float) -> float | None:
    """DR-0002 Row 1's per-point statistic from the usable draws, by the
    grader's own formula (`grade.three_sigma_dr_basis`)."""
    if len(pop.values) < 2:
        return None
    return grade.three_sigma_dr_basis(len(pop.values), statistics.stdev(pop.values), step_mv)


def ratified_noise_sigma(plus: Population, minus: Population, od_x_mv: float) -> dict:
    """Per-point two-rung probit-slope sigma from the hit fractions, or the
    reason there is none (saturated rung, unordered rungs)."""
    p_plus = sum(plus.values) / len(plus.values)
    p_minus = sum(minus.values) / len(minus.values)
    out = {"p_plus": p_plus, "p_minus": p_minus, "sigma_mv": None, "problem": None}
    try:
        out["sigma_mv"] = grade.probit_slope_sigma(p_plus, p_minus, od_x_mv)
    except ValueError as exc:
        out["problem"] = str(exc)
    return out


# --------------------------------------------------------------------------- #
# native engine
# --------------------------------------------------------------------------- #


def _run(cmd: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise EngineError(f"cannot execute {cmd[0]!r}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError(f"{' '.join(cmd[:3])} ... timed out after {timeout}s") from exc


def engine_preflight(klt_cmd: list[str], pin: dict) -> str:
    """Prove the *pinned* native yield engine works before trusting any output.

    Checks the reported version against ``manifests/klt-pin.json`` and runs a
    tiny known-answer sample set (3 draws, 1 outside the limit). A missing
    extension, a version mismatch or a wrong answer is an execution failure:
    never a passing or empty result."""
    ver = _run(klt_cmd + ["--version"], REPO_ROOT)
    text = (ver.stdout + ver.stderr).decode("utf-8", "replace").strip()
    if ver.returncode != 0 or pin["klt_version"] not in text:
        raise EngineError(f"klt version {text!r} does not match the pin {pin['klt_version']!r} "
                          f"({PIN_FILE})")
    doc = {"measurements": [{"name": "probe", "samples": [0.1, 0.2, 5.0],
                             "limits": {"min": 0.0, "max": 1.0}}]}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "probe.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        proc = _run(klt_cmd + ["yield", str(path), "--format", "json"], REPO_ROOT)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise EngineError(f"klt yield preflight produced no JSON: {proc.stderr.decode('utf-8', 'replace')[:300]}")
    if "error" in out:
        raise EngineError(f"klt yield preflight failed: {out['error'].get('message')}")
    m = (out.get("measurements") or [{}])[0]
    est = ((m.get("yield") or {}).get("empirical") or {}).get("estimate")
    if proc.returncode not in (0,) or est is None or abs(est - 2.0 / 3.0) > 1e-12:
        raise EngineError(f"klt yield preflight gave a wrong answer (exit {proc.returncode}, "
                          f"empirical yield {est!r}, expected 2/3)")
    return text


def run_yield(klt_cmd: list[str], samples_rel: str) -> bytes:
    """Run `klt yield` from the repo root on a repo-relative path and return
    the report bytes verbatim. Any error envelope or non-JSON is an
    :class:`EngineError`; a report is never synthesised."""
    proc = _run(klt_cmd + ["yield", samples_rel, "--format", "json"], REPO_ROOT)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        raise EngineError(f"klt yield produced no JSON for {samples_rel}: "
                          f"{proc.stderr.decode('utf-8', 'replace')[:300]}")
    if not isinstance(out, dict) or "error" in out:
        msg = out.get("error", {}).get("message") if isinstance(out, dict) else out
        raise EngineError(f"klt yield failed on {samples_rel}: {msg}")
    return proc.stdout


# --------------------------------------------------------------------------- #
# generation
# --------------------------------------------------------------------------- #


def _chain_summary(bench: grade.BenchEvidence) -> dict:
    return {tag: dict(sha, envelope_sha256=bench.envelope_files[tag])
            for tag, sha in bench.chain_checked.items()}


def _rows_spec() -> dict:
    return json.loads((build_mod.EXPERIMENT_DIR / "rows.json").read_text(encoding="utf-8"))


def validate_selection(offset_n, rows) -> tuple[int | None, tuple[str, ...]]:
    """The declared offset N and row selection, or ``YieldInputError``.

    ``offset_n`` None is the historical ratified N (60). A declared N must be
    a valid draw count; selecting only row 1 is the offset-only form (no noise
    source is read, so no noise population is run or re-analysed).
    """
    rows = tuple(rows)
    if rows not in (ROWS_BOTH, ROWS_OFFSET):
        raise YieldInputError(f"unsupported row selection {rows!r}; use {ROWS_BOTH} or {ROWS_OFFSET}")
    if offset_n is not None:
        try:
            offset_n = BENCH_MODS.validate_offset_n(offset_n)
        except ValueError as exc:
            raise YieldInputError(str(exc)) from None
        if offset_n == BENCH_MODS.OFFSET_MC_N and rows == ROWS_BOTH:
            offset_n = None  # the historical basis is not a "declared" variant
    return offset_n, rows


def derive_inputs(source_dir: Path, offset_n: int | None = None,
                  rows_sel: tuple[str, ...] = ROWS_BOTH) -> dict:
    """Everything deterministic from the committed source campaign: the
    sample-set documents and the per-point provenance. No engine, no I/O
    outside ``source_dir``.

    ``offset_n`` declares a non-historical offset draw count (the saved
    requests must carry exactly it, every population must have exactly it);
    ``rows_sel`` selects both rows (historical default) or the offset row
    only, which reads no noise evidence at all.
    """
    offset_n, rows_sel = validate_selection(offset_n, rows_sel)
    rows = _rows_spec()
    grid = rows["grid"]
    row1 = next(r for r in rows["rows"] if r["id"] == "1")["evidence"]
    row2 = next(r for r in rows["rows"] if r["id"] == "2")["evidence"]
    expected_off = int(offset_n) if offset_n is not None else int(row1["expected_n"])
    with_noise = rows_sel == ROWS_BOTH
    names = (OFFSET["bench"], NOISE["bench"]) if with_noise else (OFFSET["bench"],)
    benches = grade.load_campaign(Path(source_dir), bench_names=names, offset_n=offset_n)
    off_bench = benches[OFFSET["bench"]]
    dut = grade.load_dut_reference()
    for b in [benches[n] for n in names]:
        problems = grade.check_dut(b, dut)
        if problems:
            raise YieldInputError(f"{b.name}: {problems[0]}")

    limits = offset_limits()
    off_pops = collect_populations(off_bench, OFFSET["measurement"], "mV", grid, expected_off)
    step_mv = float(row1["quantization_step"])
    if not with_noise:
        return {
            "grid": grid, "limits": limits, "step_mv": step_mv,
            "offset_pops": off_pops, "noise_pops": None, "zero_pops": None,
            "offset_doc": sample_set(off_pops, prefix=OFFSET["prefix"], unit="mV",
                                     limits_for=limits, with_control=True),
            "noise_doc": None,
            "benches": {OFFSET["bench"]: off_bench},
            "expected_n": {"1": expected_off},
            "offset_n": offset_n, "rows_sel": rows_sel,
        }
    noise_bench = benches[NOISE["bench"]]
    noise_pops = {name: collect_populations(noise_bench, name, "1", grid, int(row2["expected_n"]),
                                            binary=True, independence=True)
                  for name, _ in NOISE_MEASUREMENTS}
    zero_pops = collect_populations(noise_bench, row2["zero"], "1", grid, int(row2["expected_n"]),
                                    binary=True, independence=True)
    guard = row2["zero_guard"]
    od_x = float(row2["od_x_mv"])
    for label, zp in zero_pops.items():
        p_zero = sum(zp.values) / len(zp.values)
        if not guard["min"] <= p_zero <= guard["max"]:
            raise YieldInputError(f"{label}: zero-overdrive fraction {p_zero} outside the "
                                  f"injection guard [{guard['min']}, {guard['max']}]")
    return {
        "grid": grid, "limits": limits, "step_mv": step_mv, "od_x_mv": od_x, "guard": guard,
        "offset_pops": off_pops, "noise_pops": noise_pops, "zero_pops": zero_pops,
        "offset_doc": sample_set(off_pops, prefix=OFFSET["prefix"], unit="mV",
                                 limits_for=limits, with_control=True),
        "noise_doc": noise_sample_set(noise_pops),
        "benches": {OFFSET["bench"]: off_bench, NOISE["bench"]: noise_bench},
        "expected_n": {"1": expected_off, "2": int(row2["expected_n"])},
        "offset_n": offset_n, "rows_sel": rows_sel,
    }


def _pop_record(pop: Population, bench: grade.BenchEvidence, name_in_report: str) -> dict:
    return {
        "point": pop.point, "source_corner": pop.corner_id, "report_measurement": name_in_report,
        "attempted": pop.attempted, "usable": len(pop.values),
        "errored": pop.count("errored"), "inconclusive": pop.count("inconclusive"),
        "excluded": pop.excluded, "sample_seeds": pop.seeds,
    }


def _yield_summary(report: dict) -> dict:
    out = {}
    for m in report["measurements"]:
        y = (m.get("yield") or {}).get("empirical") or {}
        ci = y.get("confidence_interval") or {}
        nc = m.get("negative_control")
        out[m["name"]] = {
            "n": m.get("n"), "errored": m.get("errored"), "inconclusive": m.get("inconclusive"),
            "limits": m.get("limits"),
            "empirical_estimate": y.get("estimate"), "confidence": y.get("confidence"),
            "ci_low": ci.get("low"), "ci_high": ci.get("high"),
            "sample_size_verdict": (m.get("sample_size") or {}).get("verdict"),
            "required_n": (m.get("sample_size") or {}).get("required_n"),
            "negative_control_verdict": nc.get("verdict") if isinstance(nc, dict) else None,
            "warnings": m.get("warnings") or [],
        }
    return out


def generate(campaign_id: str = DEFAULT_CAMPAIGN_ID, klt_cmd: list[str] | None = None,
             source_rel: str = SOURCE_CAMPAIGN, offset_n: int | None = None,
             rows_sel: tuple[str, ...] = ROWS_BOTH) -> Path:
    """Write ``sim/klt-yield/campaigns/<campaign_id>/``. Refuses to touch an
    existing directory (append-only evidence)."""
    pin = load_pin()
    klt_cmd = klt_cmd or default_klt_command(pin)
    out_dir = REPO_ROOT / OUT_ROOT / campaign_id
    if out_dir.exists():
        raise YieldInputError(f"{out_dir.relative_to(REPO_ROOT)} already exists; evidence is "
                              "append-only, choose a new --campaign-id")
    tool_version = engine_preflight(klt_cmd, pin)
    derived = derive_inputs(REPO_ROOT / source_rel, offset_n, rows_sel)

    inputs_rel = f"{OUT_ROOT}/{campaign_id}/inputs"
    docs = {"offset": derived["offset_doc"], "noise": derived["noise_doc"]}
    docs = {k: v for k, v in docs.items() if v is not None}
    try:
        (out_dir / "inputs").mkdir(parents=True)
        reports, report_bytes = {}, {}
        for key, doc in docs.items():
            (out_dir / "inputs" / f"{key}.samples.json").write_text(dumps(doc), encoding="utf-8")
            raw = run_yield(klt_cmd, f"{inputs_rel}/{key}.samples.json")
            (out_dir / f"{key}.yield.json").write_bytes(raw)
            report_bytes[key], reports[key] = raw, json.loads(raw)
        index = build_index(campaign_id, source_rel, derived, reports, report_bytes, tool_version,
                            pin, klt_cmd)
        (out_dir / "index.json").write_text(dumps(index), encoding="utf-8")
        (out_dir / "index.md").write_text(render_index_md(index), encoding="utf-8")
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)  # our own half-written directory
        raise
    return out_dir


def smoke_control(source_dir: Path) -> dict:
    """The committed mismatch-off smoke evidence, read as-is: same point,
    mismatch models on vs off. It shows the injection mechanism moves the
    spread; it is NOT a known-bad yield control (the off population sits
    inside the limits)."""
    path = Path(source_dir) / SMOKE_CONTROL
    raw = path.read_bytes()
    env = json.loads(raw)
    vos = next(m for m in env["measurements"] if m["name"] == "vos_mv")
    by = {e["corner_id"]: e for e in vos["monte_carlo"]["by_corner"]}
    on = next((e for c, e in by.items() if c.startswith("mos_tt_mismatch/")), None)
    off = next((e for c, e in by.items() if not c.split("/")[0].endswith("_mismatch")), None)
    if on is None or off is None:
        raise YieldInputError("smoke control: mismatch-on / mismatch-off populations not both present")
    return {
        "path": f"{SOURCE_CAMPAIGN}/{SMOKE_CONTROL}", "sha256": sha256_bytes(raw),
        "mismatch_on": {"corner_id": on["corner_id"], "n": on["n"], "stddev_mv": on["stddev"]},
        "mismatch_off": {"corner_id": off["corner_id"], "n": off["n"], "stddev_mv": off["stddev"]},
        "limits_mv": [-15.0, 15.0],
        "mismatch_off_inside_limits": (off["min"] >= -15.0 and off["max"] <= 15.0),
        "reading": ("mismatch-injection control only: with mismatch models off the spread is "
                    "zero, with them on it is not. The off population is inside the limits, so "
                    "it is not a known-bad yield control; that role is played by the derived "
                    "over-limit control carried in inputs/offset.samples.json."),
    }


def build_index(campaign_id: str, source_rel: str, derived: dict, reports: dict,
                report_bytes: dict, tool_version: str, pin: dict, klt_cmd: list[str]) -> dict:
    source_dir = REPO_ROOT / source_rel
    out_rel = f"{OUT_ROOT}/{campaign_id}"
    offset_n, with_noise = derived["offset_n"], derived["rows_sel"] == ROWS_BOTH
    grader = grade.grade_campaign(source_dir, offset_n=offset_n)
    g_rows = {r["id"]: r for r in grader["rows"]}

    # ---- row 1 ----
    off_sum = _yield_summary(reports["offset"])
    off_points = []
    grader_pts = {d["point"]: d for d in g_rows["1"]["monte_carlo_per_point"]}
    for label, pop in derived["offset_pops"].items():
        name = f"{OFFSET['prefix']}@{label}"
        rec = _pop_record(pop, derived["benches"]["offset_mc"], name)
        mine = ratified_offset_3sigma(pop, derived["step_mv"])
        theirs = grader_pts[label]["three_sigma_dr_basis"]
        rec["yield"] = off_sum[name]
        rec["ratified_statistic"] = {
            "name": "3 x population sigma net of staircase quantization (mV)",
            "value_mv": mine, "grader_value_mv": theirs,
            "agrees_with_grader": mine is not None and theirs is not None
            and math.isclose(mine, theirs, rel_tol=1e-9, abs_tol=1e-9),
            "target_mv": 15.0,
        }
        off_points.append(rec)

    # ---- row 2 ----
    noise_sum = _yield_summary(reports["noise"]) if with_noise else {}
    grader_noise = ({d["point"]: d for d in g_rows["2"]["monte_carlo_per_point"]}
                    if with_noise else {})
    noise_points = []
    for label in (derived["zero_pops"] if with_noise else ()):
        plus, minus = (derived["noise_pops"][n][label] for n, _ in NOISE_MEASUREMENTS)
        sig = ratified_noise_sigma(plus, minus, derived["od_x_mv"])
        g = grader_noise[label]
        noise_points.append({
            "point": label, "source_corner": plus.corner_id,
            "rungs": {
                n: dict(_pop_record(derived["noise_pops"][n][label],
                                    derived["benches"]["transient_noise"], f"{n}@{label}"),
                        yield_=noise_sum[f"{n}@{label}"])
                for n, _ in NOISE_MEASUREMENTS},
            "zero_rung_guard": {
                "p_zero": sum(derived["zero_pops"][label].values) / len(derived["zero_pops"][label].values),
                "min": derived["guard"]["min"], "max": derived["guard"]["max"]},
            "ratified_statistic": {
                "name": "two-rung probit-slope sigma (mV rms)", **sig,
                "grader_value_mv": g.get("sigma"),
                "agrees_with_grader": sig["sigma_mv"] is not None and g.get("sigma") is not None
                and math.isclose(sig["sigma_mv"], g["sigma"], rel_tol=1e-9, abs_tol=1e-9),
            },
        })
    for p in noise_points:  # JSON key must not carry a trailing underscore
        for rung in p["rungs"].values():
            rung["yield"] = rung.pop("yield_")

    def stats_of(report):
        return {"status": report.get("status"), "measurement_count": report.get("measurement_count"),
                "confidence": report.get("confidence"),
                "target_ci_halfwidth": report.get("target_ci_halfwidth"),
                "min_samples": report.get("min_samples"),
                "run_warnings": report.get("warnings") or []}

    off_rel, noise_rel = f"{out_rel}/inputs/offset.samples.json", f"{out_rel}/inputs/noise.samples.json"
    n_text = offset_n if offset_n is not None else 60
    source_env = {}
    for name, bench in derived["benches"].items():
        source_env[name] = _chain_summary(bench)
    sample_sizes = {n: s["sample_size_verdict"] for n, s in off_sum.items()}
    def noise_row() -> dict:
        return (
        {
            "row_id": "2", "spec_row": "Input-referred noise (whole-latch transient noise)",
            "report": f"{out_rel}/noise.yield.json",
            "report_sha256": sha256_bytes(report_bytes["noise"]),
            "samples": noise_rel, "samples_sha256": sha256_file(REPO_ROOT / noise_rel),
            "citable_for_item6": False,
            "what_the_report_establishes": (
                "Per PVT point and rung (hit_plus >= 0.5, hit_minus <= 0.5): the fraction of "
                "N = 80 independent trials that resolve in the correct direction at "
                "+/-1 mV overdrive. This is a Bernoulli hit fraction, NOT the ratified "
                "input-referred noise sigma (grid-wide mean of the per-point probit-slope "
                "sigma, in each point's ratified_statistic). No target yield is declared and "
                "no negative control is declared, so this report is not cited for item 6."),
            "settings": stats_of(reports["noise"]),
            "populations": noise_points,
        }
        )

    index = {
        "schema": INDEX_SCHEMA,
        "campaign_id": campaign_id,
        "generated_by": ("python3 sim/run_klt_yield.py generate --campaign-id " + campaign_id),
        "tool": {"klt_version_reported": tool_version, "pin_file": PIN_FILE,
                 "klt_commit": pin["klt_commit"], "klt_version": pin["klt_version"],
                 "command": klt_cmd},
        "source": {
            "campaign": source_rel,
            "realization_note": (
                "Analyses the already-committed whole-latch klt sim realization (klt 0.5.0+"
                "ge8ca621a6961, base seed 20260916, offset N = 60 and noise N = 80 per PVT point). "
                "Issue #82 (the campaign's offset reads ~13 % above the DR-0002 record, cause "
                "undetermined between the old harness loop and the new process) is NOT settled by "
                "this analysis, and nothing here replaces the ratified historical record."),
            "benches": source_env,
            "grading_json_sha256": sha256_file(source_dir / "grading.json"),
        },
        "rows": [
            {
                "row_id": "1", "spec_row": "Offset sigma (whole latch)",
                "report": f"{out_rel}/offset.yield.json",
                "report_sha256": sha256_bytes(report_bytes["offset"]),
                "samples": off_rel, "samples_sha256": sha256_file(REPO_ROOT / off_rel),
                "citable_for_item6": True,
                "what_the_report_establishes": (
                    f"Per PVT point (45 separate populations, N = {n_text} each, never pooled): the "
                    "empirical fraction of vos_mv draws inside the +/-15 mV Target window with a "
                    "Clopper-Pearson interval. This is a per-draw yield, NOT the ratified "
                    "criterion (3 x population sigma net of 3 mV staircase quantization, <= 15 mV "
                    "at the worst point), which is carried in each population's "
                    "ratified_statistic. No target yield is declared: none is ratified."),
                "negative_control": (
                    "Each population declares a synthetic over-limit control (nominal draws + "
                    "30 mV forced offset); klt yield must report it detected."),
                "settings": stats_of(reports["offset"]),
                "sample_size_verdicts": sample_sizes,
                "populations": off_points,
            },
        ],
        "mismatch_off_smoke_control": smoke_control(source_dir),
        "limitations": [
            "Transient-noise draws are not reproducible (ngspice-46 TRNOISE ignores klt's "
            "per-sample seed); the recorded seeds identify samples, not noise streams "
            "(klayout-tools#2963).",
            "Noise-row trials share raw noise draws across PVT points (never within one); a "
            "repeat within a point is excluded as inconclusive.",
            "No hand-edited source: every derived document is regenerated by the command above "
            "and compared byte-for-byte by `check`.",
        ],
        "ratified_summary": {
            "row1_worst_3sigma_mv": max((p["ratified_statistic"]["value_mv"] for p in off_points
                                         if p["ratified_statistic"]["value_mv"] is not None),
                                        default=None),
            "row1_target_mv": 15.0,
            "row2_grid_mean_sigma_mv": g_rows["2"]["target"].get("grid_mean") if with_noise else None,
            "row2_target_mv": 1.0,
            "row2_target_verdict": g_rows["2"]["target_verdict"],
            "note": "copied from the existing grader on the same campaign; yield statistics above "
                    "do not replace them.",
        },
    }
    if with_noise:
        index["rows"].append(noise_row())
    else:
        index["ratified_summary"].pop("row2_grid_mean_sigma_mv")
        index["ratified_summary"].pop("row2_target_mv")
        index["ratified_summary"].pop("row2_target_verdict")
    if offset_n is not None or not with_noise:
        index["declared"] = declared_block(offset_n, derived, index["rows"][0])
        index["source"]["realization_note"] = larger_n_note(offset_n)
    return index


def larger_n_note(offset_n) -> str:
    return (f"Analyses a separately identified, offset-only whole-latch klt sim campaign (declared "
            f"N = {offset_n} draws per PVT point, klt base seed 20260916; every population's "
            "sample seed is recorded). No noise population is run or re-analysed here. Issue #82 "
            "(the whole-latch offset reads ~13 % above the DR-0002 historical record, cause "
            "undetermined between the old harness loop and the new process) is NOT settled by a "
            "larger sample and this discrepancy warning is retained: nothing here replaces the "
            "ratified historical record or DR-0002's evidence basis.")


def declared_block(offset_n, derived: dict, row1: dict) -> dict:
    """Campaign-level declaration (non-historical campaigns only; the historical
    index is unchanged byte-for-byte): declared N, row selection, and the
    engine's own sample-size verdict across all populations."""
    verdicts = [p["yield"]["sample_size_verdict"] for p in row1["populations"]]
    required = [p["yield"]["required_n"] for p in row1["populations"]
                if p["yield"]["required_n"] is not None]
    failures = [p["point"] for p in row1["populations"] if (p["yield"]["empirical_estimate"] or 0) < 1.0]
    return {
        "offset_n": offset_n, "rows": list(derived["rows_sel"]),
        "attempted_per_population": sorted({p["attempted"] for p in row1["populations"]}),
        "sample_size_verdicts": {v: verdicts.count(v) for v in sorted(set(verdicts))},
        "max_required_n_reported_by_engine": max(required) if required else None,
        "points_reporting_insufficient_or_no_verdict": [
            p["point"] for p in row1["populations"]
            if p["yield"]["sample_size_verdict"] in (None, "insufficient")],
        "points_with_observed_target_failures": failures,
        "note": ("The engine's sample-size verdict is read from each population's own report; "
                 "N = 183 is the zero-failure planning figure, not a guarantee. If any "
                 "population reports `insufficient` the honest unmet verdict stands and "
                 "max_required_n_reported_by_engine is the additional sample requirement. Any "
                 "observed Target failure is listed, never hidden, and the 15 mV bound is "
                 "unchanged."),
    }


def render_index_md(index: dict) -> str:
    lines = [f"# klt yield campaign `{index['campaign_id']}`", "",
             "GENERATED by `" + index["generated_by"] + "`; do not edit.", "",
             f"Source campaign: `{index['source']['campaign']}` (read only).", "",
             index["source"]["realization_note"], ""]
    for row in index["rows"]:
        lines += [f"## Row {row['row_id']}: {row['spec_row']}", "",
                  row["what_the_report_establishes"], "",
                  f"- report: `{row['report']}` (sha256 `{row['report_sha256']}`)",
                  f"- samples: `{row['samples']}` (sha256 `{row['samples_sha256']}`)", ""]
        if row["row_id"] == "1":
            lines += ["| point | N | usable | yield (CP 95 %) | sample size | control | 3 sigma (mV) |",
                      "|---|---|---|---|---|---|---|"]
            for p in row["populations"]:
                y = p["yield"]
                lines.append(
                    f"| {p['point']} | {p['attempted']} | {p['usable']} | "
                    f"{y['empirical_estimate']:.4f} [{y['ci_low']:.4f}, {y['ci_high']:.4f}] | "
                    f"{y['sample_size_verdict']} (needs {y['required_n']}) | "
                    f"{y['negative_control_verdict']} | {p['ratified_statistic']['value_mv']:.3f} |")
        else:
            lines += ["| point | hit_plus | hit_minus | sigma (mV) |", "|---|---|---|---|"]
            for p in row["populations"]:
                rp, rm = p["rungs"]["hit_plus"]["yield"], p["rungs"]["hit_minus"]["yield"]
                s = p["ratified_statistic"]["sigma_mv"]
                lines.append(f"| {p['point']} | {rp['empirical_estimate']:.4f} "
                             f"[{rp['ci_low']:.3f}, {rp['ci_high']:.3f}] | "
                             f"{rm['empirical_estimate']:.4f} [{rm['ci_low']:.3f}, {rm['ci_high']:.3f}] | "
                             f"{'-' if s is None else format(s, '.3f')} |")
        lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# check (no simulation, no engine required unless --rerun)
# --------------------------------------------------------------------------- #


def check(campaign_id: str = DEFAULT_CAMPAIGN_ID, source_rel: str = SOURCE_CAMPAIGN,
          klt_cmd: list[str] | None = None, rerun: bool = False,
          manifest_path: str = "manifests/sg13g2-comparator.json",
          offset_n: int | None = None, require_cited: bool = False) -> list[str]:
    """Problems found (empty = consistent): derived inputs regenerate
    byte-for-byte from the source, index hashes match the files, each
    report names the committed samples document, and the manifest's item-6
    citation pins the samples hash. ``rerun`` also re-executes the pinned
    engine and requires identical report bytes."""
    problems: list[str] = []
    out_dir = REPO_ROOT / OUT_ROOT / campaign_id
    index_path = out_dir / "index.json"
    if not index_path.is_file():
        return [f"{OUT_ROOT}/{campaign_id}/index.json does not exist"]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    # The campaign's own declaration (absent = the historical N = 60, rows 1+2).
    # A caller-supplied --offset-n must agree with it: an undeclared or wrong N
    # is a problem, never silently accepted.
    declared = index.get("declared") or {}
    decl_n = declared.get("offset_n")
    if offset_n is not None and offset_n != (decl_n if decl_n is not None else 60):
        problems.append(f"--offset-n {offset_n} does not match the campaign's declared "
                        f"offset N {decl_n if decl_n is not None else 60}")
    rows_sel = tuple(declared.get("rows") or ROWS_BOTH)
    out_rel = f"{OUT_ROOT}/{campaign_id}"
    if index.get("source", {}).get("campaign") != source_rel:
        problems.append(f"index records source {index.get('source', {}).get('campaign')!r}, "
                        f"checked against {source_rel!r} (stale source)")
    try:
        derived = derive_inputs(REPO_ROOT / source_rel, decl_n, rows_sel)
    except YieldInputError as exc:
        return problems + [f"source evidence rejected: {exc}"]
    for row in index["rows"]:
        for p in row["populations"] if row["row_id"] == "1" else ():
            want = derived["expected_n"]["1"]
            if p["attempted"] != want:
                problems.append(f"{p['point']}: index records {p['attempted']} attempted draws, "
                                f"declared N is {want}")
    if len(index["rows"]) != len(rows_sel):
        problems.append(f"index holds {len(index['rows'])} rows, declaration selects {list(rows_sel)}")
    for key, doc in (("offset", derived["offset_doc"]), ("noise", derived["noise_doc"])):
        if doc is None:
            if (out_dir / "inputs" / f"{key}.samples.json").exists():
                problems.append(f"{key}.samples.json present but the declaration excludes that row")
            continue
        path = out_dir / "inputs" / f"{key}.samples.json"
        if not path.is_file() or path.read_text(encoding="utf-8") != dumps(doc):
            problems.append(f"{key}.samples.json does not regenerate from the source campaign")
    for row, key in zip(index["rows"], ("offset", "noise")):
        samples = REPO_ROOT / row["samples"]
        report = REPO_ROOT / row["report"]
        if not samples.is_file() or sha256_file(samples) != row["samples_sha256"]:
            problems.append(f"row {row['row_id']}: samples hash differs from the index")
        if not report.is_file() or sha256_file(report) != row["report_sha256"]:
            problems.append(f"row {row['row_id']}: report hash differs from the index")
            continue
        named = json.loads(report.read_bytes()).get("samples")
        if named != row["samples"]:
            problems.append(f"row {row['row_id']}: report names samples {named!r}, "
                            f"expected {row['samples']!r}")
        if row["row_id"] == "1":
            for p in row["populations"]:
                if not p["ratified_statistic"]["agrees_with_grader"]:
                    problems.append(f"{p['point']}: ratified offset statistic disagrees with the grader")
    manifest = json.loads((REPO_ROOT / manifest_path).read_text(encoding="utf-8"))
    cite = (manifest.get("evidence") or {}).get("6")
    if not isinstance(cite, dict):
        problems.append("manifest cites no item 6")
    else:
        row1 = index["rows"][0]
        # A superseded campaign (item 6 repointed at a later report) is checked
        # for internal consistency only; the one the manifest cites must pin
        # its own samples hash.
        if cite.get("file") != row1["report"]:
            if require_cited:
                problems.append(f"manifest item 6 cites {cite.get('file')!r}, expected {row1['report']!r}")
        elif cite.get("content_hash") != "sha256:" + row1["samples_sha256"]:
            problems.append("manifest item 6 content_hash is not the sha256 of the report's "
                            "samples document (the artifact signoff pins for a yield report)")
    if rerun:
        pin = load_pin()
        cmd = klt_cmd or default_klt_command(pin)
        try:
            engine_preflight(cmd, pin)
            for row in index["rows"]:
                if run_yield(cmd, row["samples"]) != (REPO_ROOT / row["report"]).read_bytes():
                    problems.append(f"row {row['row_id']}: re-running klt yield changed the report")
        except EngineError as exc:
            problems.append(f"engine: {exc}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("generate", "check"):
        p = sub.add_parser(name)
        p.add_argument("--campaign-id", default=DEFAULT_CAMPAIGN_ID)
        p.add_argument("--source", default=SOURCE_CAMPAIGN,
                       help="repo-relative committed klt sim campaign directory (read only)")
        p.add_argument("--klt", default=os.environ.get("KLT_YIELD_CMD"),
                       help="klt command (default: the uvx command built from manifests/klt-pin.json; "
                            "or $KLT_YIELD_CMD)")
        p.add_argument("--offset-n", type=int, default=None, metavar="N",
                       help="declared offset draws per PVT point (default: the historical 60); "
                            "for `check` it must agree with the campaign's own declaration")
        p.add_argument("--rows", choices=("both", "offset"), default=None,
                       help="generate only: `offset` analyses the offset row only (no noise "
                            "evidence read); default both, the historical form")
        if name == "check":
            p.add_argument("--require-cited", action="store_true",
                           help="fail unless the manifest's item 6 cites this campaign")
            p.add_argument("--rerun", action="store_true",
                           help="also re-run the pinned native engine and require identical reports")
    args = ap.parse_args(argv)
    cmd = shlex.split(args.klt) if args.klt else None
    try:
        if args.cmd == "generate":
            sel = ROWS_OFFSET if args.rows == "offset" else ROWS_BOTH
            out = generate(args.campaign_id, cmd, args.source, args.offset_n, sel)
            print(f"wrote {out.relative_to(REPO_ROOT)}")
            return 0
        problems = check(args.campaign_id, args.source, cmd, rerun=args.rerun,
                         offset_n=args.offset_n, require_cited=args.require_cited)
    except (YieldInputError, EngineError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0

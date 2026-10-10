"""Memory / hysteresis characterization (issue #159): does the previous
decision bias the next one?

CHARACTERIZATION, NOT COMPLIANCE. No specification row is added or changed;
a future spec claim needs its own DR-0002 decision record.

WHAT IS MEASURED. At each PVT point two histories are compared in ONE
netlist and ONE simulator invocation (same model cards, temperature, supply,
DUT netlist, clock):

* history ``P``: three conditioning strobes at +50 mV, then the swept probe
  on the fourth strobe;
* history ``N``: three conditioning strobes at -50 mV, then the same swept
  probe on the fourth strobe.

Each history owns its own DUT instances (one per probe value); only the
conditioning polarity differs. The switching boundary (the differential
input at which the fourth decision changes polarity) is searched for each
history on [-50 mV, +50 mV] to a final bracket of at most 10 uV, and

    memory_shift = threshold_after_P - threshold_after_N.

THE SEARCH. The contract asks for a deterministic bisection to <= 10 uV
(14 iterations, 15 permitted). ``klt sim`` cannot run an adaptive search in
one request, and every bisection round is a full sequential batch
round-trip, so this module uses the deterministic equivalent that needs
fewer round trips: a 10-ary search. Round 1 evaluates 11 probes
(-50 mV ... +50 mV in 10 mV steps, endpoints included); each later round
evaluates the 9 interior points of the current bracket. The bracket shrinks
by exactly 10x per round: 100 mV -> 10 mV -> 1 mV -> 100 uV -> 10 uV, i.e.
FOUR sequential batch requests, ending at exactly the 10 uV limit. All
arithmetic is in integer microvolts so the width is exact, not rounded.
The bracket is chosen by the same rule as a bisection: the adjacent pair of
evaluated points with opposite resolved polarities.

CLASSIFICATION (supply-normalised ``decision = (V(dout) - V(doutb)) / VDD``
at 9 ns after the fourth rising edge):

* resolved positive  ``decision >= +0.8``
* resolved negative  ``decision <= -0.8``
* unresolved         otherwise
* resolved wrong polarity: a resolved result whose sign opposes the nonzero
  probe input (an expected consequence of an offset; counted, never folded
  into the threshold and never folded into 'unresolved').

A search is REJECTED (no threshold fabricated) when the initial bracket
does not resolve to opposite polarities, when an unresolved point separates
the two polarities (the bracket cannot be closed on resolved points), when
the resolved polarities are non-monotone (more than one sign change, or
reversed), or when a measurement is missing.

Stdlib only; no ngspice and no PDK are needed to import or test this.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from . import build as build_mod
from .benches import MODELS, PROCESSES, SUPPLIES_V, TEMPERATURES_C

EXPERIMENT_DIR = build_mod.SIM_DIR / "comparator-memory"
CAMPAIGNS_DIR = EXPERIMENT_DIR / "campaigns"

#: ---- contract constants (issue #159) -------------------------------------
RESOLVED_THRESHOLD = 0.8
INIT_LO_UV = -50_000
INIT_HI_UV = 50_000
RESOLUTION_UV = 10          # final bracket must be <= this
FANOUT = 10                 # bracket divisions per round
MAX_ROUNDS = 4              # 100 mV / 10**4 = 10 uV exactly
CONDITION_V = 0.05
HIGH_NS = 10.0              # strobe high time
NOMINAL_PERIOD_NS = 30.0
LONG_RESET_PERIOD_NS = 110.0   # 100 ns low
SHORT_RESET_PERIOD_NS = 11.0   # 1 ns low
SAMPLE_AFTER_RISE_NS = 9.0
N_CONDITIONING = 3
FIRST_RISE_NS = 10.0
#: the input steps from the conditioning value to the probe 0.3 ns after the
#: third strobe's falling edge has completed (0.1 ns ramp); identical for
#: every period, so the controls differ from the nominal run in reset time
#: only.
SWITCH_AFTER_RISE_NS = HIGH_NS + 0.3
SWITCH_RAMP_NS = 0.1

#: control criteria (issue #159), in microvolts
LONG_RESET_MAX_ABS_UV = 20.0
SHORT_RESET_MIN_ABS_UV = 40.0
SHORT_OVER_LONG_MIN_UV = 20.0

HISTORIES = ("P", "N")
CONDITION_SIGN = {"P": +1, "N": -1}

BENCH_NAME = "memory"
CONTROL_NAMES = ("long", "short")
CONTROL_PERIOD_NS = {"nominal": NOMINAL_PERIOD_NS, "long": LONG_RESET_PERIOD_NS,
                     "short": SHORT_RESET_PERIOD_NS}
CONTROL_POINT = ("tt", 1.2, 27)

#: solver options. Threshold work at 10 uV needs a tighter relative
#: tolerance than the 1e-4 the timing benches use.
OPTIONS = ("reltol=1e-6", "vntol=1e-9", "abstol=1e-13")


class MemoryError_(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# classification and the deterministic search (pure functions)
# --------------------------------------------------------------------------- #

POS, NEG, UNRES = "resolved_positive", "resolved_negative", "unresolved"


def classify(decision: float | None, probe_uv: int | float) -> dict:
    """Classify one decision value taken with the probe input ``probe_uv``."""
    if decision is None or decision != decision:
        return {"class": None, "wrong_polarity": False, "decision": None}
    if decision >= RESOLVED_THRESHOLD:
        cls = POS
    elif decision <= -RESOLVED_THRESHOLD:
        cls = NEG
    else:
        cls = UNRES
    wrong = (cls == POS and probe_uv < 0) or (cls == NEG and probe_uv > 0)
    return {"class": cls, "wrong_polarity": bool(wrong), "decision": decision}


def round_probes(lo_uv: int, hi_uv: int, first: bool) -> list[int]:
    """Probe inputs (integer uV) of one round: 11 including the endpoints in
    round 1, the 9 interior points afterwards."""
    width = hi_uv - lo_uv
    if width % FANOUT:
        raise MemoryError_(f"bracket width {width} uV is not divisible by {FANOUT}")
    step = width // FANOUT
    idx = range(0, FANOUT + 1) if first else range(1, FANOUT)
    return [lo_uv + i * step for i in idx]


def n_probes(first: bool) -> int:
    return FANOUT + 1 if first else FANOUT - 1


def round_step_uv(round_no: int) -> int:
    """Probe spacing of round ``round_no`` (1-based) from the fixed schedule."""
    return (INIT_HI_UV - INIT_LO_UV) // FANOUT ** round_no


@dataclass
class Search:
    """The deterministic search for one (PVT point, history)."""

    lo_uv: int = INIT_LO_UV
    hi_uv: int = INIT_HI_UV
    lo_cls: str | None = None
    hi_cls: str | None = None
    rounds: int = 0
    done: bool = False
    rejected: str | None = None
    tally: dict = field(default_factory=lambda: {
        "evaluated": 0, "resolved_positive": 0, "resolved_negative": 0,
        "unresolved": 0, "wrong_polarity": 0, "missing": 0})
    log: list = field(default_factory=list)

    @property
    def active(self) -> bool:
        return not self.done and self.rejected is None

    @property
    def width_uv(self) -> int:
        return self.hi_uv - self.lo_uv

    def threshold_uv(self) -> Fraction | None:
        if not self.done:
            return None
        return Fraction(self.lo_uv + self.hi_uv, 2)

    def next_probes(self) -> list[int]:
        return round_probes(self.lo_uv, self.hi_uv, self.rounds == 0)

    def update(self, decisions: dict[int, float | None]) -> None:
        """Consume one round's decision values, keyed by probe input (uV)."""
        if not self.active:
            return
        first = self.rounds == 0
        probes = self.next_probes()
        self.rounds += 1
        entries = []
        for p in probes:
            c = classify(decisions.get(p), p)
            entries.append((p, c))
            self.tally["evaluated"] += 1
            if c["class"] is None:
                self.tally["missing"] += 1
            else:
                self.tally[c["class"]] += 1
            if c["wrong_polarity"]:
                self.tally["wrong_polarity"] += 1
        self.log.append({
            "round": self.rounds, "bracket_in_uv": [self.lo_uv, self.hi_uv],
            "probes": [{"probe_uv": p, "decision": c["decision"], "class": c["class"],
                        "wrong_polarity": c["wrong_polarity"]} for p, c in entries]})
        if any(c["class"] is None for _, c in entries):
            self.rejected = "missing measurement"
            return
        pts = list(entries)
        if not first:
            pts = [(self.lo_uv, {"class": self.lo_cls})] + pts + [(self.hi_uv, {"class": self.hi_cls})]
        elif pts[0][1]["class"] == UNRES or pts[-1][1]["class"] == UNRES:
            self.rejected = "initial bracket endpoint unresolved"
            return
        if first and not (pts[0][1]["class"] == NEG and pts[-1][1]["class"] == POS):
            self.rejected = ("initial bracket does not contain opposite resolved "
                             "polarities (negative at the low end, positive at the high end)")
            return
        # sign changes among resolved points, in ascending probe order
        changes = []
        prev = None  # (index, class)
        for i, (_, c) in enumerate(pts):
            if c["class"] == UNRES:
                continue
            if prev is not None and c["class"] != prev[1]:
                changes.append((prev[0], i, prev[1], c["class"]))
            prev = (i, c["class"])
        if len(changes) != 1:
            self.rejected = (f"non-monotone resolved polarities ({len(changes)} sign changes)"
                             if changes else "no resolved sign change in the bracket")
            return
        a, b, ca, cb = changes[0]
        if (ca, cb) != (NEG, POS):
            self.rejected = "reversed polarity (positive below negative)"
            return
        if b - a != 1:
            self.rejected = ("unresolved point inside the switching bracket "
                             f"({b - a - 1} between {pts[a][0]} and {pts[b][0]} uV)")
            return
        self.lo_uv, self.hi_uv = pts[a][0], pts[b][0]
        self.lo_cls, self.hi_cls = ca, cb
        if self.width_uv <= RESOLUTION_UV:
            self.done = True


def history_result(search: Search) -> dict:
    thr = search.threshold_uv()
    return {
        "threshold_mv": None if thr is None else float(thr) / 1000.0,
        "threshold_uv": None if thr is None else float(thr),
        "bracket_uv": [search.lo_uv, search.hi_uv] if search.done else None,
        "bracket_width_uv": search.width_uv if search.done else None,
        "rounds": search.rounds,
        "rejected": search.rejected,
        "decision_classification": dict(search.tally),
        "log": search.log,
    }


def memory_shift_uv(p: Search, n: Search) -> Fraction | None:
    a, b = p.threshold_uv(), n.threshold_uv()
    if a is None or b is None:
        return None
    return a - b


def point_result(p: Search, n: Search, *, extra: dict | None = None) -> dict:
    shift = memory_shift_uv(p, n)
    out = {
        "threshold_after_P_mV": history_result(p)["threshold_mv"],
        "threshold_after_N_mV": history_result(n)["threshold_mv"],
        "memory_shift_mV": None if shift is None else float(shift) / 1000.0,
        "abs_memory_shift_mV": None if shift is None else abs(float(shift)) / 1000.0,
        "final_bracket_width_uV": {"P": p.width_uv if p.done else None,
                                   "N": n.width_uv if n.done else None},
        "rejected": ({"P": p.rejected, "N": n.rejected}
                     if (p.rejected or n.rejected or not (p.done and n.done)) else None),
        "P": history_result(p),
        "N": history_result(n),
        "classification_total": {
            k: p.tally[k] + n.tally[k] for k in p.tally},
    }
    if extra:
        out.update(extra)
    return out


# --------------------------------------------------------------------------- #
# control verdicts
# --------------------------------------------------------------------------- #


def long_reset_verdict(shift_uv: float | Fraction | None) -> dict:
    if shift_uv is None:
        return {"verdict": "FAIL", "reason": "paired search rejected: no shift", "abs_shift_uv": None}
    a = abs(float(shift_uv))
    ok = a <= LONG_RESET_MAX_ABS_UV
    return {"verdict": "PASS" if ok else "FAIL", "abs_shift_uv": a,
            "criterion": f"|shift| <= {LONG_RESET_MAX_ABS_UV:g} uV",
            "reason": None if ok else f"|shift| {a:g} uV exceeds {LONG_RESET_MAX_ABS_UV:g} uV"}


def short_reset_verdict(shift_uv, long_shift_uv) -> dict:
    crit = (f"|shift| >= {SHORT_RESET_MIN_ABS_UV:g} uV and exceeds the long-reset |shift| "
            f"by >= {SHORT_OVER_LONG_MIN_UV:g} uV")
    if shift_uv is None or long_shift_uv is None:
        return {"verdict": "FAIL", "abs_shift_uv": None, "criterion": crit,
                "reason": "paired search rejected: no shift"}
    a, b = abs(float(shift_uv)), abs(float(long_shift_uv))
    reasons = []
    if a < SHORT_RESET_MIN_ABS_UV:
        reasons.append(f"|shift| {a:g} uV below {SHORT_RESET_MIN_ABS_UV:g} uV")
    if a - b < SHORT_OVER_LONG_MIN_UV:
        reasons.append(f"excess over long-reset {a - b:g} uV below {SHORT_OVER_LONG_MIN_UV:g} uV")
    return {"verdict": "FAIL" if reasons else "PASS", "abs_shift_uv": a,
            "excess_over_long_uv": a - b, "criterion": crit,
            "reason": "; ".join(reasons) or None}


# --------------------------------------------------------------------------- #
# netlist
# --------------------------------------------------------------------------- #

def _corner_key(process: str, supply: float, temp: float) -> tuple:
    return (process, round(float(supply), 3), float(temp))


def clock_times_ns(period_ns: float) -> dict:
    rise = [FIRST_RISE_NS + k * period_ns for k in range(N_CONDITIONING + 1)]
    return {
        "rise_ns": rise,
        "t_switch_ns": rise[N_CONDITIONING - 1] + SWITCH_AFTER_RISE_NS,
        "t_sample_ns": rise[N_CONDITIONING] + SAMPLE_AFTER_RISE_NS,
        "t_stop_ns": rise[N_CONDITIONING] + HIGH_NS,
        "reset_ns": period_ns - HIGH_NS,
    }


def _ns(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") + "n"


def _sel(supply: float, temp: float) -> str:
    """ngspice expression that is 1 only at one (supply, temperature)."""
    t_idx = TEMPERATURES_C.index(int(temp) if float(temp).is_integer() else temp)
    v_idx = SUPPLIES_V.index(round(float(supply), 2))
    t_cond = ["(temper<0)", "((temper>=0)*(temper<80))", "(temper>=80)"][t_idx]
    v_cond = ["(v(vdd)<1.14)", "((v(vdd)>=1.14)*(v(vdd)<1.26))", "(v(vdd)>=1.26)"][v_idx]
    return f"({t_cond}*{v_cond})"


def lookup_expr(table: dict[tuple, int]) -> str:
    """Sum of corner selectors times integer uV values. ``table`` maps
    (supply, temperature) -> value."""
    if len({int(v) for v in table.values()}) == 1:
        return str(int(next(iter(table.values()))))
    terms = [f"{_sel(s, t)}*{int(v)}" for (s, t), v in sorted(table.items())]
    return "+".join(terms) if terms else "0"


def compose_circuit(period_ns: float, first: bool, step_uv: int,
                    lo_tables: dict[str, dict[tuple, int]]) -> str:
    """The bench circuit for one round.

    ``lo_tables[h]`` maps (supply, temperature) -> the low end (uV) of
    history ``h``'s bracket at that PVT point; the probe of instance ``m`` is
    ``lo + m * step`` where ``m`` runs 0..10 (round 1) or 1..9.
    """
    ck = clock_times_ns(period_ns)
    mult = list(range(0, FANOUT + 1)) if first else list(range(1, FANOUT))
    L = [
        "* ---- bench: memory / hysteresis (issue #159) ---------------------------",
        "* Two histories in ONE netlist: P (3 strobes at +50 mV, then the probe) and",
        "* N (3 strobes at -50 mV, then the SAME probe grid), each probe on its own",
        "* DUT instance from the same clock and supply. The probe differential for",
        "* instance m is lo + m*step (integer uV); `lo` is looked up per PVT point from",
        "* the committed bracket of the previous round, `step` is the round's fixed",
        "* spacing. The probe actually applied is measured (s_<h>_<m>) and checked",
        "* against the plan, so a wrong lookup rejects the point instead of misreporting.",
        f"* clock: {HIGH_NS:g} ns high, period {period_ns:g} ns (reset {ck['reset_ns']:g} ns);",
        f"* decision sampled {SAMPLE_AFTER_RISE_NS:g} ns after the fourth rising edge",
        f"* (t = {ck['t_sample_ns']:g} ns).",
        f".options {' '.join(OPTIONS)}",
        "",
        "vsup  vdd  0 dc 1.2",
        # unit pulse scaled by the live supply (klt sim alters vsup per corner)
        f"vclku clku 0 pulse(0 1 {_ns(FIRST_RISE_NS)} 100p 100p {_ns(HIGH_NS)} {_ns(period_ns)})",
        "Bclk  clk  0 v = 'v(clku)*v(vdd)'",
        "vcm   cm   0 dc {dut_vcm}",
        f"vsw   sw   0 pwl(0 0 {_ns(ck['t_switch_ns'])} 0 {_ns(ck['t_switch_ns'] + SWITCH_RAMP_NS)} 1)",
        f"vcp   cp   0 dc {CONDITION_V}",
        f"vcn   cn   0 dc {-CONDITION_V}",
        "Btchk tcheck 0 v = 'temper'",
    ]
    for h in HISTORIES:
        L.append(f"Blo{h}   lo{h}   0 v = '{lookup_expr(lo_tables[h])}'")
    L.append("")
    for h in HISTORIES:
        cond = "cp" if h == "P" else "cn"
        for m in mult:
            n = f"{h}{m}"
            L += [
                f"* history {h}, probe multiplier {m}",
                f"Bs{n} s{n} 0 v = 'v({cond})*(1-v(sw)) + (v(lo{h})+{m}*{step_uv})*1e-6*v(sw)'",
                f"Eap{n} ap{n} cm s{n} 0 0.5",
                f"Ean{n} an{n} cm s{n} 0 -0.5",
                f"ib{n}  vdd ibn{n} dc {{dut_ib}}",
                f"X{n}   ap{n} an{n} clk ibn{n} dout{n} doutb{n} vdd 0 comparator_dut",
                f"Bd{n} d{n} 0 v = '(v(dout{n})-v(doutb{n}))/v(vdd)'",
            ]
    return "\n".join(L) + "\n"


REFERENCE_CIRCUIT = EXPERIMENT_DIR / "testbench" / "memory.circuit.spice"


def reference_circuit() -> str:
    """The committed reference netlist: the nominal round-1 circuit (uniform
    -50 mV bracket low end), i.e. the generator's output before any bracket
    lookup is specialised. Drift-guarded by the unit tests."""
    tables = {h: {(s, t): INIT_LO_UV for s in SUPPLIES_V for t in TEMPERATURES_C} for h in HISTORIES}
    return compose_circuit(NOMINAL_PERIOD_NS, True, round_step_uv(1), tables)


def meas_name(kind: str, h: str, m: int | None = None) -> str:
    """Measurement names are LOWER CASE: ngspice folds .meas names to lower
    case in its log, and the pinned klt (0.5.0) matches the log case-
    sensitively, so a mixed-case name is reported as 'produced no value'."""
    return (f"lo_{h}_meas" if kind == "lo" else f"{kind}_{h}_{m}").lower()


def measurements(period_ns: float, first: bool) -> list[dict]:
    ck = clock_times_ns(period_ns)
    ts = _ns(ck["t_sample_ns"])
    meas = [
        {"name": "vdd_meas", "spice": f".meas tran vdd_meas find v(vdd) at={_ns(FIRST_RISE_NS - 5)}", "unit": "V"},
        {"name": "temp_meas", "spice": ".meas tran temp_meas find v(tcheck) at=1n", "unit": "C"},
    ]
    for h in HISTORIES:
        meas.append({"name": meas_name("lo", h), "spice":
                     f".meas tran {meas_name('lo', h)} find v(lo{h}) at=1n", "unit": "uV"})
    mult = list(range(0, FANOUT + 1)) if first else list(range(1, FANOUT))
    for h in HISTORIES:
        for m in mult:
            meas.append({"name": meas_name("d", h, m), "spice":
                         f".meas tran {meas_name('d', h, m)} find v(d{h}{m}) at={ts}", "unit": "V/V"})
            meas.append({"name": meas_name("s", h, m), "spice":
                         f".meas tran {meas_name('s', h, m)} find v(s{h}{m}) at={ts}", "unit": "V"})
    return meas


def analysis_args(period_ns: float) -> str:
    ck = clock_times_ns(period_ns)
    return f"5p {_ns(ck['t_stop_ns'])}"


def compose_body(period_ns: float, first: bool, step_uv: int, lo_tables: dict, *,
                 title: str, osdi_dir: str = build_mod.BATCH_OSDI_DIR,
                 dut_json: Path = build_mod.DUT_JSON) -> str:
    binding = build_mod.load_dut_binding(dut_json)
    params = dict(binding.get("params") or {})
    dut_path: Path = binding["_netlist_path"]
    dut_bytes = dut_path.read_bytes()
    dut_text = dut_bytes.decode("utf-8")
    try:
        dut_rel = dut_path.relative_to(build_mod.REPO_ROOT).as_posix()
    except ValueError:
        dut_rel = dut_path.name
    circuit = compose_circuit(period_ns, first, step_uv, lo_tables)
    lines = [
        f"* {title} -- klt sim netlist BODY (sim/comparator-memory, issue #159)",
        "* GENERATED by `python3 sim/run_memory.py` (sim/kltsim/memory.py) -- do not edit.",
        f"*   circuit sha256={build_mod.sha256_bytes(circuit.encode('utf-8'))}",
        f"*   DUT:     {dut_rel}  sha256={build_mod.sha256_bytes(dut_bytes)}",
        f"*            sim/dut.json id={binding.get('id')} provenance={binding.get('provenance')}",
        f"*   OSDI:    {osdi_dir}",
        "*",
        "* klt sim netlist-body convention: no .lib / .temp / analysis / .end here.",
        "* The .control block is the one deliberate deviation (see sim/kltsim/build.py):",
        "* SG13G2's MOS models are OSDI and must be pre_osdi-loaded.",
        ".control",
    ]
    lines += [f"pre_osdi {osdi_dir.rstrip('/')}/{name}" for name in build_mod.OSDI_MODELS]
    lines += [".endc", "", "* ---- DUT operating point (sim/dut.json params) ----"]
    for key, value in sorted(params.items()):
        lines.append(f".param {key}={value!r}")
    lines += [
        "",
        f"{build_mod.DUT_BEGIN} {dut_rel} sha256={build_mod.sha256_bytes(dut_bytes)} ====",
        dut_text.rstrip("\n"),
        f"{build_mod.DUT_END} ====",
        "",
        circuit.rstrip("\n"),
        "",
    ]
    return "\n".join(lines)


def compose_request(period_ns: float, first: bool, body_name: str, processes: list[str], *,
                    backend: str = "batch", grid: list[tuple] | None = None,
                    comment: list[str] | None = None, round_no: int | None = None) -> dict:
    """A ``klt sim`` request. ``grid`` (list of (supply, temperature)) narrows the
    corners to one PVT point; the default is the 3 x 3 grid of each process."""
    if grid is None:
        supplies, temps = list(SUPPLIES_V), list(TEMPERATURES_C)
    else:
        supplies = sorted({s for s, _ in grid})
        temps = sorted({t for _, t in grid})
    ck = clock_times_ns(period_ns)
    return {
        "_comment": (comment or []) + [
            "sg13g2-comparator -- klt sim request, bench `memory` (issue #159). CHARACTERIZATION, "
            "not compliance: no limits are declared, so the envelope status grades nothing.",
            "GENERATED by `python3 sim/run_memory.py`; the committed copy is byte-for-byte what was submitted.",
            f"period {period_ns:g} ns, reset {ck['reset_ns']:g} ns, decision sampled at "
            f"{ck['t_sample_ns']:g} ns (9 ns after the fourth rising edge).",
        ],
        "engine": "ngspice",
        "netlist": body_name,
        "netlist_source": "schematic",
        "backend": backend,
        "models": dict(MODELS),
        "corners": {
            "process": list(processes),
            "supply_v": {"vsup": supplies},
            "temperature_c": temps,
        },
        "analysis": {"kind": "tran", "args": analysis_args(period_ns)},
        "measurements": measurements(period_ns, first),
        "options": {"timeout_s": 1800, "keep_artifacts": True},
    }


# --------------------------------------------------------------------------- #
# envelope reading
# --------------------------------------------------------------------------- #

PROBE_TOL_UV = 0.5   # applied-vs-planned probe agreement
SUPPLY_TOL_V = 1e-3
TEMP_TOL_C = 1e-3


def corner_values(corner: dict) -> dict[str, float | None]:
    out: dict = {}
    for m in corner.get("measurements") or []:
        name = m.get("name")
        if name in out:
            out[name] = None  # repeated entry: untrusted
            continue
        out[name] = m.get("value")
    return out


def parse_corner_id(corner: dict) -> tuple | None:
    """(process, supply, temperature) of a non-Monte-Carlo klt sim corner."""
    process = corner.get("process")
    supply = (corner.get("supply_v") or {}).get("vsup")
    temp = corner.get("temperature_c")
    if process is None or supply is None or temp is None:
        return None
    return (process, round(float(supply), 3), float(temp))


def extract_round(env: dict, period_ns: float, first: bool, plan: dict[tuple, dict]) -> dict:
    """Per corner, the decisions each history's probes produced.

    ``plan[(process, supply, temp)] = {"P": {"lo": uV, "probes": [uV...]}, "N": ...}``
    (see :func:`build_plan`) is what the round was built to apply. Returns ``{key: {"P": {probe: decision},
    "N": {...}, "problem": str|None, "runtime_s": ..}}``; a corner whose
    supply/temperature/lookup/probe application does not match the plan, or
    that has any missing value, carries a ``problem`` and no decisions.
    """
    mult = list(range(0, FANOUT + 1)) if first else list(range(1, FANOUT))
    out: dict = {}
    for corner in env.get("corners") or []:
        key = parse_corner_id(corner)
        if key is None:
            continue
        vals = corner_values(corner)
        problem = None
        decisions = {h: {} for h in HISTORIES}
        if corner.get("status") not in ("pass", "ok", "fail"):
            problem = f"corner status {corner.get('status')!r}"
        planned = plan.get(key)
        if problem is None and planned is None:
            problem = "corner not in the round plan"
        if problem is None:
            if vals.get("vdd_meas") is None or abs(vals["vdd_meas"] - key[1]) > SUPPLY_TOL_V:
                problem = f"supply probe {vals.get('vdd_meas')} disagrees with corner {key[1]} V"
            elif vals.get("temp_meas") is None or abs(vals["temp_meas"] - key[2]) > TEMP_TOL_C:
                problem = f"temperature probe {vals.get('temp_meas')} disagrees with corner {key[2]} C"
        if problem is None:
            for h in HISTORIES:
                lo_planned = planned[h]["lo"]
                lo = vals.get(meas_name("lo", h))
                if lo is None or abs(lo - lo_planned) > PROBE_TOL_UV:
                    problem = f"bracket lookup lo_{h}={lo} uV disagrees with plan {lo_planned} uV"
                    break
        if problem is None:
            for h in HISTORIES:
                for m, p in zip(mult, planned[h]["probes"]):
                    d = vals.get(meas_name("d", h, m))
                    s = vals.get(meas_name("s", h, m))
                    if d is None or s is None:
                        problem = f"missing {meas_name('d', h, m)}/{meas_name('s', h, m)}"
                        break
                    if abs(s * 1e6 - p) > PROBE_TOL_UV:
                        problem = f"applied probe {s * 1e6:.3f} uV disagrees with plan {p} uV ({h}{m})"
                        break
                    decisions[h][p] = d
                if problem:
                    break
        out[key] = {"P": decisions["P"], "N": decisions["N"], "problem": problem,
                    "runtime_s": corner.get("runtime_s"), "corner_id": corner.get("corner_id")}
    return out


# --------------------------------------------------------------------------- #
# campaign replay
# --------------------------------------------------------------------------- #


def grid_keys(processes=None) -> list[tuple]:
    return [(f"mos_{p}", round(s, 3), float(t))
            for p in (processes or PROCESSES) for s in SUPPLIES_V for t in TEMPERATURES_C]


@dataclass
class PointSearch:
    key: tuple
    P: Search = field(default_factory=Search)
    N: Search = field(default_factory=Search)
    problem: str | None = None

    def active(self) -> bool:
        return self.problem is None and (self.P.active or self.N.active)

    def plan(self) -> dict:
        return {h: getattr(self, h).next_probes() for h in HISTORIES}


def new_searches(keys) -> dict[tuple, PointSearch]:
    return {k: PointSearch(k) for k in keys}


def build_plan(searches: dict[tuple, PointSearch], round_no: int) -> dict[tuple, dict]:
    """What round ``round_no`` (1-based) applies at every corner: per history the
    bracket low end and the probe inputs. A finished or rejected search is
    still simulated (corners are a Cartesian product) with the placeholder
    bracket lo = -50 mV; its results are ignored by :func:`apply_round`."""
    first = round_no == 1
    step = round_step_uv(round_no)
    mult = range(0, FANOUT + 1) if first else range(1, FANOUT)
    plan = {}
    for key, ps in searches.items():
        plan[key] = {}
        for h in HISTORIES:
            s = getattr(ps, h)
            lo = s.lo_uv if s.active else INIT_LO_UV
            if s.active and s.width_uv != step * FANOUT:
                raise MemoryError_(
                    f"{key} {h}: bracket width {s.width_uv} uV is off the round-{round_no} schedule")
            plan[key][h] = {"lo": lo, "probes": [lo + m * step for m in mult]}
    return plan


def lo_tables_for(plan: dict[tuple, dict]) -> dict[str, dict]:
    """Per history, (supply, temperature) -> bracket low end, for one process's
    corners of ``plan``."""
    tables: dict = {h: {} for h in HISTORIES}
    for (proc, supply, temp), per in plan.items():
        for h in HISTORIES:
            tables[h][(supply, temp)] = per[h]["lo"]
    return tables


def apply_round(searches: dict[tuple, PointSearch], extracted: dict, first: bool) -> None:
    """Advance every active search with one round's extracted decisions."""
    for key, ps in searches.items():
        if not ps.active():
            continue
        ex = extracted.get(key)
        if ex is None:
            ps.problem = "corner missing from the round's envelope"
            continue
        if ex["problem"]:
            ps.problem = ex["problem"]
            continue
        for h in HISTORIES:
            getattr(ps, h).update(ex[h])


# --------------------------------------------------------------------------- #
# json helper
# --------------------------------------------------------------------------- #


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

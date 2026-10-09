"""Bench definitions: what each ``klt sim`` request measures, and why.

Every measurement here is one verbatim ngspice ``.meas`` card that ``klt
sim`` copies into its generated corner deck. Derived quantities (tau, the
offset of one draw, the injected charge) are computed by ngspice itself
through ``.meas ... param='...'`` so the value in the envelope is the
engine's, not this adapter's.

``limits`` are set ONLY from DR-0002 **Target** bounds (the ratified
compliance column) and from validity gates whose failure means the number
next to them is not a decision-time/offset/charge at all (a wrong decision,
an offset clamped at the edge of the swept window). Stretch bounds are
deliberately NOT encoded as limits: an envelope's own ``status`` is then the
Target verdict of the rows it carries, and the Stretch verdicts are computed
by ``kltsim.grade`` from the very same tool-reported per-corner values. A
measurement with no ``limits`` is reported, never graded, by ``klt sim``.

The ``role`` of each measurement (``spec`` / ``gate`` / ``probe`` /
``reported``) is adapter metadata only -- it is not written into the
request, which stays a pure ``klt sim`` document.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The ratified PVT grid (README.md / DR-0002 Row 5): 5 process x 3 supply
#: x 3 temperature = 45 points. Process names are cornerMOSlv.lib sections.
PROCESSES = ("tt", "ff", "ss", "fs", "sf")
SUPPLIES_V = (1.08, 1.2, 1.32)
TEMPERATURES_C = (-40, 27, 125)

#: cornerMOSlv.lib (models.lib below) -- the one model library the DUT
#: needs: it instantiates only sg13_lv_nmos / sg13_lv_pmos.
MODELS = {"pdk": "ihp-sg13g2", "lib": "libs.tech/ngspice/models/cornerMOSlv.lib"}

LN10 = "2.302585093"


@dataclass(frozen=True)
class Meas:
    name: str
    spice: str
    unit: str | None = None
    limits: dict | None = None
    role: str = "reported"  # spec | gate | probe | reported
    k_sigma: float | None = None

    def request_entry(self) -> dict:
        entry: dict = {"name": self.name, "spice": self.spice}
        if self.unit is not None:
            entry["unit"] = self.unit
        if self.limits is not None:
            entry["limits"] = dict(self.limits)
        if self.k_sigma is not None:
            entry["k_sigma"] = self.k_sigma
        return entry


@dataclass(frozen=True)
class Bench:
    name: str
    circuit: str  # file under sim/klt-corner-verification/benches/
    description: str
    process_sections: tuple[str, ...]
    supply_keys: tuple[str, ...]
    analysis: dict
    measurements: tuple[Meas, ...]
    timeout_s: int
    hosts: int = 1
    split_by_process: bool = False
    monte_carlo: dict | None = None
    has_dut: bool = True  # False: a DUT-free instrument-validation fixture
    probes: dict = field(default_factory=dict)  # corner-application probes

    def measurement(self, name: str) -> Meas:
        for m in self.measurements:
            if m.name == name:
                return m
        raise KeyError(name)


def _sum_dlev() -> str:
    return "+".join(f"dlev{k}" for k in range(33))


REGENERATION = Bench(
    name="regeneration",
    circuit="regeneration.circuit.spice",
    description=(
        "Decision time at 50 mV / 1 mV / 0.1 mV overdrive, regeneration "
        "time constant tau, and average power over one 30 ns (33.3 MHz) "
        "cycle including the tail-bias reference branch -- DR-0002 Rows 3 "
        "and 5."
    ),
    process_sections=tuple(f"mos_{p}" for p in PROCESSES),
    supply_keys=("vsup", "vsupa"),
    analysis={"kind": "tran", "args": "5p 60n"},
    timeout_s=600,
    measurements=(
        # -- corner-application probes ------------------------------------
        Meas("vdd_meas", ".meas tran vdd_meas find v(vdd) at=25n", "V", role="probe"),
        Meas("vdda_meas", ".meas tran vdda_meas find v(vdda) at=25n", "V", role="probe"),
        Meas("temp_meas", ".meas tran temp_meas find v(tcheck) at=1n", "C", role="probe"),
        # -- raw delays (seconds), measured on the SECOND strobe ------------
        Meas("td_a", ".meas tran td_a trig v(clkn) val=0.5 rise=2 targ v(dan) val=0.5 rise=1 td=35n", "s"),
        Meas("td_b", ".meas tran td_b trig v(clkn) val=0.5 rise=2 targ v(dbn) val=0.5 rise=1 td=35n", "s"),
        Meas("td_c", ".meas tran td_c trig v(clkn) val=0.5 rise=2 targ v(dcn) val=0.5 rise=1 td=35n", "s"),
        # -- decision-polarity gates: each instance decided BOTH ways -------
        Meas("dout_od50_first", ".meas tran dout_od50_first find v(dan) at=18n", "V/V", {"max": 0.1}, "gate"),
        Meas("dout_od1_first", ".meas tran dout_od1_first find v(dbn) at=18n", "V/V", {"max": 0.1}, "gate"),
        Meas("dout_od01_first", ".meas tran dout_od01_first find v(dcn) at=18n", "V/V", {"max": 0.1}, "gate"),
        Meas("dout_od50_end", ".meas tran dout_od50_end find v(dan) at=55n", "V/V", {"min": 0.9}, "gate"),
        Meas("dout_od1_end", ".meas tran dout_od1_end find v(dbn) at=55n", "V/V", {"min": 0.9}, "gate"),
        Meas("dout_od01_end", ".meas tran dout_od01_end find v(dcn) at=55n", "V/V", {"min": 0.9}, "gate"),
        # -- DR-0002 Row 3 (Target limits only) -----------------------------
        Meas("td_od50_ns", ".meas tran td_od50_ns param='td_a*1e9'", "ns", {"max": 1.5}, "spec"),
        Meas("td_od1_ns", ".meas tran td_od1_ns param='td_b*1e9'", "ns"),
        Meas("td_od01_ns", ".meas tran td_od01_ns param='td_c*1e9'", "ns", {"max": 2.0}, "spec"),
        Meas("tau_ps", f".meas tran tau_ps param='(td_c-td_b)/{LN10}*1e12'", "ps", {"max": 250.0}, "spec"),
        Meas("resolve_decades", f".meas tran resolve_decades param='td_b/((td_c-td_b)/{LN10})'", "1"),
        # -- DR-0002 Row 5: power (no Target bound is ratified) -------------
        Meas("i_stat", ".meas tran i_stat avg i(vsupa) from=25n to=29n", "A"),
        Meas("i_static_ua", ".meas tran i_static_ua param='abs(i_stat)*1e6'", "uA"),
        Meas("p_avg", ".meas tran p_avg avg par('-v(vdda)*i(vsupa)') from=30n to=60n", "W"),
        Meas("p_avg_uw", ".meas tran p_avg_uw param='p_avg*1e6'", "uW", role="spec"),
    ),
    probes={"supply": ("vdd_meas", "vdda_meas"), "temperature": "temp_meas"},
)


#: Mirror/headroom indicators for the issue #80 bias-point sweep, appended to
#: the regeneration bench of a swept-bias campaign only (``build
#: --bias-probes``); the issue #62 campaign's request is untouched. Instance
#: A's bias branch: ``ibna`` is the diode-connected reference's Vgs (the
#: gate voltage XMT mirrors); ``tmid`` is the drain of the tail device XMT.
#: The flattened node name ``xa.x1.tmid`` (instance order, outermost first)
#: was confirmed by a one-corner fleet smoke (the ``x1.xa.tmid`` ordering
#: yields no value); that smoke is committed under ``campaigns/20261009-issue80/smoke/``.
BIAS_PROBES = (
    Meas("vref_v", ".meas tran vref_v find v(ibna) at=5n", "V"),
    Meas("tmid_eval_v", ".meas tran tmid_eval_v find v(xa.x1.tmid) at=10.4n", "V"),
)


def qkick_measurements(node: str, side: str) -> tuple[Meas, ...]:
    """The Q_kick measure strings for one integrator node (DR-0002 Row 4):
    q at the 29 ns pre-decision reference, its max/min over 30 ... 45 ns, and
    ``max(|max - q29|, |min - q29|)`` converted to fC (1 pF integrator: 1 V
    = 1000 fC). One template serves the real kickback bench (nodes ``qp`` /
    ``qn``) and the known-charge fixture, so the validated strings ARE the
    graded strings."""
    return (
        Meas(f"{node}29", f".meas tran {node}29 find v({node}) at=29n", "V"),
        Meas(f"{node}max", f".meas tran {node}max max v({node}) from=30n to=45n", "V"),
        Meas(f"{node}min", f".meas tran {node}min min v({node}) from=30n to=45n", "V"),
        Meas(
            f"qkick_{side}_fc",
            f".meas tran qkick_{side}_fc param='max(abs({node}max-{node}29),abs({node}min-{node}29))*1e3'",
            "fC",
        ),
    )


def qkick_fixture_measurements(node: str, side: str) -> tuple[Meas, ...]:
    """Fixture-only extras for one case: q at the window end, the signed
    excursions, the net (end-of-window) charge and the peak-volts x C_in
    estimator DR-0002 Row 4 (b) calls biased."""
    return (
        Meas(f"{node}end", f".meas tran {node}end find v({node}) at=45n", "V"),
        Meas(f"qpos_{side}_fc", f".meas tran qpos_{side}_fc param='({node}max-{node}29)*1e3'", "fC"),
        Meas(f"qneg_{side}_fc", f".meas tran qneg_{side}_fc param='({node}min-{node}29)*1e3'", "fC"),
        Meas(f"qnet_{side}_fc", f".meas tran qnet_{side}_fc param='({node}end-{node}29)*1e3'", "fC"),
    )


KICKBACK = Bench(
    name="kickback",
    circuit="kickback.circuit.spice",
    description=(
        "Branch-A (1 kohm / 100 fF) peak transient injected charge Q_kick "
        "measured directly, signal-dependent differential residue against a "
        "non-restoring 1 Gohm / 1 pF source, and the reported peak excursion "
        "-- DR-0002 Row 4."
    ),
    process_sections=tuple(f"mos_{p}" for p in PROCESSES),
    supply_keys=("vsup",),
    analysis={"kind": "tran", "args": "5p 60n"},
    timeout_s=900,
    measurements=(
        Meas("vdd_meas", ".meas tran vdd_meas find v(vdd) at=25n", "V", role="probe"),
        Meas("temp_meas", ".meas tran temp_meas find v(tcheck) at=1n", "C", role="probe"),
        # -- branch A: peak excursion (reporting requirement, unbounded) ----
        Meas("ad_pos", ".meas tran ad_pos max v(ad) from=30n to=45n", "V"),
        Meas("ad_neg", ".meas tran ad_neg min v(ad) from=30n to=45n", "V"),
        Meas("kick_1k_peak_mv", ".meas tran kick_1k_peak_mv param='max(abs(ad_pos),abs(ad_neg))*1e3'", "mV"),
        Meas("kick_1k_pos_mv", ".meas tran kick_1k_pos_mv param='ad_pos*1e3'", "mV"),
        Meas("kick_1k_neg_mv", ".meas tran kick_1k_neg_mv param='ad_neg*1e3'", "mV"),
        # -- branch A: direct Q_kick (DR-0002 Row 4 definition) -------------
        *qkick_measurements("qp", "p"),
        *qkick_measurements("qn", "n"),
        Meas("qkick_fc", ".meas tran qkick_fc param='max(qkick_p_fc,qkick_n_fc)'", "fC", {"max": 25.0}, "spec"),
        # -- branches B/C: signal-dependent differential residue ------------
        Meas("bd0", ".meas tran bd0 find v(bd) at=29n", "V"),
        Meas("bd1", ".meas tran bd1 find v(bd) at=55n", "V"),
        Meas("cd0", ".meas tran cd0 find v(cd) at=29n", "V"),
        Meas("cd1", ".meas tran cd1 find v(cd) at=55n", "V"),
        Meas("kick_sigdep_uv", ".meas tran kick_sigdep_uv param='abs((cd1-cd0)-(bd1-bd0))*1e6'", "uV", {"max": 100.0}, "spec"),
        Meas("bc0", ".meas tran bc0 find v(bc) at=29n", "V"),
        Meas("bc1", ".meas tran bc1 find v(bc) at=55n", "V"),
        Meas("kick_cm_uv", ".meas tran kick_cm_uv param='(bc1-bc0)*1e6'", "uV"),
        # -- decision-correctness gates -------------------------------------
        Meas("dout_1k_end", ".meas tran dout_1k_end find v(dan) at=55n", "V/V", {"min": 0.9}, "gate"),
        Meas("dout_float_small_end", ".meas tran dout_float_small_end find v(dbn) at=55n", "V/V", {"min": 0.9}, "gate"),
        Meas("dout_float_big_end", ".meas tran dout_float_big_end find v(dcn) at=55n", "V/V", {"min": 0.9}, "gate"),
    ),
    probes={"supply": ("vdd_meas",), "temperature": "temp_meas"},
)


#: Known-charge validation of the Q_kick instrument (issue #78). Each case
#: injects an analytic charge through the same ammeter+integrator block;
#: ``q_fc`` is the expected peak |q(t)-q(29 ns)| over 30 ... 45 ns; ``net_fc``
#: the expected end-of-window net, in the instrument's own v(q) x 1000
#: convention; ``sign`` the expected sign of the dominant v(q) excursion.
#: SIGN: charge pushed INTO the pin node (the DUT driving its input node)
#: makes v(q) FALL -- the ammeter's positive terminal is the source-network
#: side, so i(vk) is negative for that direction, and Bq* integrates +i(vk)
#: onto q. (kickback.circuit.spice's header says the opposite; the sign never
#: enters the graded absolute value.) ``FIXTURE_TOL_FC`` is the stated
#: tolerance on each compared quantity.
FIXTURE_TOL_FC = 0.02
FIXTURE_CASES = {
    "a": {"node": "qa", "q_fc": 10.0, "net_fc": -10.0, "sign": -1,
          "what": "unipolar +10 fC (+7 fC before 29 ns and +4 fC after 45 ns excluded)"},
    "b": {"node": "qb", "q_fc": 10.0, "net_fc": 10.0, "sign": +1,
          "what": "unipolar -10 fC"},
    "c": {"node": "qc", "q_fc": 20.0, "net_fc": 0.0, "sign": -1,
          "what": "bipolar +20 fC then -20 fC, net 0"},
    "d": {"node": "qd", "q_fc": 10.0, "net_fc": -10.0, "sign": -1,
          "what": "+10 fC through a restoring 1 kohm / 100 fF node (V x C_in reads ~0.1 fC)"},
}

KICKBACK_FIXTURE = Bench(
    name="kickback_fixture",
    circuit="kickback_fixture.circuit.spice",
    description=(
        "Known-charge validation of the Q_kick instrument: unipolar, "
        "negative, bipolar (zero net, nonzero peak) and restoring-resistor "
        "injections through the kickback bench's own ammeter+integrator "
        "block -- DR-0002 Row 4 instrument validation (issue #78). No DUT."
    ),
    process_sections=("mos_tt",),
    supply_keys=("vsup",),
    analysis={"kind": "tran", "args": "5p 60n"},
    timeout_s=300,
    has_dut=False,
    measurements=tuple(
        m
        for case, spec in FIXTURE_CASES.items()
        for m in (*qkick_measurements(spec["node"], case), *qkick_fixture_measurements(spec["node"], case))
    ) + (
        # case d only: the biased estimator DR-0002 Row 4 (b) discusses,
        # peak node volts x C_in (100 fF: 1 V = 100 fC).
        Meas("vpk_d_v", ".meas tran vpk_d_v max v(apd) from=30n to=45n", "V"),
        Meas("vcest_d_fc", ".meas tran vcest_d_fc param='vpk_d_v*100'", "fC"),
    ),
)


#: DR-0002 Row 1 basis for the whole-latch bench: N = 60 draws per point,
#: seed 20260916 (here: klt's base seed -- see offset_mc.circuit.spice's
#: header for why the draws are a new realization of the same basis).
OFFSET_MC_N = 60
OFFSET_MC_SEED = 20260916
#: staircase quantization step (V): the per-draw offset is resolved to one
#: 3 mV level, so a draw's variance carries step^2/12 of quantization noise
#: that the original bench subtracted (sig_vos_mv's 7.5e-7 V^2 term).
OFFSET_MC_STEP_V = 0.003

OFFSET_MC = Bench(
    name="offset_mc",
    circuit="offset_mc.circuit.spice",
    description=(
        "Whole-latch input-referred offset, one mismatch draw per klt sim "
        "Monte-Carlo sample, N = 60 per PVT point -- DR-0002 Row 1."
    ),
    process_sections=tuple(f"mos_{p}_mismatch" for p in PROCESSES),
    supply_keys=("vsup",),
    analysis={"kind": "tran", "args": "100p 990n"},
    timeout_s=300,
    split_by_process=True,
    monte_carlo={
        "n": OFFSET_MC_N,
        "seed": OFFSET_MC_SEED,
        "vary": "mismatch",
        "quantiles": [0.135, 50, 99.865],
    },
    measurements=(
        Meas("vdd_meas", ".meas tran vdd_meas find v(vdd) at=5n", "V", role="probe"),
        Meas("temp_meas", ".meas tran temp_meas find v(tcheck) at=1n", "C", role="probe"),
        Meas("vbias_mv", ".meas tran vbias_mv find par('v(ibn)*1e3') at=5n", "mV"),
        # RANGE-ADEQUACY GATE: the draw's offset must fall strictly inside
        # the swept -48 ... +48 mV window, else the value is clamped, not
        # measured (the original bench's n_out_of_range check, per draw).
        Meas("lowcount", f".meas tran lowcount param='33-({_sum_dlev()})'", "levels", {"min": 0.5, "max": 32.5}, "gate"),
        # The per-draw offset (original: vos = -0.048 + (lowcount-0.5)*0.003).
        # Limits are the Target (+/-15 mV) and k_sigma = 3 asks klt for its
        # mean +/- 3 sigma window -- see kltsim.grade for how that window
        # relates to DR-0002's per-point 3-sigma statistic.
        Meas(
            "vos_mv",
            ".meas tran vos_mv param='(-0.048+(lowcount-0.5)*0.003)*1e3'",
            "mV",
            {"min": -15.0, "max": 15.0},
            "spec",
            k_sigma=3.0,
        ),
    ),
    probes={"supply": ("vdd_meas",), "temperature": "temp_meas"},
)


#: DR-0002 Row 2 basis (sim/comparator-transient-noise, record
#: 20260921-154729-41cbc7f): N = 80 trials per rung per PVT point, probe
#: overdrive od_x = 1 mV, injected density 36.27 nV/sqrt(Hz). The seed is
#: RECORDED ONLY: klt writes a per-sample `.options seed=` from it, which
#: ngspice-46's TRNOISE generator ignores (see the circuit's header, item 4).
TRANSIENT_NOISE_N = 80
TRANSIENT_NOISE_SEED = 20260916
#: Probe overdrive (V), copied from sim/comparator-transient-noise/testbench/tb.json.
TRANSIENT_NOISE_OD_X_V = 1e-3

TRANSIENT_NOISE = Bench(
    name="transient_noise",
    circuit="transient_noise.circuit.spice",
    description=(
        "Whole-latch TRNOISE-injected decision statistics: three rungs "
        "(-od_x / 0 / +od_x) per sample, one trial per klt sim Monte-Carlo "
        "sample, N = 80 per PVT point -- DR-0002 Row 2 (compliance path). "
        "The DR-designated statistic (grid-wide mean of the per-point "
        "two-rung probit-slope sigma) is computed by sim/kltsim/grade.py "
        "from klt's per-corner means; klt sim cannot grade it itself "
        "(klayout-tools#2960)."
    ),
    # Plain sections: mismatch OFF, as in the original bench (everything
    # static within one strobe belongs to the offset row).
    process_sections=tuple(f"mos_{p}" for p in PROCESSES),
    supply_keys=("vsup",),
    analysis={"kind": "tran", "args": "20p 5.1n 0 20p"},
    timeout_s=300,
    split_by_process=True,
    monte_carlo={
        "n": TRANSIENT_NOISE_N,
        "seed": TRANSIENT_NOISE_SEED,
        # klt requires one of mismatch/process/both. On plain mos_<p>
        # sections no statistical model parameter exists for either seed to
        # reach, so the sample-to-sample variation is TRNOISE's alone.
        "vary": "mismatch",
    },
    measurements=(
        Meas("vdd_meas", ".meas tran vdd_meas find v(vdd) at=0.5n", "V", role="probe"),
        Meas("temp_meas", ".meas tran temp_meas find v(tcheck) at=0.5n", "C", role="probe"),
        # -- raw injected-noise draws: the independence probe ----------------
        Meas("vn0_a", ".meas tran vn0_a find v(vd0) at=0.5n", "V", role="noiseprobe"),
        Meas("vn0_b", ".meas tran vn0_b find v(vd0) at=2.5n", "V", role="noiseprobe"),
        Meas("vn1_a", ".meas tran vn1_a find v(vd1) at=0.5n", "V", role="noiseprobe"),
        # -- decision resolution gates (an unresolved output is no trial) ----
        Meas("d_zero", ".meas tran d_zero find v(dn0) at=5n", "V/V"),
        Meas("d_plus", ".meas tran d_plus find v(dn1) at=5n", "V/V"),
        Meas("d_minus", ".meas tran d_minus find v(dn2) at=5n", "V/V"),
        Meas("res_zero", ".meas tran res_zero param='abs(d_zero-0.5)'", "V/V", {"min": 0.4}, "gate"),
        Meas("res_plus", ".meas tran res_plus param='abs(d_plus-0.5)'", "V/V", {"min": 0.4}, "gate"),
        Meas("res_minus", ".meas tran res_minus param='abs(d_minus-0.5)'", "V/V", {"min": 0.4}, "gate"),
        # -- the trial outcomes: 0/1 per sample; klt's per-corner mean of
        #    each is the original's frac_high_* -----------------------------
        Meas("hit_zero", ".meas tran hit_zero find v(h0) at=5n", "1", role="spec"),
        Meas("hit_plus", ".meas tran hit_plus find v(h1) at=5n", "1", role="spec"),
        Meas("hit_minus", ".meas tran hit_minus find v(h2) at=5n", "1", role="spec"),
    ),
    probes={"supply": ("vdd_meas",), "temperature": "temp_meas",
            "independence": ("vn0_a", "vn0_b", "vn1_a")},
)


BENCHES: dict[str, Bench] = {b.name: b for b in (REGENERATION, KICKBACK, OFFSET_MC, TRANSIENT_NOISE)}

#: Instrument-validation fixtures. Deliberately NOT in BENCHES: they carry no
#: DUT and no spec row, so the campaign builder and grader never see them.
FIXTURE_BENCHES: dict[str, Bench] = {KICKBACK_FIXTURE.name: KICKBACK_FIXTURE}

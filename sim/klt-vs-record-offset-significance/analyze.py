#!/usr/bin/env python3
"""Issue #82: significance of the +13 % klt-vs-record whole-latch offset shift.

Read-only over committed evidence (sim/ is append-only):
  record : sim/comparator-offset-transient-mc/{records/20260917-060858-ea40b57.json,
           corners/20260917-060858-ea40b57/*.log}  (per-draw `vos =` lines)
  klt    : sim/klt-corner-verification/campaigns/20261009-d73a9ac/
           offset_mc.mos_<p>_mismatch.envelope.json (per-draw vos_mv)

Run:  python3 -I sim/klt-vs-record-offset-significance/analyze.py [--out FILE]
Statistic (DR-0002 Row 1): 3*sqrt(pop_var - step^2/12), step = 3 mV, N = 60.
Every number is per PVT point (process x temp x vdd, 45-point grid) or a mean
over that 45-point grid; never a single-corner figure presented as a grid sigma.
"""
import glob, json, math, os, re, sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REC = os.path.join(ROOT, "sim/comparator-offset-transient-mc")
REC_ID = "20260917-060858-ea40b57"
CAMP = os.path.join(ROOT, "sim/klt-corner-verification/campaigns/20261009-d73a9ac")
STEP = 0.003
N = 60
out = []
def P(*a):
    s = " ".join(str(x) for x in a); out.append(s); print(s)

def three_sig(v):
    v = np.asarray(v, float)
    var = v.var(ddof=0) - STEP**2 / 12
    return 3e3 * math.sqrt(max(var, 0.0))   # mV

# ---- record side ----------------------------------------------------------
rec_pts = json.load(open(f"{REC}/records/{REC_ID}.json"))["points"]
rec_draws, rec3, short = {}, {}, []
for p in rec_pts:
    cid = p["corner_id"]
    txt = open(f"{REC}/corners/{REC_ID}/{cid}.log").read()
    v = [float(x) for x in re.findall(r"^vos = (\S+)", txt, re.M)]
    rec3[cid] = p["measurements"]["vos_3sig_mv"]
    if len(v) != N:
        # sf_mismatch_125c_1.32v's committed log carries only 59 of the 60
        # per-draw `vos =` prints (m_n_samples = 60 in the same log). Its
        # reported 3sigma is used for the means; the point is left out of the
        # per-draw matrices (correlation / bootstrap), which use 44 points.
        short.append((cid, len(v)))
        continue
    rec_draws[cid] = np.array(v)
    assert abs(three_sig(v) - rec3[cid]) < 1e-3, (cid, three_sig(v), rec3[cid])

# ---- klt side -------------------------------------------------------------
klt_draws, seeds, seedkey = {}, [], {}
for f in sorted(glob.glob(f"{CAMP}/offset_mc.mos_*_mismatch.envelope.json")):
    for c in json.load(open(f))["corners"]:
        base = c["corner_id"]          # mos_tt_mismatch/1.080V/-40C/mc0
        proc, vdd, t, mc = base.split("/")
        cid = f"{proc[4:]}_{t.lower().replace('c','')}c_{float(vdd[:-1]):.2f}v"
        vos = next(m["value"] for m in c["measurements"] if m["name"] == "vos_mv")
        klt_draws.setdefault(cid, {})[int(mc[2:])] = vos * 1e-3
        seeds.append(c["monte_carlo"]["mismatch_seed"])
        seedkey.setdefault(cid, set()).add(c["monte_carlo"]["mismatch_seed"])
klt_draws = {k: np.array([d[i] for i in sorted(d)]) for k, d in klt_draws.items()}
assert set(klt_draws) == set(rec3), set(klt_draws) ^ set(rec3)
assert all(len(v) == N for v in klt_draws.values())
klt3 = {k: three_sig(v) for k, v in klt_draws.items()}
keys = sorted(rec3)

# ---- step 0: reproduce the issue's numbers -------------------------------
r = np.array([rec3[k] for k in keys]); q = np.array([klt3[k] for k in keys])
ratio = q / r
P("== Reproduction (45-point PVT grid, N=60 per point, DR-0002 Row 1 statistic) ==")
P(f"record grid-mean 3sigma = {r.mean():.3f} mV   (issue: 8.404)")
P(f"klt    grid-mean 3sigma = {q.mean():.3f} mV   (issue: 9.511)")
P(f"ratio of grid means     = {q.mean()/r.mean():.4f}  (+{100*(q.mean()/r.mean()-1):.1f} %)")
P(f"per-point ratio klt/record = {ratio.mean():.3f} +/- {ratio.std(ddof=1):.3f} (SD over 45 points; issue: 1.136 +/- 0.171)")
P(f"naive SE (treats 45 ratios as independent) = {ratio.std(ddof=1)/math.sqrt(45):.4f} -> shift/SE = {(ratio.mean()-1)/(ratio.std(ddof=1)/math.sqrt(45)):.1f} sigma")

# ---- step 1: independence structure --------------------------------------
P("\n== Draw structure across the 45 points ==")
dk = [k for k in keys if k in rec_draws]
P(f"per-draw matrices use {len(dk)} points; short record logs excluded: {short}")
R = np.array([rec_draws[k] for k in dk]); K = np.array([klt_draws[k] for k in dk])
def mean_offdiag_corr(M):
    C = np.corrcoef(M); iu = np.triu_indices(len(M), 1); return C[iu].mean(), C[iu].min()
mr, mn = mean_offdiag_corr(R); mk, kn = mean_offdiag_corr(K)
P(f"record: mean/min pairwise corr of the 60 per-draw offsets between points = {mr:.3f} / {mn:.3f}")
P(f"klt   : mean/min pairwise corr of the 60 per-draw offsets between points = {mk:.3f} / {kn:.3f}")
P(f"klt mismatch_seed values: {len(seeds)} total, {len(set(seeds))} unique")
# klt's per-sample seed depends on (vdd, temp, sample) but NOT on the process section:
grp = {}
for k in keys:
    _, tc, vv = k.rsplit("_", 2)[0], k.split("_")[-2], k.split("_")[-1]
    grp.setdefault((tc, vv), []).append(k)
same = all(seedkey[a] == seedkey[b] for g in grp.values() for a in g for b in g)
P(f"klt: {len(grp)} (temp,vdd) groups; the 60 mismatch seeds are IDENTICAL across the 5 process sections within a group: {same}")
P(f"      -> klt has {len(grp)} independent seed streams (not 45); points in a group share draws (common random numbers)")
gi = [[dk.index(k) for k in g if k in dk] for g in grp.values()]
Ck = np.corrcoef(K)
wk = np.mean([Ck[i, j] for g in gi for i in g for j in g if i < j])
bk = np.mean([Ck[i, j] for a, g in enumerate(gi) for b, h in enumerate(gi) if a != b for i in g for j in h])
P(f"klt: mean pairwise corr within a (temp,vdd) group = {wk:.3f}; across groups = {bk:.3f}")
Cr = np.corrcoef(R)
P(f"record: all points share the single stream: mean pairwise corr = {mr:.3f}")
# effective number of independent record sigma estimates: variance of grid mean
# of per-point sigma-hat when sigma-hat_i are correlated with rho_ij.

# ---- step 1b: bootstrap SE of each grid mean preserving the structure ----
rng = np.random.default_rng(82)
B = 20000
def boot(M, joint):
    """Resample draw indices; joint=True uses the SAME indices at every point
    (record: points share draws), False resamples each point independently."""
    means = np.empty(B)
    for b in range(B):
        if joint:
            idx = rng.integers(0, N, N); s = [three_sig(M[i][idx]) for i in range(len(M))]
        else:
            s = [three_sig(M[i][rng.integers(0, N, N)]) for i in range(len(M))]
        means[b] = np.mean(s)
    return means
B = 4000
def boot_groups(M, groups):
    """klt: resample the draw index jointly inside each seed group, independently across groups."""
    means = np.empty(B)
    for b in range(B):
        s = []
        for g in groups:
            idx = rng.integers(0, N, N); s += [three_sig(M[i][idx]) for i in g]
        means[b] = np.mean(s)
    return means
bR = boot(R, True); bK_ind = boot(K, False); bK = boot_groups(K, gi)
P("\n== Bootstrap SE of the grid-mean 3sigma (B=%d, seed 82) ==" % B)
P(f"record (joint resample, shared draws across points): SE = {bR.std(ddof=1):.3f} mV = {100*bR.std(ddof=1)/r.mean():.1f} % of mean")
P(f"klt   (resample jointly within each of 9 seed groups): SE = {bK.std(ddof=1):.3f} mV = {100*bK.std(ddof=1)/q.mean():.1f} % of mean   <- used")
P(f"klt   (if all 44 points were independent; NOT the case): SE = {bK_ind.std(ddof=1):.3f} mV")
bK_joint = boot(K, True)
P(f"klt   (if all points shared ONE stream; not the case): SE = {bK_joint.std(ddof=1):.3f} mV  [for reference]")
d = q.mean() - r.mean()
se = math.hypot(bR.std(ddof=1), bK.std(ddof=1))
P(f"\ndifference of grid means = {d:.3f} mV; combined SE = {se:.3f} mV -> {d/se:.2f} sigma")
lr = np.log(q.mean()) - np.log(r.mean())
lse = math.hypot(np.log(bR).std(ddof=1), np.log(bK).std(ddof=1))
P(f"log-ratio {lr:.4f} (ratio {math.exp(lr):.4f}); SE(log) = {lse:.4f} -> {lr/lse:.2f} sigma")
# analytic cross-check: relative SE of an N=60 sigma estimate ~ 1/sqrt(2(N-1))
a_rec = 1/math.sqrt(2*(N-1)); a_klt = a_rec/math.sqrt(9)
P(f"analytic cross-check: rec {100*a_rec:.1f} % (fully common) , klt {100*a_klt:.1f} % (9 independent seed streams) -> {100*math.hypot(a_rec,a_klt):.1f} % ; shift/SE = {math.log(q.mean()/r.mean())/math.hypot(a_rec,a_klt):.2f} sigma")
# Wilson-style: a two-sided p from the normal approximation on the log-ratio
z = lr/lse
p = math.erfc(abs(z)/math.sqrt(2))
P(f"two-sided p (normal approx) = {p:.3f}")
open(os.path.join(os.path.dirname(__file__), "analysis_output.txt") if "--out" not in sys.argv else sys.argv[sys.argv.index("--out")+1], "w").write("\n".join(out) + "\n")

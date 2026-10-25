"""Station-closure optimisation.

Rule (agreed with the project owner):
  * Every demand point that is within 10 min of some station today must still be
    within 10 min of a remaining station after closures (people already outside
    10 min today are not counted against a plan).
  * 建國、後港、永吉、忠孝 may not be closed.
  * Pure driving time, ambulance speed assumptions; no back-fill / busy-unit effects.

Part A  max number of closures (set-cover ILP, CBC via PuLP), per speed scenario.
Part B  best set of exactly K closures: minimise population-weighted mean
        nearest-station time, subject to the coverage rule (ILP p-median on
        aggregated demand, then exact re-evaluation on all demand points).
"""
import os, json, itertools
import numpy as np
import pandas as pd
import pulp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = f"{ROOT}/data/cache"
OUT = f"{ROOT}/output"
os.makedirs(OUT, exist_ok=True)
LIMIT = 600
K_TARGET = 10

st = pd.read_csv(f"{C}/stations_snapped.csv")
demand = pd.read_parquet(f"{C}/demand.parquet")
pop = demand["pop"].values
names = st.name.tolist()
S = len(names)
protected = set(st.loc[st.protected == 1, "name"])
assert protected == {"建國分隊", "後港分隊", "永吉分隊", "忠孝分隊"}, protected


def coverage_rows(T):
    """Unique coverage patterns (which stations reach a point ≤10 min) for points covered today."""
    cov = T <= LIMIT
    today = cov.any(0)
    pats, inv = np.unique(cov[:, today].T, axis=0, return_inverse=True)
    return pats, today


def max_closures(T, extra_fixed_open=()):
    pats, _ = coverage_rows(T)
    m = pulp.LpProblem("min_open", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(S)]
    m += pulp.lpSum(x)
    for p in pats:
        m += pulp.lpSum(x[i] for i in np.flatnonzero(p)) >= 1
    for i, n in enumerate(names):
        if n in protected or n in extra_fixed_open:
            m += x[i] == 1
    m.solve(pulp.PULP_CBC_CMD(msg=0))
    assert pulp.LpStatus[m.status] == "Optimal"
    keep = [names[i] for i in range(S) if x[i].value() > 0.5]
    return S - len(keep), keep, len(pats)


def evaluate(T, closed):
    open_idx = [i for i, n in enumerate(names) if n not in closed]
    best_all = T.min(0)
    best = T[open_idx].min(0)
    today = best_all <= LIMIT
    within = best <= LIMIT
    n_within = (T[open_idx] <= LIMIT).sum(0)
    return {
        "closed": sorted(closed),
        "coverage_kept": bool(within[today].all()),
        "pop_lost_coverage": float(pop[today & ~within].sum()),
        "pop_within_10min_pct": float(pop[within].sum() / pop.sum() * 100),
        "mean_min": float(np.average(best, weights=pop) / 60),
        "p90_min": float(weighted_quantile(best, pop, 0.9) / 60),
        "max_min_covered_pop": float(best[today].max() / 60),
        "pop_double_covered_pct": float(pop[n_within >= 2].sum() / pop.sum() * 100),
    }


def weighted_quantile(v, w, q):
    o = np.argsort(v)
    cw = np.cumsum(w[o])
    return v[o][np.searchsorted(cw, q * cw[-1])]


GRID_M = 150


def best_k_closures(T, k):
    """p-median with exact coverage constraints.

    Objective (population-weighted time) is computed on demand aggregated to a
    150 m grid (pop-weighted mean time per station per cell); the 10-minute rule
    is enforced exactly on every demand point via its coverage pattern.
    Assignment is restricted to each cell's 8 nearest stations.
    """
    cell = (np.floor(demand.x.values / GRID_M).astype(np.int64) * 100000
            + np.floor(demand.y.values / GRID_M).astype(np.int64))
    _, inv = np.unique(cell, return_inverse=True)
    G = inv.max() + 1
    w = np.bincount(inv, weights=pop)
    Tg = np.vstack([np.bincount(inv, weights=pop * np.minimum(T[i], 3600), minlength=G) for i in range(S)])
    Tg = Tg / np.maximum(w, 1e-9)
    pats, _ = coverage_rows(T)

    m = pulp.LpProblem("pmedian", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(S)]
    y = {}
    for g in np.flatnonzero(w > 0):
        for i in np.argsort(Tg[:, g])[:8]:
            y[i, g] = pulp.LpVariable(f"y{i}_{g}", lowBound=0)
    m += pulp.lpSum(w[g] * Tg[i, g] * v for (i, g), v in y.items())
    m += pulp.lpSum(x) == S - k
    by_g = {}
    for (i, g), v in y.items():
        by_g.setdefault(g, []).append(v)
        m += v <= x[i]
    for lst in by_g.values():
        m += pulp.lpSum(lst) == 1
    for p in pats:
        m += pulp.lpSum(x[i] for i in np.flatnonzero(p)) >= 1
    for i, n in enumerate(names):
        if n in protected:
            m += x[i] == 1
    m.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=600))
    status = pulp.LpStatus[m.status]
    closed = [names[i] for i in range(S) if x[i].value() < 0.5]
    return closed, status, G


results = {}
T = {s: np.load(f"{C}/times_{s}.npy").astype(float) for s in ("base", "slow", "fast")}
for s in ("base", "slow", "fast"):
    kmax, keep, npat = max_closures(T[s])
    results[s] = {"max_closures": kmax, "max_closure_set": sorted(set(names) - set(keep)), "patterns": npat,
                  "baseline": evaluate(T[s], [])}
    print(f"[{s}] max closures keeping coverage: {kmax}  (coverage patterns: {npat})")

# Part B: optimal 10 under base speeds, then stress-test under slow speeds
closed10, status, G = best_k_closures(T["base"], K_TARGET)
print(f"best {K_TARGET} (base): status={status}, groups={G}: {closed10}")
results["recommended_10"] = {"status": status, "closed": closed10,
                             **{f"eval_{s}": evaluate(T[s], closed10) for s in T}}

# robust variant: choose 10 under the slow scenario so it holds even in heavier traffic
closed10_slow, status_s, _ = best_k_closures(T["slow"], K_TARGET)
results["robust_10"] = {"status": status_s, "closed": closed10_slow,
                        **{f"eval_{s}": evaluate(T[s], closed10_slow) for s in T}}
print(f"best {K_TARGET} (slow): {closed10_slow}")

# curve: best mean time for k = 0..kmax under base
curve = []
for k in range(0, results["base"]["max_closures"] + 1, 2):
    c, stt, _ = best_k_closures(T["base"], k) if k else ([], "Optimal", 0)
    ev = evaluate(T["base"], c)
    curve.append({"k": k, "status": stt, **ev})
    print(f"k={k:2d} mean={ev['mean_min']:.2f} p90={ev['p90_min']:.2f} double={ev['pop_double_covered_pct']:.1f}% {stt}")
results["curve_base"] = curve

json.dump(results, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)

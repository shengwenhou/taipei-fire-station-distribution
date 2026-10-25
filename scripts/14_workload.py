"""Station workload (expected annual ambulance dispatches) before and after closures.

Calls: 2025 (民國114年) ambulance dispatches by district from 臺北市消防統計年報 表6-1,
spread within each district in proportion to resident population. Each demand point's
calls go to its nearest open station (first-due). The 127 calls recorded as 「其他」
(outside the 12 districts) are left out.

Overload rule: a station is flagged when its expected load after closures exceeds the
busiest station's load today (an observed, currently-working level in this model).
"""
import os, json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = f"{ROOT}/data/cache"

st = pd.read_csv(f"{C}/stations_snapped.csv")
d = pd.read_parquet(f"{C}/demand.parquet")
ems = pd.read_csv(f"{ROOT}/data/raw/ems/ems_calls_by_district_114.csv")
names = st.name.tolist()

dist_pop = d.groupby("district")["pop"].sum()
rate = ems.set_index("district").ambulance_dispatches_2025 / dist_pop
d["calls"] = d["pop"] * d.district.map(rate)
assert abs(d.calls.sum() - ems.ambulance_dispatches_2025.sum()) < 1


def loads(T, closed):
    open_idx = np.array([i for i, n in enumerate(names) if n not in closed])
    nearest = open_idx[T[open_idx].argmin(0)]
    return pd.Series(np.bincount(nearest, weights=d.calls.values, minlength=len(names)), index=names)


plans = {"現況": []}
for std, fname in (("d8", "results_drive480.json"), ("d10", "results.json")):
    r = json.load(open(f"{ROOT}/output/{fname}"))
    plans[f"建議10隊_{std}"] = r["robust_10"]["closed"]

T = np.load(f"{C}/times_base.npy").astype(float)
table = pd.DataFrame({k: loads(T, set(v)) for k, v in plans.items()}).round(0)
cap = table["現況"].max()
out = table.copy()
out.insert(0, "district", st.set_index("name").district)
out.to_csv(f"{ROOT}/output/station_workload_2025.csv")

print("calls per 1,000 residents by district:")
print((rate * 1000).round(1).sort_values(ascending=False).to_string())
print(f"\nbusiest station today: {table['現況'].idxmax()} {cap:,.0f}/yr ({cap/365:.1f}/day)")
for k in plans:
    if k == "現況":
        continue
    col = table[k]
    over = col[col > cap].sort_values(ascending=False)
    up = (col - table["現況"])[col > 0].sort_values(ascending=False).head(5)
    print(f"\n[{k}] max {col.max():,.0f} ({col.idxmax()}); stations above today's max: {len(over)} {over.to_dict()}")
    print("  biggest increases:", {n: f"+{v:,.0f} ({col[n]/table['現況'][n]-1:+.0%})" for n, v in up.items()})

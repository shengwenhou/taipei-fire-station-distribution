"""Compact data bundle for the interactive web page (web/data.js).

Demand points are aggregated to a 150 m grid. For each cell and station we keep the
population-weighted mean travel time (seconds, uint16) per speed scenario, plus, for each
response standard, the exact coverage rule as unique coverage patterns (set of
stations within the driving limit of a point covered today) with their population,
and which cells hold each pattern. A plan drops coverage for a pattern only when
every station in it is closed.

Standards: d10 = 10 min pure driving; d8 = 2 min dispatch/turnout + 8 min driving.
"""
import os, json, base64
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = f"{ROOT}/data/cache"
GRID = 150
STANDARDS = {"d10": (600, "results.json"), "d8": (480, "results_drive480.json")}

st = pd.read_csv(f"{C}/stations_snapped.csv")
d = pd.read_parquet(f"{C}/demand.parquet")
pop = d["pop"].values
S = len(st)

cell = (np.floor(d.x.values / GRID).astype(np.int64) * 100000 + np.floor(d.y.values / GRID).astype(np.int64))
ukeys, inv = np.unique(cell, return_inverse=True)
G = len(ukeys)
w = np.bincount(inv, weights=pop, minlength=G)
cx = (ukeys // 100000 + 0.5) * GRID
cy = (ukeys % 100000 + 0.5) * GRID
ll = gpd.GeoSeries(gpd.points_from_xy(cx, cy), crs=3826).to_crs(4326)

out = {"grid_m": GRID, "cells": {"lon": np.round(ll.x.values, 5).tolist(), "lat": np.round(ll.y.values, 5).tolist(),
                                  "pop": np.round(w, 1).tolist()}, "times": {}, "patterns": {k: {} for k in STANDARDS}}
check = {}
for sc in ("slow", "base", "fast"):
    T = np.load(f"{C}/times_{sc}.npy").astype(float)
    Tc = np.vstack([np.bincount(inv, weights=pop * np.minimum(T[i], 3600), minlength=G) for i in range(S)])
    Tc = np.minimum(np.round(Tc / np.maximum(w, 1e-9)), 3600).astype(np.uint16)
    out["times"][sc] = base64.b64encode(Tc.T.copy().tobytes()).decode()   # row-major [cell][station]
    for std, (limit, _) in STANDARDS.items():
        today = T.min(0) <= limit
        cov = (T <= limit)[:, today].T
        pats, pinv = np.unique(cov, axis=0, return_inverse=True)
        ppop = np.bincount(pinv, weights=pop[today])
        pair = pinv.astype(np.int64) * G + inv[today]
        upair, pairinv = np.unique(pair, return_inverse=True)
        out["patterns"][std][sc] = {
            "bits": base64.b64encode(np.packbits(pats, axis=1).tobytes()).decode(),
            "pop": np.round(ppop, 2).tolist(),
            "pair_pattern": (upair // G).tolist(), "pair_cell": (upair % G).tolist(),
            "pair_pop": np.round(np.bincount(pairinv, weights=pop[today]), 2).tolist(),
        }
        check[(std, sc)] = len(pats)

out["bytes_per_pattern"] = int(np.ceil(S / 8))

st_out = st[["name", "brigade", "squadron", "district", "address", "lat", "lon", "protected", "note"]].fillna("")
out["stations"] = st_out.to_dict(orient="records")

vg = gpd.read_file(f"{C}/villages.geojson")
vg["geometry"] = vg.geometry.simplify(0.00015, preserve_topology=True)
dist = vg.dissolve("district").reset_index()
dist["geometry"] = dist.geometry.simplify(0.0002, preserve_topology=True)

def rings(geom):
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in polys]

out["villages"] = [{"d": r.district, "v": r.village, "p": int(r.population), "r": rings(r.geometry)} for r in vg.itertuples()]
out["districts"] = [{"d": r.district, "r": rings(r.geometry),
                     "c": [round(r.geometry.representative_point().x, 5), round(r.geometry.representative_point().y, 5)]}
                    for r in dist.itertuples()]
# village id per cell (for tooltips)
cells_g = gpd.GeoDataFrame(geometry=ll, crs=4326)
j = gpd.sjoin_nearest(cells_g, gpd.read_file(f"{C}/villages.geojson")[["district", "village", "geometry"]],
                      how="left").groupby(level=0).first()
out["cells"]["vill"] = (j.district + " " + j.village).tolist()

out["results"] = {}
for std, (limit, fname) in STANDARDS.items():
    res = json.load(open(f"{ROOT}/output/{fname}"))
    out["results"][std] = {
        "limit_s": limit,
        "scenarios": {s: {"max": res[s]["max_closures"], "max_set": res[s]["max_closure_set"], "baseline": res[s]["baseline"]}
                      for s in ("slow", "base", "fast")},
        "robust10": res["robust_10"], "best10_base": res["recommended_10"], "curve": res["curve_base"],
    }
out["params"] = json.load(open(f"{C}/params.json"))
os.makedirs(f"{ROOT}/web", exist_ok=True)
js = "window.TFD_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
open(f"{ROOT}/web/data.js", "w").write(js)
print(f"cells={G}, patterns={check}, data.js={len(js)/1e6:.2f} MB")

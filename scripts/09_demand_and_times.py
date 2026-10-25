"""Build population demand points and station→demand travel-time matrices.

Demand: each village's population (內政部 115/09) is spread over its residential-ish
buildings in proportion to footprint area; villages without buildings fall back to
their drivable road nodes. Each building is snapped to the nearest local-road node.

Travel time = network time (directed, one-ways respected, speed by road class)
            + off-network snap distance at 15 km/h.
Outputs per speed scenario: data/cache/times_<scenario>.npy  (stations × demand, seconds)
"""
import os, json
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = f"{ROOT}/data/cache"

SPEED_KMH = {  # ambulance running with lights & siren, typical urban traffic
    "motorway": 60, "trunk": 50, "primary": 35, "secondary": 30, "tertiary": 25,
    "unclassified": 20, "residential": 20, "living_street": 15, "service": 15, "unknown": 15,
}
LINK_KMH = 35          # motorway / trunk ramps
OFFNET_KMH = 15        # building ↔ nearest road node
SCENARIOS = {"base": 1.0, "slow": 0.8, "fast": 1.2}

N = pd.read_parquet(f"{C}/graph_nodes.parquet")
E = pd.read_parquet(f"{C}/graph_edges.parquet")
idx = pd.Series(np.arange(len(N)), index=N.node_id)
E["ui"], E["vi"] = idx[E.u].values, idx[E.v].values
speed = E.road_class.map(SPEED_KMH).astype(float)
speed[E.is_link & E.road_class.isin(["motorway", "trunk"])] = LINK_KMH
E["sec_base"] = E.length_m / (speed / 3.6)

# nodes touching "local" roads (not freeway / expressway) – used for snapping
local = E[~E.road_class.isin(["motorway", "trunk"]) & ~E.is_link]
local_nodes = np.unique(np.concatenate([local.ui.values, local.vi.values]))
XY = N[["x", "y"]].values
tree = cKDTree(XY[local_nodes])

def snap(xy):
    d, i = tree.query(xy)
    return local_nodes[i], d

# ---- stations ----
st = pd.read_csv(f"{ROOT}/data/stations_geocoded.csv")
sg = gpd.GeoSeries(gpd.points_from_xy(st.lon, st.lat), crs=4326).to_crs(3826)
st["node"], st["snap_m"] = snap(np.column_stack([sg.x, sg.y]))
print("station snap distance (m): max %.0f, median %.0f" % (st.snap_m.max(), st.snap_m.median()))
print(st.loc[st.snap_m > 60, ["name", "snap_m"]].to_string())

# ---- villages & population ----
va = pd.read_parquet(f"{C}/village_areas.parquet")
va["region"] = va.hierarchy.map(lambda h: next((x["name"] for x in h if x["subtype"] == "region"), None))
va["district"] = va.hierarchy.map(lambda h: h[2]["name"] if len(h) > 3 else None)
pop = pd.read_csv(f"{ROOT}/data/raw/population/taipei_village_population_11509.csv")
vg = va[va.region == "臺北市"].merge(pop, on=["district", "village"])
vg = gpd.GeoDataFrame(vg, geometry=shapely.from_wkb(vg.wkb), crs=4326).to_crs(3826)
vg = vg[["district", "village", "village_code", "population", "geometry"]].reset_index(drop=True)
assert len(vg) == 456

# ---- buildings → villages ----
b = pd.read_parquet(f"{C}/buildings.parquet")
b = b[(b.subtype.isna() | b.subtype.isin(["residential", "commercial"])) & (b.area_m2 >= 20)]
bg = gpd.GeoDataFrame(b, geometry=gpd.points_from_xy(b.lon, b.lat), crs=4326).to_crs(3826)
bg = gpd.sjoin(bg, vg[["village_code", "geometry"]], predicate="within", how="inner")
w = bg.groupby("village_code").area_m2.transform("sum")
bg["pop"] = bg.area_m2 / w * bg.village_code.map(vg.set_index("village_code").population)
demand = pd.DataFrame({"x": bg.geometry.x, "y": bg.geometry.y, "pop": bg["pop"],
                       "village_code": bg.village_code, "kind": "building"})

# villages with no qualifying building: spread over road nodes inside the village
missing = vg[~vg.village_code.isin(bg.village_code)]
for v in missing.itertuples():
    inside = shapely.contains_xy(v.geometry, XY[local_nodes, 0], XY[local_nodes, 1])
    pts = XY[local_nodes[inside]] if inside.any() else np.array([[v.geometry.centroid.x, v.geometry.centroid.y]])
    demand = pd.concat([demand, pd.DataFrame({"x": pts[:, 0], "y": pts[:, 1], "pop": v.population / len(pts),
                                              "village_code": v.village_code, "kind": "road_node"})])
print(f"villages without buildings: {len(missing)}")
demand = demand.reset_index(drop=True)
demand["node"], demand["snap_m"] = snap(demand[["x", "y"]].values)
dmd_lonlat = gpd.GeoSeries(gpd.points_from_xy(demand.x, demand.y), crs=3826).to_crs(4326)
demand["lon"], demand["lat"] = dmd_lonlat.x.values, dmd_lonlat.y.values
demand = demand.merge(vg[["village_code", "district", "village"]], on="village_code")
print(f"demand points: {len(demand):,}; population: {demand['pop'].sum():,.0f}; "
      f"snap >200 m: {(demand.snap_m > 200).sum()} pts / {demand.loc[demand.snap_m > 200, 'pop'].sum():.0f} people")

demand.to_parquet(f"{C}/demand.parquet")
st.to_csv(f"{C}/stations_snapped.csv", index=False)
vg.to_crs(4326).to_file(f"{C}/villages.geojson", driver="GeoJSON")

# ---- travel times ----
n = len(N)
for name, factor in SCENARIOS.items():
    A = csr_matrix((E.sec_base.values / factor, (E.ui.values, E.vi.values)), shape=(n, n))
    D = dijkstra(A, directed=True, indices=st.node.values, limit=3600)
    T = D[:, demand.node.values] + (demand.snap_m.values / (OFFNET_KMH / 3.6))[None, :]
    np.save(f"{C}/times_{name}.npy", T.astype(np.float32))
    best = T.min(0)
    cov = demand["pop"].values[best <= 600].sum() / demand["pop"].sum()
    print(f"[{name}] population within 10 min of nearest station: {cov:.2%}; "
          f"pop-weighted mean nearest time {np.average(best, weights=demand['pop']) / 60:.2f} min")
json.dump({"speed_kmh": SPEED_KMH, "link_kmh": LINK_KMH, "offnet_kmh": OFFNET_KMH, "scenarios": SCENARIOS},
          open(f"{C}/params.json", "w"), ensure_ascii=False, indent=1)

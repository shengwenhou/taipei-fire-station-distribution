"""Interactive map: stations (kept / closed / protected) and village-level
population-weighted nearest-station time before vs after the recommended closures."""
import os, json
import numpy as np
import pandas as pd
import geopandas as gpd
import folium

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = f"{ROOT}/data/cache"
res = json.load(open(f"{ROOT}/output/results.json"))
closed = set(res["recommended_10"]["closed"])

st = pd.read_csv(f"{C}/stations_snapped.csv")
demand = pd.read_parquet(f"{C}/demand.parquet")
T = np.load(f"{C}/times_base.npy").astype(float)
open_idx = [i for i, n in enumerate(st.name) if n not in closed]
demand["before"] = T.min(0) / 60
demand["after"] = T[open_idx].min(0) / 60

def wavg(g, col):
    return np.average(g[col], weights=g["pop"]) if g["pop"].sum() > 0 else np.nan

agg = demand.groupby("village_code").apply(
    lambda g: pd.Series({"before": wavg(g, "before"), "after": wavg(g, "after"),
                         "max_after": g["after"].max()}), include_groups=False).reset_index()
vg = gpd.read_file(f"{C}/villages.geojson").merge(agg, on="village_code")
vg["delta"] = vg.after - vg.before
vg[["district", "village", "population", "before", "after", "delta", "max_after"]].round(2) \
    .sort_values("delta", ascending=False).to_csv(f"{ROOT}/output/village_times_recommended10.csv", index=False)

m = folium.Map(location=[25.07, 121.55], zoom_start=12, tiles="CartoDB positron")
for col, title, show in [("before", "現況：各里人口加權平均行車時間（分）", False),
                         ("after", "裁撤10隊後：各里人口加權平均行車時間（分）", True),
                         ("delta", "裁撤後增加的時間（分）", False)]:
    bins = [0, 1, 2, 3, 4, 5, 6, 8, 10, 30] if col != "delta" else [0, 0.05, 0.5, 1, 1.5, 2, 3, 5]
    ch = folium.Choropleth(vg, data=vg, columns=["village_code", col], key_on="feature.properties.village_code",
                           fill_color="YlOrRd", bins=bins, fill_opacity=0.65, line_weight=0.3,
                           legend_name=title, name=title, show=show)
    ch.add_to(m)
    folium.GeoJsonTooltip(fields=["district", "village", "population", "before", "after", "delta"],
                          aliases=["區", "里", "人口", "現況(分)", "裁撤後(分)", "增加(分)"],
                          localize=True).add_to(ch.geojson)

colors = {"closed": "red", "protected": "purple", "kept": "blue"}
for r in st.itertuples():
    kind = "closed" if r.name in closed else ("protected" if r.protected == 1 else "kept")
    label = {"closed": "建議裁撤", "protected": "指定保留", "kept": "保留"}[kind]
    folium.CircleMarker([r.lat, r.lon], radius=7, color=colors[kind], fill=True, fill_opacity=0.9,
                        tooltip=f"{r.name}（{label}）<br>{r.address}").add_to(m)
folium.LayerControl(collapsed=False).add_to(m)
m.save(f"{ROOT}/output/map_recommended10.html")
print("saved map;", vg.sort_values("delta", ascending=False).head(10)[["district", "village", "before", "after"]].round(2).to_string())

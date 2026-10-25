"""Collect geocoding candidates per station from three independent sources:
official page map embed, OSM (Nominatim POI search), Overture places."""
import json, os, re, math
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = pd.read_csv(f"{ROOT}/data/stations.csv")
nom = json.load(open(f"{ROOT}/data/raw/geocode_cache.json"))
ov = pd.read_csv(f"{ROOT}/data/raw/overture_fire_places.csv")
ov = ov[ov.category != "fire_protection_service"]
emb = {r["name"]: r for r in json.load(open(f"{ROOT}/data/raw/official_page_extract.json"))}

CN = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7"}
def norm(s):
    s = str(s or "")
    for k, v in CN.items():
        s = s.replace(k + "段", v + "段")
    return re.sub(r"(臺北市|台北市|台灣|\d{3,6}|..區|\s)", "", s).replace("之", "-")

def dist_m(a, b):
    return math.hypot((a[0] - b[0]) * 111000, (a[1] - b[1]) * 111000 * math.cos(math.radians(25)))

rows = []
for _, r in st.iterrows():
    short = r["name"].replace("分隊", "")
    key = norm(r["address"])
    cands = []
    e = emb.get(r["name"])
    if e and e.get("embed_lat"):
        cands.append(("official_embed", e["embed_lat"], e["embed_lng"], ""))
    for q in (r["name"], "消防局" + r["name"]):
        for p in nom.get(q, []):
            dn = p["display_name"]
            if dn.startswith(short) and ("fire_station" == p["type"] or "消防" in dn or "分隊" in dn) and "義消" not in dn and "臺北市" in dn:
                cands.append(("osm", float(p["lat"]), float(p["lon"]), dn[:50]))
    for _, o in ov.iterrows():
        nm = str(o["name"])
        if "義消" in nm or "義勇" in nm or "警察" in nm or "交通" in nm:
            continue
        a = norm(o["addr"])
        if (key and a and (key in a or a in key) and len(a) >= 5) or (short in nm and ("消防" in nm or nm.startswith(short))):
            cands.append(("overture", o["lat"], o["lon"], f"{nm} / {o['addr']}"))
    # dedupe
    seen, uniq = set(), []
    for c in cands:
        k = (c[0], round(c[1], 4), round(c[2], 4))
        if k not in seen:
            seen.add(k); uniq.append(c)
    rows.append((r["name"], r["address"], uniq))

out = []
for name, addr, cands in rows:
    print(f"\n## {name}  {addr}")
    for c in cands:
        print(f"   {c[0]:15s} {c[1]:.6f},{c[2]:.6f}  {c[3]}")
    out.append({"name": name, "address": addr, "candidates": cands})
json.dump(out, open(f"{ROOT}/data/raw/geocode_candidates.json", "w"), ensure_ascii=False, indent=1)

"""Geocode fire stations via Nominatim (OSM).

Strategy: (a) search the station as a named POI (OSM usually maps
amenity=fire_station with names like 臺北市政府消防局XX分隊), (b) search the
street address. Results are cached in data/raw/geocode_cache.json.
"""
import json, time, urllib.parse, urllib.request, os, csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data/raw/geocode_cache.json")
VIEWBOX = "121.44,25.22,121.68,24.95"
UA = "taipei-fire-station-distribution research script (github.com/shengwenhou)"

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

def nominatim(q):
    if q in cache:
        return cache[q]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "viewbox": VIEWBOX, "bounded": 1, "limit": 5,
         "accept-language": "zh-TW", "addressdetails": 1})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    res = json.load(urllib.request.urlopen(req, timeout=30))
    cache[q] = res
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False, indent=1)
    time.sleep(1.1)
    return res

for r in csv.DictReader(open(os.path.join(ROOT, "data/stations.csv"))):
    poi = nominatim(r["name"]) + nominatim("消防局" + r["name"])
    addr = nominatim(r["address"])
    fs = [p for p in poi if p.get("type") == "fire_station" or "消防" in p.get("display_name", "")]
    print(r["name"], "| POI:", [(p["display_name"][:40], p["lat"][:8], p["lon"][:9], p["type"]) for p in fs[:2]],
          "| ADDR:", [(p["display_name"][:40], p["lat"][:8], p["lon"][:9], p["type"]) for p in addr[:1]])

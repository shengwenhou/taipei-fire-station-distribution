"""Shared Nominatim helper with on-disk cache (1 req/s per OSM usage policy)."""
import json, os, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data/raw/geocode_cache.json")
VIEWBOX = "121.44,25.22,121.68,24.95"
UA = "taipei-fire-station-distribution research script (github.com/shengwenhou)"
_cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

def nominatim(q, bounded=True):
    key = q if bounded else "unbounded:" + q
    if key in _cache:
        return _cache[key]
    params = {"q": q, "format": "jsonv2", "limit": 5, "accept-language": "zh-TW", "addressdetails": 1}
    if bounded:
        params.update(viewbox=VIEWBOX, bounded=1)
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": UA})
    res = json.load(urllib.request.urlopen(req, timeout=30))
    _cache[key] = res
    json.dump(_cache, open(CACHE, "w"), ensure_ascii=False, indent=1)
    time.sleep(1.1)
    return res

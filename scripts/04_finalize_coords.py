"""Final station coordinates.

Primary: the fire department's official station locations (data.taipei 「臺北市政府消防局各分隊駐地位置」,
TWD97 TM2, file data/raw/official/tfd_station_locations_20261013.csv).
FINAL below is the earlier hand-checked geocoding (official page embeds, OSM, Overture); it is kept as
a fallback and as an independent check (median 20 m from the official points).
Each entry: (lat, lon, primary source, corroboration)."""
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = {
    "華山分隊": (25.047228, 121.520846, "osm", "overture 中正中隊@北平東路1號"),
    "泉州分隊": (25.024490, 121.512407, "overture@泉州街40號", "overture 第一大隊@泉州街40號4F"),
    "城中分隊": (25.046893, 121.513486, "osm@忠孝西路一段86", ""),
    "忠孝分隊": (25.043813, 121.527299, "overture@忠孝東路二段8號", ""),
    "古亭分隊": (25.011636, 121.537696, "osm", "overture 古亭消防隊"),
    "雙園分隊": (25.028427, 121.495856, "osm@西藏路213-1", "overture"),
    "龍山分隊": (25.038628, 121.499357, "osm@桂林路137", "overture；官網內嵌地圖偏西約400m"),
    "萬芳分隊": (25.002140, 121.566596, "osm@萬美街一段52", "overture 鄰址萬美街一段50號"),
    "木柵分隊": (24.988938, 121.563263, "overture@木柵路二段200號", "osm 木柵路二段街道"),
    "景美分隊": (24.992395, 121.541167, "osm@景文街30", "overture"),
    "寶橋分隊": (24.979882, 121.554880, "overture@樟新街2號", "overture 文山中隊同址"),
    "金華分隊": (25.032656, 121.527859, "osm", "overture"),
    "安和分隊": (25.032784, 121.552167, "overture@安和路二段2號", ""),
    "復興分隊": (25.030033, 121.543230, "osm@復興南路二段92", "overture 同址"),
    "南港分隊": (25.054670, 121.607340, "overture@興中路6號", "osm 興中路街道"),
    "舊莊分隊": (25.044872, 121.615359, "overture@研究院路二段86號", "osm"),
    "成德分隊": (25.047863, 121.586825, "osm", "overture@東新街63巷11號"),
    "信義分隊": (25.040772, 121.569032, "osm@松仁路1", ""),
    "永吉分隊": (25.045468, 121.569290, "osm", "overture@永吉路48號"),
    "莊敬分隊": (25.029600, 121.565048, "osm", "overture 第二大隊@松智路40號"),
    "大直分隊": (25.080227, 121.556829, "osm 第三大隊大直分隊", ""),
    "松江分隊": (25.047663, 121.534126, "osm@松江路25巷9", "官網內嵌地圖；overture 第三大隊同址"),
    "圓山分隊": (25.068596, 121.529791, "osm@民族東路41", "overture"),
    "建國分隊": (25.068068, 121.535660, "overture@民族東路282號", ""),
    "八德分隊": (25.048484, 121.563070, "osm@八德路四段162", "overture"),
    "中崙分隊": (25.048402, 121.545804, "osm", "overture@長安東路二段229號"),
    "東湖分隊": (25.067432, 121.612941, "overture@五分街8號", "overture 交通第六分隊同址"),
    "大湖分隊": (25.083988, 121.601479, "osm@成功路五段3;5", ""),
    "內湖分隊": (25.069710, 121.590263, "osm", "overture@成功路二段378號"),
    "民權分隊": (25.067007, 121.578278, "overture@民權東路六段9號", "osm"),
    "建成分隊": (25.054786, 121.518475, "osm@承德路二段35", "官網內嵌地圖；overture"),
    "延平分隊": (25.050345, 121.511379, "osm@鄭州路109", "overture 大同中隊同址"),
    "大同分隊": (25.061408, 121.513859, "osm", "overture@重慶北路二段223號"),
    "山仔后分隊": (25.133976, 121.545386, "overture 義消山仔后山搜分隊@仰德大道四段161號(同址)", ""),
    "天母分隊": (25.125100, 121.533000, "內插：天母派出所@中山北路七段192號之鄰址", "誤差約30m"),
    "福安分隊": (25.096690, 121.497060, "osm", "官網內嵌地圖"),
    "社子分隊": (25.079383, 121.511213, "osm", "官網內嵌地圖；overture"),
    "劍潭分隊": (25.089967, 121.527846, "osm@中山北路五段376", "官網內嵌地圖"),
    "雙溪分隊": (25.097667, 121.544674, "osm", "overture@至善路二段41號"),
    "後港分隊": (25.087180, 121.518090, "overture 後港高級救護分隊@福港街153號", ""),
    "陽明山分隊": (25.151470, 121.546465, "osm@勝利街1", "overture"),
    "光明分隊": (25.135160, 121.502448, "osm", "overture@光明路155號"),
    "關渡分隊": (25.123249, 121.466782, "osm@知行路345", ""),
    "石牌分隊": (25.118050, 121.517097, "osm", "overture@石牌路二段101號"),
    "秀山分隊": (25.145663, 121.493115, "osm", ""),
    "福國分隊": (25.101642, 121.510918, "官網內嵌地圖", "osm 福國路街道"),
}
from pyproj import Transformer
import numpy as np

st = pd.read_csv(f"{ROOT}/data/stations.csv")
off = pd.read_csv(f"{ROOT}/data/raw/official/tfd_station_locations_20261013.csv")
off["lon"], off["lat"] = Transformer.from_crs(3826, 4326, always_xy=True).transform(off["經度"].values, off["緯度"].values)
off = off.set_index("分隊名稱")
missing = [n for n in st.name if n not in off.index and n not in FINAL]
assert not missing, missing

def pick(n):
    if n in off.index:
        o = off.loc[n]
        chk = ""
        if n in FINAL:
            d = np.hypot((FINAL[n][0] - o.lat) * 111000, (FINAL[n][1] - o.lon) * 111000 * np.cos(np.radians(25)))
            chk = f"與先前地理編碼相距 {d:.0f} m"
        return (round(o.lat, 6), round(o.lon, 6), f"官方駐地座標（{o['地址']}）", chk)
    return FINAL[n]

rows = {n: pick(n) for n in st.name}
st["lat"] = st.name.map(lambda n: rows[n][0])
st["lon"] = st.name.map(lambda n: rows[n][1])
st["coord_source"] = st.name.map(lambda n: rows[n][2])
st["coord_check"] = st.name.map(lambda n: rows[n][3])
st.to_csv(f"{ROOT}/data/stations_geocoded.csv", index=False)
print(len(st), "stations written;", sum(n in off.index for n in st.name), "from official locations")

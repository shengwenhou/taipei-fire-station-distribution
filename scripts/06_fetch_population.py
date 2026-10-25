"""Village (里) boundaries from Overture divisions + village population from 內政部戶政司 (ODRP014)."""
import duckdb, json, os, urllib.request
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "2026-10-21.0"
YM = "11509"  # 民國115年9月

# --- population (Taipei only) ---
rows = []
for page in range(1, 10):
    url = f"https://www.ris.gov.tw/rs-opendata/api/v1/datastore/ODRP014/{YM}?page={page}"
    d = json.load(urllib.request.urlopen(url, timeout=120))
    rows += [r for r in d["responseData"] if r["site_id"].startswith("臺北市")]
    if page >= int(d["totalPage"]):
        break
pop = pd.DataFrame([{"district": r["site_id"][3:], "village": r["village"], "village_code": r["district_code"],
                     "households": int(r["household_no"]), "population": int(r["people_total"])} for r in rows])
os.makedirs(f"{ROOT}/data/raw/population", exist_ok=True)
pop.to_csv(f"{ROOT}/data/raw/population/taipei_village_population_{YM}.csv", index=False)
print("villages:", len(pop), "population:", pop.population.sum())

# --- boundaries ---
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;"
            "CREATE OR REPLACE SECRET anon (TYPE s3, PROVIDER config, KEY_ID '', SECRET '', REGION 'us-west-2');")
con.execute(f"""
CREATE TABLE div AS SELECT id, names.primary AS name, hierarchies[1] AS h
FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=divisions/type=division/*', hive_partitioning=1)
WHERE country = 'TW' AND subtype = 'locality' AND bbox.xmin > 121.40 AND bbox.xmax < 121.72 AND bbox.ymin > 24.90 AND bbox.ymax < 25.25;
""")
con.execute(f"""
COPY (
  SELECT a.division_id, a.names.primary AS village, d.h AS hierarchy, ST_AsWKB(a.geometry) AS wkb
  FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=divisions/type=division_area/*', hive_partitioning=1) a
  JOIN div d ON d.id = a.division_id
  WHERE a.subtype = 'locality' AND a.is_land
) TO '{ROOT}/data/cache/village_areas.parquet' (FORMAT parquet)
""")
print(con.execute(f"SELECT count(*) FROM '{ROOT}/data/cache/village_areas.parquet'").fetchone())
print(con.execute(f"SELECT village, hierarchy FROM '{ROOT}/data/cache/village_areas.parquet' LIMIT 3").fetchall())

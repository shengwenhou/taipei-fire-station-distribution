"""Pull fire-station-like places in Taipei from Overture Maps (for geocoding cross-check)."""
import duckdb, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "2026-10-21.0"
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; CREATE OR REPLACE SECRET anon (TYPE s3, PROVIDER config, KEY_ID '', SECRET '', REGION 'us-west-2');")
q = f"""
COPY (
  SELECT id, names.primary AS name, taxonomy.primary AS category, phones[1] AS phone,
         ST_X(geometry) AS lon, ST_Y(geometry) AS lat, addresses[1].freeform AS addr
  FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=places/type=place/*', hive_partitioning=1)
  WHERE bbox.xmin BETWEEN 121.44 AND 121.68 AND bbox.ymin BETWEEN 24.95 AND 25.22
    AND (names.primary LIKE '%分隊%' OR taxonomy.primary ILIKE '%fire%' OR basic_category ILIKE '%fire%')
) TO '{ROOT}/data/raw/overture_fire_places.csv' (HEADER)
"""
con.execute(q)
print(con.execute(f"SELECT count(*) FROM '{ROOT}/data/raw/overture_fire_places.csv'").fetchone())

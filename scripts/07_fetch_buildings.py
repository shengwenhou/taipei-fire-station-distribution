"""Overture building footprints in Taipei (centroid, footprint area, floors) used to
spread each village's population to where people actually live."""
import duckdb, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "2026-10-21.0"
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;"
            "SET geometry_always_xy = true; CREATE OR REPLACE SECRET anon (TYPE s3, PROVIDER config, KEY_ID '', SECRET '', REGION 'us-west-2');")
con.execute(f"""
COPY (
  SELECT id, subtype, class, num_floors, height,
         ST_X(ST_Centroid(geometry)) AS lon, ST_Y(ST_Centroid(geometry)) AS lat,
         ST_Area_Spheroid(geometry) AS area_m2
  FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=buildings/type=building/*', hive_partitioning=1)
  WHERE bbox.xmin > 121.45 AND bbox.xmax < 121.67 AND bbox.ymin > 24.95 AND bbox.ymax < 25.22
) TO '{ROOT}/data/cache/buildings.parquet' (FORMAT parquet)
""")
print(con.execute(f"""SELECT count(*), sum(area_m2)/1e6, avg(num_floors IS NOT NULL::INT), avg(height IS NOT NULL::INT),
  quantile_cont(area_m2, 0.5) FROM '{ROOT}/data/cache/buildings.parquet'""").fetchall())
print(con.execute(f"SELECT subtype, count(*) FROM '{ROOT}/data/cache/buildings.parquet' GROUP BY 1 ORDER BY 2 DESC").fetchall())

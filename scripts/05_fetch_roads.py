"""Download Overture road segments for Taipei (+ buffer) to data/cache/segments.parquet."""
import duckdb, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "2026-10-21.0"
BBOX = (121.43, 24.94, 121.69, 25.23)  # Taipei city + ~1-2 km buffer into New Taipei
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;"
            "CREATE OR REPLACE SECRET anon (TYPE s3, PROVIDER config, KEY_ID '', SECRET '', REGION 'us-west-2');")
con.execute(f"""
COPY (
  SELECT id, class, subclass, ST_AsWKB(geometry) AS wkb, connectors, access_restrictions, road_flags, speed_limits
  FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=transportation/type=segment/*', hive_partitioning=1)
  WHERE subtype = 'road'
    AND bbox.xmin < {BBOX[2]} AND bbox.xmax > {BBOX[0]} AND bbox.ymin < {BBOX[3]} AND bbox.ymax > {BBOX[1]}
) TO '{ROOT}/data/cache/segments.parquet' (FORMAT parquet)
""")
print(con.execute(f"SELECT class, count(*) FROM '{ROOT}/data/cache/segments.parquet' GROUP BY 1 ORDER BY 2 DESC").fetchall())

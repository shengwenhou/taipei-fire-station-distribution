"""Build a directed, drivable road graph from Overture segments.

Output: data/cache/graph_nodes.parquet (node_id, x, y in EPSG:3826)
        data/cache/graph_edges.parquet (u, v, length_m, road_class, is_link)
Edges are split at every Overture connector. One-way restrictions are respected.
"""
import os
import numpy as np
import pandas as pd
import shapely
from shapely.ops import substring
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVABLE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
            "residential", "living_street", "service", "unknown"}
to_tm2 = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)

seg = pd.read_parquet(f"{ROOT}/data/cache/segments.parquet")
seg = seg[seg["class"].isin(DRIVABLE)]


def heading_denied(restrictions):
    """Return (forward_ok, backward_ok) for motor vehicles."""
    fwd = bwd = True
    if restrictions is None:
        return fwd, bwd
    for a in restrictions:
        if a["access_type"] != "denied" or a.get("between") is not None:
            continue
        w = a.get("when") or {}
        mode = w.get("mode")
        if mode is not None and not any(m in ("motor_vehicle", "car", "vehicle") for m in mode):
            continue
        heading = w.get("heading")
        if heading == "backward":
            bwd = False
        elif heading == "forward":
            fwd = False
        elif mode is not None:  # e.g. motor_vehicle denied entirely (pedestrian street)
            fwd = bwd = False
    return fwd, bwd


def link_fraction(flags):
    if flags is None:
        return 0.0
    return sum(f["between"][1] - f["between"][0] if f.get("between") is not None else 1.0
               for f in flags if "is_link" in f["values"])


nodes = {}
edges = []
for row in seg.itertuples(index=False):
    fwd, bwd = heading_denied(row.access_restrictions)
    if not (fwd or bwd) or row.connectors is None or len(row.connectors) < 2:
        continue
    geom = shapely.from_wkb(row.wkb)
    xs, ys = to_tm2.transform(*np.asarray(geom.coords).T)
    line = shapely.LineString(np.column_stack([xs, ys]))
    total = line.length
    is_link = link_fraction(row.road_flags) > 0.5
    cons = sorted(row.connectors, key=lambda c: c["at"])
    for c in cons:
        if c["connector_id"] not in nodes:
            p = line.interpolate(c["at"], normalized=True)
            nodes[c["connector_id"]] = (p.x, p.y)
    for a, b in zip(cons[:-1], cons[1:]):
        length = (b["at"] - a["at"]) * total
        if length <= 0:
            continue
        if fwd:
            edges.append((a["connector_id"], b["connector_id"], length, row[1], is_link))
        if bwd:
            edges.append((b["connector_id"], a["connector_id"], length, row[1], is_link))

E = pd.DataFrame(edges, columns=["u", "v", "length_m", "road_class", "is_link"])
N = pd.DataFrame([(k, x, y) for k, (x, y) in nodes.items()], columns=["node_id", "x", "y"])

# keep the largest strongly connected component so every node is reachable both ways
import networkx as nx
G = nx.DiGraph()
G.add_edges_from(zip(E.u, E.v))
big = max(nx.strongly_connected_components(G), key=len)
E = E[E.u.isin(big) & E.v.isin(big)].reset_index(drop=True)
N = N[N.node_id.isin(big)].reset_index(drop=True)
E.to_parquet(f"{ROOT}/data/cache/graph_edges.parquet")
N.to_parquet(f"{ROOT}/data/cache/graph_nodes.parquet")
print(f"nodes={len(N):,} edges={len(E):,} (largest SCC kept: {len(big):,} of {G.number_of_nodes():,})")
print(E.groupby("road_class").length_m.sum().div(1000).round(0).sort_values(ascending=False).to_dict())

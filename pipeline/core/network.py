"""Walking network from OSM highways + nearest-POI walk minutes via multi-source Dijkstra (scipy).

Topology is rebuilt from way geometries: OSM ways that share a node share an exact coordinate, so identical
(projected) vertices become one graph node. No osmnx / Overpass needed.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy import sparse
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

from . import osm
from .common import log
from .osm import col

WALK_M_PER_MIN = 4800 / 60  # 4.8 km/h (README §5)
NO_WALK = {"motorway", "motorway_link", "trunk_link", "construction", "proposed", "raceway", "bus_guideway",
           "abandoned", "platform", "elevator", "corridor", "rest_area", "services", "escape"}
STREET = {"primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
          "residential", "living_street", "pedestrian", "trunk"}
MAJOR = {"motorway", "trunk", "primary", "motorway_link", "trunk_link"}


class WalkGraph:
    def __init__(self, city: str, crs: str):
        self.crs = crs
        hw = osm.export(city, "highways", ["w/highway"], geom_types="linestring")
        hw = hw[hw.geometry.notna() & hw.geom_type.isin(["LineString", "MultiLineString"])].to_crs(crs)
        self.ways = hw  # all highways (also used for cycle / lit / major-road indicators)
        highway = col(hw, "highway").fillna("")
        foot, access = col(hw, "foot").fillna(""), col(hw, "access").fillna("")
        walk = ~highway.isin(NO_WALK) & ~foot.eq("no") & ~(access.isin(["private", "no"]) & ~foot.isin(["yes", "designated"]))
        w = hw[walk.to_numpy()]
        coords, idx = shapely.get_coordinates(w.geometry.to_numpy(), return_index=True)
        key = np.round(coords * 100).astype(np.int64)  # cm grid; identical OSM nodes map to one key
        uniq, node = np.unique(key[:, 0] * 10_000_000_000 + key[:, 1], return_inverse=True)
        same = idx[1:] == idx[:-1]
        u, v = node[:-1][same], node[1:][same]
        d = np.hypot(*(coords[1:][same] - coords[:-1][same]).T)
        keep = u != v
        u, v, d = u[keep], v[keep], d[keep]
        n = len(uniq)
        self.xy = np.zeros((n, 2))
        self.xy[node] = coords
        g = sparse.coo_matrix((np.r_[d, d], (np.r_[u, v], np.r_[v, u])), shape=(n, n)).tocsr()
        g.sum_duplicates()
        _, lab = connected_components(g, directed=False)
        big = np.bincount(lab).argmax()
        self.main = np.flatnonzero(lab == big)
        self.g = g
        self.tree = cKDTree(self.xy[self.main])
        log.info("walk graph: %d nodes, %d edges, main component %d nodes", n, g.nnz // 2, len(self.main))

    def snap(self, xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        dist, i = self.tree.query(xy)
        return self.main[i], dist

    def minutes_to_nearest(self, src_xy: np.ndarray, dst_xy: np.ndarray, cap_min: float = 60) -> np.ndarray:
        """Walk minutes from each src point to the nearest dst point (network + snap distances), capped."""
        n = self.g.shape[0]
        if len(dst_xy) == 0:
            return np.full(len(src_xy), np.nan)
        dn, dd = self.snap(dst_xy)
        # virtual super-source connected to every destination node with weight = its snap distance
        order = np.argsort(dd)
        dn, dd = dn[order], dd[order]
        first = np.unique(dn, return_index=True)[1]
        dn, dd = dn[first], dd[first] + 1e-3
        extra = sparse.coo_matrix((dd, (np.full(len(dn), n), dn)), shape=(n + 1, n + 1))
        big = sparse.bmat([[self.g, None], [None, sparse.csr_matrix((1, 1))]]).tocsr() + extra.tocsr()
        limit = cap_min * WALK_M_PER_MIN
        dist = dijkstra(big, directed=True, indices=n, limit=limit)
        sn, sd = self.snap(src_xy)
        m = (dist[sn] + sd) / WALK_M_PER_MIN
        return np.minimum(np.where(np.isfinite(m), m, cap_min), cap_min)


def lengths_within(points_xy: np.ndarray, seg_mid: np.ndarray, seg_len: np.ndarray, radius: float) -> np.ndarray:
    """Sum of segment lengths whose midpoint lies within radius of each point (metres)."""
    if len(seg_mid) == 0:
        return np.zeros(len(points_xy))
    tree = cKDTree(seg_mid)
    out = np.zeros(len(points_xy))
    for i, nb in enumerate(tree.query_ball_point(points_xy, radius)):
        if nb:
            out[i] = seg_len[nb].sum()
    return out


def segments(gdf: gpd.GeoDataFrame, max_len: float = 50.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split lines into ≤max_len pieces → (midpoints, lengths, row index)."""
    if gdf.empty:
        return np.zeros((0, 2)), np.zeros(0), np.zeros(0, dtype=int)
    geoms = shapely.segmentize(gdf.geometry.to_numpy(), max_len)
    coords, idx = shapely.get_coordinates(geoms, return_index=True)
    same = idx[1:] == idx[:-1]
    a, b = coords[:-1][same], coords[1:][same]
    return (a + b) / 2, np.hypot(*(b - a).T), idx[:-1][same]


def count_within(points_xy: np.ndarray, targets_xy: np.ndarray, radius: float) -> np.ndarray:
    if len(targets_xy) == 0:
        return np.zeros(len(points_xy), dtype=np.int32)
    tree = cKDTree(targets_xy)
    return np.array([len(x) for x in tree.query_ball_point(points_xy, radius)], dtype=np.int32)


def to_xy(df: pd.DataFrame, crs: str) -> np.ndarray:
    g = gpd.GeoSeries(gpd.points_from_xy(df["lon"], df["lat"]), crs=4326).to_crs(crs)
    return np.c_[g.x.to_numpy(), g.y.to_numpy()]

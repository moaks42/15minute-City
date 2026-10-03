"""H3 res-9 grid over the city boundary, habitable mask, population proxy and admin labels."""
from __future__ import annotations

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, mapping

from .common import log


def cell_polygon(c: str) -> Polygon:
    return Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)])


def build(boundary: gpd.GeoDataFrame, res: int = 9) -> gpd.GeoDataFrame:
    geom = boundary.to_crs(4326).union_all()
    cells = sorted(h3.geo_to_cells(mapping(geom), res))
    lat, lng = np.array([h3.cell_to_latlng(c) for c in cells]).T
    g = gpd.GeoDataFrame({"h3": cells, "lat": lat, "lon": lng},
                         geometry=[cell_polygon(c) for c in cells], crs=4326)
    log.info("grid res %d: %d cells", res, len(g))
    return g


def centroids_xy(grid: pd.DataFrame, crs: str) -> np.ndarray:
    p = gpd.GeoSeries(gpd.points_from_xy(grid["lon"], grid["lat"]), crs=4326).to_crs(crs)
    return np.c_[p.x.to_numpy(), p.y.to_numpy()]


def count_points(grid: pd.DataFrame, pts: gpd.GeoDataFrame, res: int = 9) -> np.ndarray:
    p = pts.to_crs(4326)
    cells = pd.Series([h3.latlng_to_cell(y, x, res) for x, y in zip(p.geometry.x, p.geometry.y)])
    vc = cells.value_counts()
    return grid["h3"].map(vc).fillna(0).astype(np.int32).to_numpy()


def label(grid: gpd.GeoDataFrame, polys: gpd.GeoDataFrame, id_col: str, name_col: str) -> pd.DataFrame:
    """Assign each cell the polygon containing its centroid (nearest polygon if outside all)."""
    pts = gpd.GeoDataFrame(grid[["h3"]], geometry=gpd.points_from_xy(grid["lon"], grid["lat"]), crs=4326)
    polys = polys.to_crs(4326)[[id_col, name_col, "geometry"]]
    j = gpd.sjoin(pts, polys, how="left", predicate="within").drop_duplicates("h3")
    miss = j[id_col].isna()
    if miss.any():
        m = 3857
        nn = gpd.sjoin_nearest(pts[miss.to_numpy()].to_crs(m), polys.to_crs(m), how="left").drop_duplicates("h3")
        j.loc[miss, [id_col, name_col]] = nn[[id_col, name_col]].to_numpy()
    j = j.set_index("h3").reindex(grid["h3"])
    return j[[id_col, name_col]].reset_index(drop=True)

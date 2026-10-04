"""City-agnostic core indicators (OSM + GTFS) → columns named `<criterion>.<indicator>` (config/indicators.yaml).

Units follow contracts/DATA_CONTRACT.md: walk minutes capped at 60, shares in percent 0–100, areas in ha.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy import sparse
from scipy.spatial import cKDTree

from . import osm, slope
from .common import log
from .context import Ctx
from .network import MAJOR, STREET, count_within, lengths_within, segments, to_xy
from .osm import col
from .raster import Canvas

DISK_1KM_HA = np.pi * 100.0  # area of a 1 km radius disk in ha (≈ 314.16)

# walk-minute indicators: column -> POI categories (nearest of any)
WALK = {
    "transit.stop_walk_min": ["transit_stop"],
    "transit.tram_stop_walk_min": ["tram_stop"],
    "transit.rail_station_walk_min": ["metro_station", "rail_station"],
    "poi.metro_station_walk_min": ["metro_station"],
    "active.car_free_walk_min": ["car_free"],
    "active.bikeshare_walk_min": ["bikeshare_station"],
    "green.park_walk_min": ["park_2ha"],
    "education.nursery_walk_min": ["nursery"],
    "education.kindergarten_walk_min": ["kindergarten"],
    "education.primary_school_walk_min": ["primary_school"],
    "education.secondary_school_walk_min": ["secondary_school"],
    "education.university_walk_min": ["university"],
    "education.library_walk_min": ["library"],
    "family.paediatrician_walk_min": ["paediatrician"],
    "family.kids_sports_walk_min": ["kids_sports"],
    "price.discount_grocery_walk_min": ["discount_grocery"],
    "shops.supermarket_walk_min": ["supermarket"],
    "shops.post_parcel_walk_min": ["post_office", "parcel_locker"],
    "shops.bakery_walk_min": ["bakery"],
    "shops.marketplace_walk_min": ["marketplace"],
    "shops.atm_walk_min": ["atm"],
    "health.gp_walk_min": ["gp_clinic"],
    "health.pharmacy_walk_min": ["pharmacy"],
    "health.hospital_er_walk_min": ["hospital_er"],
    "health.maternity_walk_min": ["maternity_ward"],
    "health.dentist_walk_min": ["dentist"],
    "health.gynaecology_walk_min": ["gynaecology", "maternity_ward"],
    "leisure.culture_walk_min": ["culture"],
    "leisure.sports_walk_min": ["sports", "kids_sports"],
}
# counts within a euclidean radius (m); 800 m ≈ a 10-minute walk on the network
COUNT = {
    "family.playgrounds_500m": (["playground"], 500),
    "shops.shops_10min": (["shop"], 800),
    "leisure.food_10min": (["restaurant", "cafe"], 800),
    "leisure.nightlife_10min": (["bar", "nightclub"], 800),
    "active.bike_racks_300m": (["bike_rack"], 300),
    "accessibility.benches_300m": (["bench"], 300),
}
LANDUSE_FILTERS = ["nwr/leisure=park,garden,nature_reserve,recreation_ground,dog_park",
                   "nwr/landuse=forest,grass,meadow,recreation_ground,village_green,allotments,cemetery,orchard",
                   "nwr/natural=wood,scrub,grassland,heath,wetland,water", "nwr/landuse=industrial",
                   "nwr/waterway=riverbank"]


def distinct_within(nb: list[list[int]], stop_items: np.ndarray) -> np.ndarray:
    """Number of distinct items (trip ids) over the stops within reach of each point: a tram that serves three
    platforms within 500 m is one departure, not three. (cells × stops) @ (stops × trips) → non-zeros per row."""
    vocab: dict[str, int] = {}
    rows, cols = [], []
    for s, items in enumerate(stop_items):
        for it in items:
            rows.append(s)
            cols.append(vocab.setdefault(it, len(vocab)))
    A = sparse.csr_matrix((np.ones(len(rows), np.int32), (rows, cols)), shape=(len(stop_items), max(len(vocab), 1)))
    r = [i for i, n in enumerate(nb) for _ in n]
    c = [j for n in nb for j in n]
    B = sparse.csr_matrix((np.ones(len(r), np.int32), (r, c)), shape=(len(nb), len(stop_items)))
    return np.diff((B @ A).indptr).astype(float)


def landuse(ctx: Ctx) -> gpd.GeoDataFrame:
    g = osm.export(ctx.city, "landuse", LANDUSE_FILTERS, geom_types="polygon")
    return g[g.geometry.notna()].to_crs(ctx.crs)


def park_access_points(parks: gpd.GeoDataFrame, min_ha: float = 2.0, step: float = 50.0) -> np.ndarray:
    """Points every `step` m along the outline of parks ≥ min_ha (entrances approximated by the edge)."""
    big = parks[parks.area >= min_ha * 10_000]
    if big.empty:
        return np.zeros((0, 2))
    return shapely.get_coordinates(shapely.segmentize(big.geometry.boundary.to_numpy(), step))


def car_free_points(ways: gpd.GeoDataFrame, water: gpd.GeoDataFrame) -> np.ndarray:
    """Pedestrian zones (highway=pedestrian) + footpaths along rivers (embankments, ≤ 60 m from river water)."""
    hw = col(ways, "highway").fillna("")
    ped = ways[hw.eq("pedestrian").to_numpy()]
    mid_p, _, _ = segments(ped, 50)
    paths = ways[hw.isin(["footway", "path", "cycleway", "pedestrian"]).to_numpy()]
    mid, _, _ = segments(paths, 50)
    if len(water) and len(mid):
        tree = shapely.STRtree(water.geometry.buffer(60).to_numpy())
        hit = np.unique(tree.query(shapely.points(mid), predicate="intersects")[0])
        mid = mid[hit]
    else:
        mid = np.zeros((0, 2))
    return np.vstack([mid_p, mid]) if len(mid_p) or len(mid) else np.zeros((0, 2))


def compute(ctx: Ctx, parks_extra: gpd.GeoDataFrame | None = None, walk_overrides: dict | None = None) -> pd.DataFrame:
    xy, pois, graph = ctx.xy, ctx.pois, ctx.graph
    out = pd.DataFrame(index=ctx.grid["h3"])
    pxy = to_xy(pois, ctx.crs)
    cats = pois["category"].to_numpy()

    # ---- green, water & land use ------------------------------------------------------------
    lu = landuse(ctx)
    leisure, land, natural = (col(lu, k).fillna("") for k in ("leisure", "landuse", "natural"))
    water_t, waterway = col(lu, "water").fillna(""), col(lu, "waterway").fillna("")
    green = lu[(leisure.ne("") | land.isin(["forest", "grass", "meadow", "recreation_ground", "village_green",
                                             "allotments", "cemetery", "orchard"])
                | (natural.ne("") & natural.ne("water"))).to_numpy()]
    forest = lu[(land.isin(["forest", "meadow"]) | natural.isin(["wood", "scrub", "grassland", "heath", "wetland"])
                 | leisure.eq("nature_reserve")).to_numpy()]
    industrial = lu[land.eq("industrial").to_numpy()]
    river = lu[((natural.eq("water") & water_t.isin(["river", "canal", "oxbow"])) | waterway.eq("riverbank")).to_numpy()]
    parks = lu[leisure.isin(["park", "nature_reserve", "recreation_ground"]).to_numpy()]
    parks = parks[parks.geometry.geom_type.isin(["Polygon", "MultiPolygon"])][["geometry"]]
    if parks_extra is not None and not parks_extra.empty:
        parks = pd.concat([parks, parks_extra.to_crs(ctx.crs)[["geometry"]]], ignore_index=True)
    cv = Canvas(xy, margin=1500, res=20)
    out["green.green_share_500m"] = (100 * cv.mean_within(cv.burn(green), xy, 500)).round(2)
    out["green.forest_meadow_ha_1km"] = (DISK_1KM_HA * cv.mean_within(cv.burn(forest), xy, 1000)).round(2)
    out["environment.industrial_ha_1km"] = (DISK_1KM_HA * cv.mean_within(cv.burn(industrial), xy, 1000)).round(2)

    special = {"park_2ha": park_access_points(gpd.GeoDataFrame(geometry=parks.geometry.buffer(0), crs=ctx.crs)),
               "car_free": car_free_points(graph.ways, river)}

    # ---- walk minutes -----------------------------------------------------------------------
    for colname, cs in {**WALK, **(walk_overrides or {})}.items():
        dst = np.vstack([special[c] if c in special else pxy[cats == c] for c in cs])
        if len(dst) == 0:
            out[colname] = np.nan
            log.warning("[%s] %s: no POIs (%s) → NaN", ctx.city, colname, cs)
            continue
        out[colname] = graph.minutes_to_nearest(xy, dst).round(1)

    for colname, (cs, r) in COUNT.items():
        out[colname] = count_within(xy, pxy[np.isin(cats, cs)], r).astype(float)

    # ---- street network indicators ----------------------------------------------------------
    ways = graph.ways
    hw = col(ways, "highway").fillna("")
    cyc = col(ways, "cycleway").fillna("") + col(ways, "cycleway:left").fillna("") \
        + col(ways, "cycleway:right").fillna("") + col(ways, "cycleway:both").fillna("")
    bike = hw.eq("cycleway") | cyc.str.contains("lane|track") \
        | (hw.isin(["path", "footway", "track"]) & col(ways, "bicycle").fillna("").eq("designated"))
    mid, ln, _ = segments(ways[bike.to_numpy()])
    out["active.cycleway_km_1km"] = (lengths_within(xy, mid, ln, 1000) / 1000).round(2)

    streets = ways[hw.isin(STREET).to_numpy()]
    mid, ln, ri = segments(streets)
    lit = col(streets, "lit").fillna("").isin(["yes", "24/7", "automatic", "limited"]).to_numpy()[ri]
    tot = lengths_within(xy, mid, ln, 500)
    litlen = lengths_within(xy, mid[lit], ln[lit], 500)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["safety.lit_share"] = np.where(tot > 0, 100 * litlen / tot, np.nan).round(1)

    # intersections: street vertices shared by ≥3 street-segment ends
    c, idx = shapely.get_coordinates(streets.geometry.to_numpy(), return_index=True)
    key = np.round(c * 100).astype(np.int64)
    k = key[:, 0] * 10_000_000_000 + key[:, 1]
    ends = np.r_[True, idx[1:] != idx[:-1]] | np.r_[idx[1:] != idx[:-1], True]
    deg = pd.Series(np.where(ends, 1, 2)).groupby(k).sum()
    first = pd.Series(np.arange(len(k))).groupby(k).first()
    inter = c[first[deg[deg >= 3].index].to_numpy()]
    out["active.intersection_density"] = (count_within(xy, inter, 500) / (np.pi * 0.25)).round(1)

    major = ways[hw.isin(MAJOR).to_numpy()]
    mid, _, _ = segments(major, 20)
    out["environment.major_road_m"] = cKDTree(mid).query(xy)[0].round(0) if len(mid) else np.nan

    # ---- GTFS --------------------------------------------------------------------------------
    st = ctx.stops
    sxy = to_xy(st, ctx.crs)
    nb = cKDTree(sxy).query_ball_point(xy, 500)
    dep = st["dep_peak_per_h"].to_numpy()
    depwc = st["dep_peak_wc_per_h"].to_numpy()
    night = st["dep_night"].to_numpy()
    routes = st["routes"].to_numpy()
    wcb = st["wheelchair_boarding"].astype(str).to_numpy()
    has_wcb = np.isin(wcb, ["1", "2"]).any()
    has_wct = depwc.sum() > 0
    a_dep, a_lines, a_night, a_wcs, a_wct = (np.zeros(len(xy)) for _ in range(5))
    for i, n in enumerate(nb):
        if not n:
            a_wcs[i] = a_wct[i] = np.nan
            continue
        a_dep[i] = dep[n].sum()
        a_lines[i] = len(set().union(*routes[n]))
        a_night[i] = night[n].sum()
        a_wcs[i] = 100 * (wcb[n] == "1").mean() if has_wcb else np.nan
        a_wct[i] = 100 * depwc[n].sum() / dep[n].sum() if has_wct and dep[n].sum() > 0 else np.nan
    if {"peak_trips", "night_trips"} <= set(st.columns):  # distinct vehicles, not the sum over every nearby stop
        a_dep = distinct_within(nb, st["peak_trips"].to_numpy()) / 2.0
        a_night = distinct_within(nb, st["night_trips"].to_numpy())
    out["transit.departures_per_h_500m"] = a_dep.round(1)
    out["transit.lines_500m"] = a_lines
    out["transit.night_departures_500m"] = a_night
    out["accessibility.accessible_stop_share"] = np.round(a_wcs, 1)
    out["accessibility.lowfloor_trip_share"] = np.round(a_wct, 1)
    try:
        out["accessibility.slope_pct"] = slope.compute(ctx)
    except Exception as ex:  # noqa: BLE001 — P2 indicator; never block the build
        log.warning("[%s] slope_pct failed: %s → NaN", ctx.city, ex)
        ctx.man.record("copernicus_dem", status="missing", note=f"DEM failed: {str(ex)[:200]}")
        out["accessibility.slope_pct"] = np.nan
    if not has_wcb:
        log.warning("[%s] GTFS has no wheelchair_boarding info → accessible_stop_share NaN", ctx.city)
    if not has_wct:
        log.warning("[%s] GTFS has no wheelchair_accessible trips → lowfloor_trip_share NaN", ctx.city)
    return out.reset_index(drop=True)

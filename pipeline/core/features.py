"""City-agnostic core indicators (OSM + GTFS) → columns named `<criterion>.<indicator>`."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

from . import osm
from .common import log
from .context import Ctx
from .network import MAJOR, STREET, count_within, lengths_within, segments, to_xy
from .osm import col
from .raster import Canvas

# walk-minute indicators: column -> POI categories (nearest of any)
WALK = {
    "transit.stop_walk_min": ["transit_stop"],
    "transit.rail_station_walk_min": ["metro_station", "rail_station"],
    "green.park_walk_min": ["park_2ha"],
    "education.nursery_walk_min": ["nursery"],
    "education.kindergarten_walk_min": ["kindergarten"],
    "education.primary_school_walk_min": ["primary_school"],
    "education.secondary_school_walk_min": ["secondary_school"],
    "education.university_walk_min": ["university"],
    "education.library_walk_min": ["library"],
    "family.paediatrician_walk_min": ["paediatrician"],
    "family.kids_sport_walk_min": ["pool", "sports"],
    "price.discount_grocery_walk_min": ["discount_grocery"],
    "shops.supermarket_walk_min": ["supermarket"],
    "shops.pharmacy_walk_min": ["pharmacy"],
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
    "leisure.sports_walk_min": ["sports", "pool"],
    "active.bike_share_walk_min": ["bike_share"],
}
# counts within euclidean radius (m)
COUNT = {
    "family.playgrounds_500m": (["playground"], 500),
    "shops.shops_800m": (["shop"], 800),
    "leisure.food_800m": (["food"], 800),
    "leisure.nightlife_800m": (["nightlife"], 800),
    "active.bike_racks_300m": (["bicycle_parking"], 300),
    "accessibility.benches_300m": (["bench"], 300),
}
GREEN_FILTERS = ["nwr/leisure=park,garden,nature_reserve,recreation_ground,dog_park",
                 "nwr/landuse=forest,grass,meadow,recreation_ground,village_green,allotments,cemetery,orchard",
                 "nwr/natural=wood,scrub,grassland,heath,wetland", "nwr/landuse=industrial"]


def landuse(ctx: Ctx) -> gpd.GeoDataFrame:
    g = osm.export(ctx.city, "landuse", GREEN_FILTERS, geom_types="polygon")
    return g[g.geometry.notna()].to_crs(ctx.crs)


def park_access_points(parks: gpd.GeoDataFrame, min_ha: float = 2.0, step: float = 50.0) -> pd.DataFrame:
    """Points every `step` m along the outline of parks ≥ min_ha (entrances are approximated by the edge)."""
    big = parks[parks.area >= min_ha * 10_000]
    if big.empty:
        return pd.DataFrame(columns=["x", "y"])
    rings = shapely.segmentize(big.geometry.boundary.to_numpy(), step)
    xy = shapely.get_coordinates(rings)
    return pd.DataFrame({"x": xy[:, 0], "y": xy[:, 1]})


def compute(ctx: Ctx, parks_extra: gpd.GeoDataFrame | None = None, walk_overrides: dict | None = None) -> pd.DataFrame:
    xy, pois, graph = ctx.xy, ctx.pois, ctx.graph
    out = pd.DataFrame(index=ctx.grid["h3"])
    pxy = to_xy(pois, ctx.crs)
    cats = pois["category"].to_numpy()

    # ---- green & land use -------------------------------------------------------------------
    lu = landuse(ctx)
    leisure, land, natural = (col(lu, k).fillna("") for k in ("leisure", "landuse", "natural"))
    green = lu[(leisure.ne("") | land.isin(["forest", "grass", "meadow", "recreation_ground", "village_green",
                                             "allotments", "cemetery", "orchard"]) | natural.ne("")).to_numpy()]
    forest = lu[(land.isin(["forest", "meadow"]) | natural.isin(["wood", "scrub", "grassland", "heath", "wetland"])
                 | leisure.eq("nature_reserve")).to_numpy()]
    industrial = lu[land.eq("industrial").to_numpy()]
    parks = lu[leisure.isin(["park", "garden", "nature_reserve", "recreation_ground"]).to_numpy()]
    parks = parks[parks.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    if parks_extra is not None and not parks_extra.empty:
        parks = pd.concat([parks[["geometry"]], parks_extra.to_crs(ctx.crs)[["geometry"]]], ignore_index=True)
    # garden polygons are often private: only public ones count as parks
    cv = Canvas(xy, margin=1500, res=20)
    out["green.green_share_500m"] = cv.mean_within(cv.burn(green), xy, 500).round(4)
    out["green.forest_share_1km"] = cv.mean_within(cv.burn(forest), xy, 1000).round(4)
    out["environment.industrial_share_1km"] = cv.mean_within(cv.burn(industrial), xy, 1000).round(4)

    # park ≥ 2 ha access points become a pseudo-POI category
    acc = park_access_points(parks.set_geometry(parks.geometry.buffer(0)))
    park_xy = acc[["x", "y"]].to_numpy()

    # ---- walk minutes -----------------------------------------------------------------------
    for colname, cs in {**WALK, **(walk_overrides or {})}.items():
        if cs == ["park_2ha"]:
            dst = park_xy
        else:
            dst = pxy[np.isin(cats, cs)]
        if len(dst) == 0:
            out[colname] = np.nan
            log.warning("[%s] %s: no POIs (%s) → NaN", ctx.city, colname, cs)
            continue
        out[colname] = graph.minutes_to_nearest(xy, dst).round(1)

    for colname, (cs, r) in COUNT.items():
        dst = pxy[np.isin(cats, cs)]
        out[colname] = count_within(xy, dst, r)

    # ---- street network indicators ----------------------------------------------------------
    ways = graph.ways
    hw = col(ways, "highway").fillna("")
    cyc = col(ways, "cycleway").fillna("") + col(ways, "cycleway:left").fillna("") \
        + col(ways, "cycleway:right").fillna("") + col(ways, "cycleway:both").fillna("")
    bike = hw.eq("cycleway") | cyc.str.contains("lane|track") \
        | (hw.isin(["path", "footway", "track"]) & col(ways, "bicycle").fillna("").eq("designated"))
    mid, ln, _ = segments(ways[bike.to_numpy()])
    out["active.cycle_km_1km"] = (lengths_within(xy, mid, ln, 1000) / 1000).round(2)
    carfree = hw.isin(["pedestrian", "footway", "path", "living_street", "steps"])
    mid, ln, _ = segments(ways[carfree.to_numpy()])
    out["active.car_free_km_500m"] = (lengths_within(xy, mid, ln, 500) / 1000).round(2)

    streets = ways[hw.isin(STREET).to_numpy()]
    mid, ln, ri = segments(streets)
    lit = col(streets, "lit").fillna("").isin(["yes", "24/7", "automatic", "limited"]).to_numpy()[ri]
    tot = lengths_within(xy, mid, ln, 300)
    litlen = lengths_within(xy, mid[lit], ln[lit], 300)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["safety.lit_share_300m"] = np.where(tot > 0, litlen / tot, np.nan).round(3)

    # intersections: street vertices shared by ≥3 street segments
    c, idx = shapely.get_coordinates(streets.geometry.to_numpy(), return_index=True)
    key = np.round(c * 100).astype(np.int64)
    k = key[:, 0] * 10_000_000_000 + key[:, 1]
    ends = np.r_[True, idx[1:] != idx[:-1]] | np.r_[idx[1:] != idx[:-1], True]
    deg = pd.Series(np.where(ends, 1, 2)).groupby(k).sum()
    ux = pd.Series(np.arange(len(k))).groupby(k).first()
    inter = c[ux[deg[deg >= 3].index].to_numpy()]
    out["active.intersections_km2_500m"] = (count_within(xy, inter, 500) / (np.pi * 0.25)).round(1)

    major = ways[hw.isin(MAJOR).to_numpy()]
    mid, _, _ = segments(major, 20)
    out["environment.major_road_dist_m"] = cKDTree(mid).query(xy)[0].round(0) if len(mid) else np.nan

    # ---- GTFS --------------------------------------------------------------------------------
    st = ctx.stops
    sxy = to_xy(st, ctx.crs)
    tree = cKDTree(sxy)
    nb = tree.query_ball_point(xy, 500)
    dep = st["dep_peak_per_h"].to_numpy()
    depwc = st["dep_peak_wc_per_h"].to_numpy()
    night = st["dep_night"].to_numpy()
    routes = st["routes"].to_numpy()
    tram = st["modes"].apply(lambda m: "tram" in m).to_numpy()
    wcb = st["wheelchair_boarding"].astype(str).to_numpy()
    has_wcb = np.isin(wcb, ["1", "2"]).any()
    has_wct = depwc.sum() > 0
    a_dep, a_lines, a_tram, a_night, a_wcs, a_wct = (np.zeros(len(xy)) for _ in range(6))
    for i, n in enumerate(nb):
        if not n:
            a_wcs[i] = a_wct[i] = np.nan
            continue
        a_dep[i] = dep[n].sum()
        a_lines[i] = len(set().union(*routes[n]))
        a_tram[i] = float(tram[n].any())
        a_night[i] = night[n].sum()
        a_wcs[i] = (wcb[n] == "1").mean() if has_wcb else np.nan
        a_wct[i] = depwc[n].sum() / dep[n].sum() if has_wct and dep[n].sum() > 0 else np.nan
    out["transit.departures_per_h_500m"] = a_dep.round(1)
    out["transit.lines_500m"] = a_lines.astype(int)
    out["transit.tram_stop_500m"] = a_tram.astype(int)
    out["transit.night_departures_500m"] = a_night.astype(int)
    out["accessibility.wheelchair_stops_share_500m"] = np.round(a_wcs, 3)
    out["accessibility.wheelchair_trips_share_500m"] = np.round(a_wct, 3)
    if not has_wcb:
        log.warning("[%s] GTFS has no wheelchair_boarding info → NaN", ctx.city)
    if not has_wct:
        log.warning("[%s] GTFS has no wheelchair_accessible trips → NaN", ctx.city)
    return out.reset_index(drop=True)

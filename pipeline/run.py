"""Build data/processed/{city}/ from data/raw/{city}/ (README §5).

    uv run python run.py --city krakow [--steps grid,pois,features,adapters,write] [--force-osm]
"""
from __future__ import annotations

import argparse
import importlib
import json
import time

import geopandas as gpd
import numpy as np
import pandas as pd

from core import features as core_features
from core import grid as core_grid
from core import gtfs, osm, pois as core_pois
from core.common import interim_dir, log, now_iso, out_dir
from core.context import Ctx
from core.network import WalkGraph

FEATURE_ORDER = ["commute", "transit", "active", "green", "education", "family", "safety", "price", "shops",
                 "health", "environment", "leisure", "accessibility"]


def neighborhoods_from_places(ctx: Ctx) -> tuple[pd.Series, pd.Series]:
    """Nearest OSM place=suburb|quarter|neighbourhood node → (id, name) per cell."""
    pl = osm.export(ctx.city, "places", ["n/place=suburb,quarter,neighbourhood"], geom_types="point")
    pl = pl[col_ok(pl, "name")].to_crs(ctx.crs)
    from scipy.spatial import cKDTree
    t = cKDTree(np.c_[pl.geometry.x, pl.geometry.y])
    _, i = t.query(ctx.xy)
    names = pl["name"].to_numpy()[i]
    ids = pl["osm_id"].astype(str).to_numpy()[i]
    return pd.Series(ids), pd.Series(names)


def col_ok(g, c):
    return g[c].notna() if c in g.columns else np.zeros(len(g), bool)


def gtfs_stops(ctx: Ctx) -> pd.DataFrame:
    cache = interim_dir(ctx.city) / "stops.parquet"
    paths = [ctx.raw / f for f in ctx.s["gtfs"]]
    day = gtfs.pick_date(paths)
    ctx.service_date = day
    if cache.exists():
        st = pd.read_parquet(cache)
        if st.attrs.get("day", day) == day and "day" in st.columns and st["day"].iloc[0] == day:
            return st
    st = gtfs.stop_stats(paths, day)
    st["day"] = day
    st.to_parquet(cache)
    return st


def stop_pois(st: pd.DataFrame) -> pd.DataFrame:
    s = st[st["departures_day"] > 0]
    rows = []
    for cat, m in [("transit_stop", np.ones(len(s), bool)),
                   ("tram_stop", s["modes"].apply(lambda x: "tram" in x).to_numpy()),
                   ("bus_stop", s["modes"].apply(lambda x: "bus" in x).to_numpy()),
                   ("metro_station", s["modes"].apply(lambda x: "metro" in x).to_numpy()),
                   ("rail_station", s["modes"].apply(lambda x: "rail" in x).to_numpy())]:
        sub = s[m]
        rows.append(pd.DataFrame({"category": cat, "name": sub["stop_name"].to_numpy(), "lat": sub["lat"].to_numpy(),
                                  "lon": sub["lon"].to_numpy(), "source": "gtfs:" + sub["feed"].to_numpy(),
                                  "extra_json": [json.dumps({"stop_id": a, "dep_peak_per_h": float(b)})
                                                 for a, b in zip(sub["stop_id"], sub["dep_peak_per_h"])]}))
    return pd.concat(rows, ignore_index=True)


def build(city: str, force_osm: bool = False) -> None:
    t0 = time.time()
    ctx = Ctx.make(city)
    ad = importlib.import_module(f"adapters.{city}")

    # ---- admin, boundary, grid -----------------------------------------------------------------
    districts = ad.districts(ctx)
    ctx.districts = districts
    ctx.boundary = gpd.GeoDataFrame(geometry=[districts.union_all()], crs=4326)
    g = core_grid.build(ctx.boundary, ctx.s["h3Res"])
    ctx.grid = g
    ctx.xy = core_grid.centroids_xy(g, ctx.crs)
    lab = core_grid.label(g, districts, "district_id", "district_name")
    g["district_id"], g["district_name"] = lab["district_id"].to_numpy(), lab["district_name"].to_numpy()

    addr = ad.addresses(ctx)
    ctx.addresses = addr
    g["population_est"] = core_grid.count_points(g, addr, ctx.s["h3Res"])
    g["habitable"] = g["population_est"] >= int(ctx.s["habitableMinAddresses"])
    log.info("[%s] habitable %d / %d cells", city, g["habitable"].sum(), len(g))

    osm.clip(city, ctx.boundary, force=force_osm)
    nb = ad.neighborhoods(ctx) if hasattr(ad, "neighborhoods") else None
    if nb is None:
        nid, nname = neighborhoods_from_places(ctx)
        g["neighborhood_id"], g["neighborhood"] = nid.to_numpy(), nname.to_numpy()
        nb_polys = None
    else:
        lab = core_grid.label(g, nb, "neighborhood_id", "neighborhood")
        g["neighborhood_id"], g["neighborhood"] = lab["neighborhood_id"].to_numpy(), lab["neighborhood"].to_numpy()
        nb_polys = nb
    ctx.man.record(f"osm_{city}", rows=None, status="ok", note=f"clipped to city + {ctx.s['routingBufferKm']} km")

    # ---- POIs + transit ------------------------------------------------------------------------
    st = gtfs_stops(ctx)
    log.info("[%s] GTFS service date %s, %d stops with service", city, ctx.service_date, (st['departures_day'] > 0).sum())
    ctx.stops = st[st["departures_day"] > 0].reset_index(drop=True)
    for key in [k for k in (x["key"] for x in ctx.s["sources"]) if k.startswith("gtfs_") and "rt" not in k
                and "stops" not in k]:
        ctx.man.record(key, rows=int(len(ctx.stops)), status="ok",
                       note=f"weekday service date {ctx.service_date}; stop-level stats 07–09 & 23–05")
    p = [core_pois.from_osm(city), stop_pois(st)]
    extra = ad.extra_pois(ctx) if hasattr(ad, "extra_pois") else None
    if extra is not None and len(extra):
        replace = set(extra.attrs.get("replace", []))
        if replace:  # adapter is authoritative for these categories (e.g. registers instead of OSM)
            p[0] = p[0][~p[0]["category"].isin(replace)]
        p.append(extra)
    pois = core_pois.finalize(pd.concat(p, ignore_index=True), ctx.s["h3Res"])
    ctx.pois = pois
    log.info("[%s] POIs: %s", city, pois["category"].value_counts().to_dict())

    # ---- features ------------------------------------------------------------------------------
    ctx.graph = WalkGraph(city, ctx.crs)
    parks_extra = ad.parks(ctx) if hasattr(ad, "parks") else None
    feats = core_features.compute(ctx, parks_extra, getattr(ad, "WALK_OVERRIDES", None))
    if hasattr(ad, "features"):
        af = ad.features(ctx)
        for c in af.columns:
            feats[c] = af[c].to_numpy()
    feats.insert(0, "h3", g["h3"].to_numpy())
    feats = feats[["h3"] + sorted([c for c in feats.columns if c != "h3"],
                                  key=lambda c: (FEATURE_ORDER.index(c.split(".")[0]) if c.split(".")[0] in FEATURE_ORDER else 99, c))]

    # ---- write ---------------------------------------------------------------------------------
    od = out_dir(city)
    grid_out = g[["h3", "district_id", "district_name", "neighborhood_id", "neighborhood", "habitable",
                  "population_est", "geometry"]].copy()
    grid_out["habitable"] = grid_out["habitable"].astype(bool)
    grid_out.to_file(od / "grid.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    feats.to_parquet(od / "features.parquet", index=False)
    pois.to_parquet(od / "pois.parquet", index=False)
    d = districts.copy()
    d = d.merge(g.groupby("district_id").agg(population_est=("population_est", "sum"), cells=("h3", "size")).reset_index(),
                on="district_id", how="left")
    d.to_file(od / "districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    if nb_polys is None:
        nb_polys = g.dissolve(by="neighborhood_id", as_index=False)[["neighborhood_id", "neighborhood", "geometry"]]
    nb_polys.to_file(od / "neighborhoods.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
    ctx.man.data["build"] = {"builtAt": now_iso(), "serviceDate": ctx.service_date, "cells": int(len(g)),
                             "habitable": int(g["habitable"].sum()), "h3Res": ctx.s["h3Res"],
                             "metricCrs": ctx.crs}
    ctx.man.save()
    log.info("[%s] done in %.0fs → %s", city, time.time() - t0, od)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True, choices=["krakow", "praha"])
    ap.add_argument("--force-osm", action="store_true")
    a = ap.parse_args()
    build(a.city, a.force_osm)

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
from core.align import align
from core.network import WalkGraph


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
        if (st.attrs.get("day", day) == day and "day" in st.columns and st["day"].iloc[0] == day
                and {"peak_trips", "night_trips"} <= set(st.columns)):
            return st
    st = gtfs.stop_stats(paths, day)
    st["day"] = day
    st.to_parquet(cache)
    return st


def stop_pois(ctx: Ctx, st: pd.DataFrame) -> pd.DataFrame:
    s = st[st["departures_day"] > 0]
    feed_key = {x["file"].rsplit(".", 1)[0]: x["key"] for x in ctx.s["sources"]}
    rows = []
    for cat, m in [("transit_stop", np.ones(len(s), bool)),
                   ("tram_stop", s["modes"].apply(lambda x: "tram" in x).to_numpy()),
                   ("bus_stop", s["modes"].apply(lambda x: "bus" in x).to_numpy()),
                   ("metro_station", s["modes"].apply(lambda x: "metro" in x).to_numpy()),
                   ("rail_station", s["modes"].apply(lambda x: "rail" in x).to_numpy())]:
        sub = s[m]
        rows.append(pd.DataFrame({"category": cat, "name": sub["stop_name"].to_numpy(), "lat": sub["lat"].to_numpy(),
                                  "lon": sub["lon"].to_numpy(), "source": sub["feed"].map(feed_key).to_numpy(),
                                  "extra_json": [json.dumps({"stop_id": a, "dep_peak_per_h": float(b)})
                                                 for a, b in zip(sub["stop_id"], sub["dep_peak_per_h"])]}))
    return pd.concat(rows, ignore_index=True)


def write(ctx: Ctx, g: gpd.GeoDataFrame, feats: pd.DataFrame, pois: pd.DataFrame, districts: gpd.GeoDataFrame,
          nb_polys: gpd.GeoDataFrame | None) -> None:
    """Write data/processed/{city}/ exactly as contracts/DATA_CONTRACT.md describes."""
    od = out_dir(ctx.city)
    built = now_iso()
    # grid.geojson: numeric feature id = row index (same order as features.parquet)
    feats_json = []
    for i, r in enumerate(g.itertuples(index=False)):
        feats_json.append({"type": "Feature", "id": i, "geometry": {"type": "Polygon", "coordinates": [
            [[round(x, 6), round(y, 6)] for x, y in r.geometry.exterior.coords]]},
            "properties": {"h3": r.h3, "district_id": str(r.district_id), "district_name": str(r.district_name),
                           "neighborhood": None if pd.isna(r.neighborhood) else str(r.neighborhood),
                           "neighborhood_id": None if pd.isna(r.neighborhood_id) else str(r.neighborhood_id),
                           "habitable": bool(r.habitable), "population_est": int(r.population_est)}})
    (od / "grid.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats_json},
                                                ensure_ascii=False, separators=(",", ":")))
    feats.to_parquet(od / "features.parquet", index=False, compression="snappy")
    pois[pois["category"].isin(core_pois.VOCAB)].reset_index(drop=True).to_parquet(
        od / "pois.parquet", index=False, compression="snappy")

    pop = g.groupby("district_id")["population_est"].sum()
    d = districts.rename(columns={"district_id": "id", "district_name": "name"}).copy()
    d["population_est"] = d["id"].map(pop).fillna(0).astype(int)
    d["geometry"] = d.to_crs(ctx.crs).simplify(10).to_crs(4326)
    d.to_file(od / "districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)

    if nb_polys is None:
        nb_polys = g.dissolve(by="neighborhood_id", as_index=False)[["neighborhood_id", "neighborhood", "geometry"]]
    n = nb_polys.rename(columns={"neighborhood_id": "id", "neighborhood": "name"}).copy()
    gg = g.groupby("neighborhood_id")
    n["population_est"] = n["id"].map(gg["population_est"].sum()).fillna(0).astype(int)
    n["district_id"] = n["id"].map(gg["district_id"].agg(lambda s: s.value_counts().index[0]))
    n["geometry"] = n.to_crs(ctx.crs).simplify(10).to_crs(4326)
    n[["id", "name", "district_id", "population_est", "geometry"]].to_file(
        od / "neighborhoods.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)

    # manifest hygiene: drop stale keys, explain verified-but-unused sources, clear stale fetch-failure notes
    keys = {x["key"]: x for x in ctx.s["sources"]}
    derived = {"r5py_travel_times", "copernicus_dem"}
    ctx.man.data["sources"] = [e for e in ctx.man.data["sources"] if e["key"] in keys or e["key"] in derived]
    for e in ctx.man.data["sources"]:
        src = keys.get(e["key"], {})
        if e["status"] == "ok" and (e.get("note") or "").startswith("fetch failed"):
            e["note"] = ""
        if e["status"] == "ok" and e.get("rows") is None and not e.get("note"):
            e["note"] = f"reachable (verified {str(e.get('fetchedAt'))[:10]}); not used for features — {src.get('use', 'reference')}"
        if e["status"] == "missing" and src.get("use"):
            e["note"] = (e.get("note") or "") + f" [{src['use']}]"
    # optional (contracts-v2 §3b): address points for the engine's local geocoder
    from core import geocode
    ad_out = geocode.addresses(ctx.addresses)
    ad_out.to_parquet(od / "addresses.parquet", index=False, compression="snappy")
    log.info("[%s] addresses.parquet: %d rows", ctx.city, len(ad_out))
    (od / "geocode.parquet").unlink(missing_ok=True)
    ctx.man.data["dataVersion"] = built
    ctx.man.data["builtAt"] = built
    ctx.man.data["build"] = {"serviceDate": ctx.service_date, "cells": int(len(g)),
                             "habitable": int(g["habitable"].sum()), "h3Res": ctx.s["h3Res"], "metricCrs": ctx.crs}
    ctx.man.save()


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
    p = [core_pois.from_osm(city), stop_pois(ctx, st)]
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
    for c in ("h3", "lat", "lon", "habitable", "district_id", "district_name", "neighborhood", "population_est"):
        feats[c] = g[c].to_numpy()
    feats = align(city, feats)
    write(ctx, g, feats, pois, districts, nb_polys)
    log.info("[%s] done in %.0fs → %s", city, time.time() - t0, out_dir(city))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True, choices=["krakow", "praha"])
    ap.add_argument("--force-osm", action="store_true")
    a = ap.parse_args()
    build(a.city, a.force_osm)

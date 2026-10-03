"""Commute travel-time matrices with r5py (README §5): habitable res-9 origins × all res-8 destinations.

    JAVA_HOME=... uv run python travel.py --city krakow [--modes transit,bike,walk]

Output data/processed/{city}/travel_times.npz: origins[] (res-9 h3), dests[] (res-8 h3), transit/bike/walk
uint8 minutes (255 = unreachable or > 120). Transit = median over a 30-min window from 08:00 on the service date.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

sys.argv += ["--max-memory", os.environ.get("R5_MAX_MEMORY", "12G")]  # r5py reads JVM options from argv

import geopandas as gpd  # noqa: E402
import h3  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core import gtfs  # noqa: E402
from core.common import Manifest, interim_dir, log, now_iso, out_dir, raw_dir, settings  # noqa: E402

MAX_MIN = 120


def points(cells: list[str]) -> gpd.GeoDataFrame:
    ll = np.array([h3.cell_to_latlng(c) for c in cells])
    return gpd.GeoDataFrame({"id": cells}, geometry=gpd.points_from_xy(ll[:, 1], ll[:, 0]), crs=4326)


def matrix(ttm: pd.DataFrame, origins: list[str], dests: list[str]) -> np.ndarray:
    oi = pd.Index(origins).get_indexer(ttm["from_id"])
    di = pd.Index(dests).get_indexer(ttm["to_id"])
    m = np.full((len(origins), len(dests)), 255, dtype=np.uint8)
    t = ttm["travel_time"].to_numpy(dtype=float)
    ok = np.isfinite(t) & (t <= MAX_MIN)
    m[oi[ok], di[ok]] = np.round(t[ok]).astype(np.uint8)
    return m


def run(city: str, modes: list[str]) -> None:
    import r5py

    s = settings(city)
    od = out_dir(city)
    grid = gpd.read_file(od / "grid.geojson")
    origins = grid.loc[grid["habitable"].astype(bool), "h3"].tolist()
    dests = sorted({h3.cell_to_parent(c, s["destRes"]) for c in grid["h3"]})
    log.info("[%s] r5py: %d origins × %d destinations, modes %s", city, len(origins), len(dests), modes)
    gtfs_paths = [raw_dir(city) / f for f in s["gtfs"]]
    day = gtfs.pick_date(gtfs_paths)
    dep = datetime.strptime(day, "%Y%m%d").replace(hour=8)
    pbf = interim_dir(city) / "clip.osm.pbf"
    t0 = time.time()
    tn = r5py.TransportNetwork(str(pbf), [str(p) for p in gtfs_paths])
    log.info("[%s] transport network built in %.0fs", city, time.time() - t0)
    O, D = points(origins), points(dests)
    npz = od / "travel_times.npz"
    out = dict(np.load(npz, allow_pickle=False)) if npz.exists() else {}
    mode_sets = {"transit": [r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
                 "bike": [r5py.TransportMode.BICYCLE], "walk": [r5py.TransportMode.WALK]}
    for m in modes:
        t0 = time.time()
        kw = dict(departure=dep, transport_modes=mode_sets[m], max_time=timedelta(minutes=MAX_MIN))
        if m == "transit":
            kw["departure_time_window"] = timedelta(minutes=30)
        ttm = r5py.TravelTimeMatrix(tn, origins=O, destinations=D, **kw)
        out[m] = matrix(pd.DataFrame(ttm), origins, dests)
        reach = (out[m] < 255).mean()
        log.info("[%s] %s matrix in %.0fs, reachable %.1f%%, median %s min", city, m, time.time() - t0,
                 100 * reach, np.median(out[m][out[m] < 255]) if reach else None)
    np.savez_compressed(npz, origins=np.array(origins), dests=np.array(dests),
                        **{k: v for k, v in out.items() if k in ("transit", "bike", "walk")},
                        departure=np.array(dep.isoformat()), max_minutes=np.array(MAX_MIN))
    man = Manifest(city)
    man.record("r5py_travel_times", url="https://r5py.readthedocs.io", fetchedAt=now_iso(),
               licence="derived (OSM ODbL + GTFS)", rows=len(origins) * len(dests), status="ok",
               note=f"r5py {r5py.__version__}; {len(origins)} habitable res-9 origins × {len(dests)} res-8 dests; "
                    f"departure {dep.isoformat()} (+30-min window, median) for transit; modes {sorted(out)}; "
                    f"uint8 minutes, 255 = unreachable/>{MAX_MIN}")
    man.save()
    log.info("[%s] wrote %s (%.1f MB)", city, npz, npz.stat().st_size / 1e6)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True, choices=["krakow", "praha"])
    ap.add_argument("--modes", default="transit,bike,walk")
    a, _ = ap.parse_known_args()
    run(a.city, a.modes.split(","))

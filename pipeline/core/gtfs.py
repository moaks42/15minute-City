"""GTFS → per-stop service statistics on one weekday (departures 7–9, night service, lines, modes, wheelchair)."""
from __future__ import annotations

import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .common import log

# GTFS basic + extended route types → mode
def mode_of(rt: int) -> str:
    if rt in (0,) or 900 <= rt < 1000:
        return "tram"
    if rt == 1 or 400 <= rt < 500:
        return "metro"
    if rt == 2 or 100 <= rt < 200:
        return "rail"
    if rt in (3, 11) or 700 <= rt < 900:
        return "bus"
    if rt == 4 or 1000 <= rt < 1100 or rt == 1200:
        return "ferry"
    if rt in (5, 6, 7, 12) or 1300 <= rt < 1500:
        return "cable"
    return "other"


def _read(z: zipfile.ZipFile, name: str, usecols=None, dtype=str) -> pd.DataFrame:
    if name not in z.namelist():
        return pd.DataFrame(columns=usecols or [])
    with z.open(name) as f:
        df = pd.read_csv(f, dtype=dtype, usecols=lambda c: (usecols is None) or (c.strip() in usecols),
                         keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    return df


def service_dates(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as z:
        cal = _read(z, "calendar.txt")
        cd = _read(z, "calendar_dates.txt")
    days: set[str] = set()
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for _, r in cal.iterrows():
        d0 = datetime.strptime(r["start_date"], "%Y%m%d").date()
        d1 = datetime.strptime(r["end_date"], "%Y%m%d").date()
        d = d0
        while d <= d1:
            if r[names[d.weekday()]] == "1":
                days.add(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
    if len(cd):
        days |= set(cd.loc[cd["exception_type"] == "1", "date"])
    return days


def pick_date(paths: list[Path], weekday: int = 1, start: date | None = None) -> str:
    """First Tuesday (default) from tomorrow on that has service in every feed."""
    common = set.intersection(*[service_dates(p) for p in paths])
    d = (start or date.today()) + timedelta(days=1)
    for _ in range(60):
        if d.weekday() == weekday and d.strftime("%Y%m%d") in common:
            return d.strftime("%Y%m%d")
        d += timedelta(days=1)
    # fall back to any weekday in common
    wk = sorted(x for x in common if datetime.strptime(x, "%Y%m%d").weekday() < 5)
    if not wk:
        raise RuntimeError("no common weekday service date across feeds")
    return wk[0]


def _active_services(z: zipfile.ZipFile, day: str) -> set[str]:
    cal = _read(z, "calendar.txt")
    cd = _read(z, "calendar_dates.txt")
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][
        datetime.strptime(day, "%Y%m%d").weekday()]
    act = set()
    if len(cal):
        m = (cal[wd] == "1") & (cal["start_date"] <= day) & (cal["end_date"] >= day)
        act = set(cal.loc[m, "service_id"])
    if len(cd):
        cdd = cd[cd["date"] == day]
        act |= set(cdd.loc[cdd["exception_type"] == "1", "service_id"])
        act -= set(cdd.loc[cdd["exception_type"] == "2", "service_id"])
    return act


def _secs(t: pd.Series) -> np.ndarray:
    p = t.str.strip().str.split(":", expand=True)
    return (p[0].astype(float) * 3600 + p[1].astype(float) * 60 + p[2].astype(float)).to_numpy()


def stop_stats(paths: list[Path], day: str, prefix_ids: bool = True) -> pd.DataFrame:
    """One row per (platform) stop with weekday statistics. Stop ids are prefixed with the feed name."""
    out = []
    for p in paths:
        tag = p.stem
        with zipfile.ZipFile(p) as z:
            stops = _read(z, "stops.txt")
            routes = _read(z, "routes.txt", ["route_id", "route_short_name", "route_type"])
            trips = _read(z, "trips.txt", ["route_id", "service_id", "trip_id", "wheelchair_accessible"])
            act = _active_services(z, day)
            trips = trips[trips["service_id"].isin(act)]
            log.info("[gtfs %s] %s: %d active services, %d trips", tag, day, len(act), len(trips))
            st = _read(z, "stop_times.txt", ["trip_id", "stop_id", "departure_time"])
        st = st[st["trip_id"].isin(set(trips["trip_id"])) & (st["departure_time"] != "")]
        st = st.merge(trips, on="trip_id").merge(routes, on="route_id", how="left")
        st["t"] = _secs(st["departure_time"])
        st["mode"] = st["route_type"].fillna("3").astype(int).map(mode_of)
        st["wc"] = st.get("wheelchair_accessible", pd.Series("", index=st.index)).eq("1")
        peak = st[(st["t"] >= 7 * 3600) & (st["t"] < 9 * 3600)]
        hm = st["t"] % (24 * 3600)
        night = st[(hm >= 23 * 3600) | (hm < 5 * 3600)]
        g = st.groupby("stop_id")
        df = pd.DataFrame({
            "departures_day": g.size(),
            "lines": g["route_id"].nunique(),
            "routes": g["route_id"].agg(lambda s: sorted(set(s))),
            "modes": g["mode"].agg(lambda s: sorted(set(s))),
        })
        df["dep_peak_per_h"] = peak.groupby("stop_id").size().reindex(df.index).fillna(0) / 2.0
        df["dep_peak_wc_per_h"] = peak[peak["wc"]].groupby("stop_id").size().reindex(df.index).fillna(0) / 2.0
        df["dep_night"] = night.groupby("stop_id").size().reindex(df.index).fillna(0)
        # trip ids per stop, so per-cell counts can take one vehicle serving several nearby stops once
        for colname, part in (("peak_trips", peak), ("night_trips", night)):
            trips_at = part.groupby("stop_id")["trip_id"].agg(lambda s: sorted(set(s)))
            df[colname] = [list(trips_at.get(sid, [])) for sid in df.index]
        s = stops.set_index("stop_id")
        df = df.join(s[["stop_name", "stop_lat", "stop_lon"]
                       + (["wheelchair_boarding"] if "wheelchair_boarding" in s.columns else [])], how="left")
        df["feed"] = tag
        df = df.reset_index().rename(columns={"index": "stop_id"})
        if prefix_ids:
            for colname in ("routes", "peak_trips", "night_trips"):
                df[colname] = df[colname].apply(lambda xs: [f"{tag}:{x}" for x in xs])
        out.append(df)
    df = pd.concat(out, ignore_index=True)
    df["lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df["wheelchair_boarding"] = df.get("wheelchair_boarding", pd.Series("", index=df.index)).fillna("")
    return df.dropna(subset=["lat", "lon"]).drop(columns=["stop_lat", "stop_lon"])

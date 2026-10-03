"""GIOŚ annual PM statistics per station (Małopolska) → IDW to cell centroids. API limit ≈ 2 req/min."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import requests

from core.common import USER_AGENT, log, now_iso, raw_dir
from core.context import Ctx

URL = "https://api.gios.gov.pl/pjp-api/v1/rest/statistics/getStatisticsForPollutants"
INDICATORS = {"PM10": "environment.pm10", "PM2,5": "environment.pm25"}


def fetch(force: bool = False) -> None:
    rd = raw_dir("krakow")
    ses = requests.Session()
    ses.headers["User-Agent"] = USER_AGENT
    for ind in INDICATORS:
        f = rd / f"gios_stats_{ind.replace(',', '_')}_all.json"
        if f.exists() and not force:
            continue
        rows, page, pages = [], 0, 1
        while page < pages:
            for attempt in range(6):
                r = ses.get(URL, timeout=120, params={"indicator": ind, "filter[wojewodztwo]": "małopolskie",
                                                      "size": 500, "page": page})
                if r.status_code == 429:
                    time.sleep(35)
                    continue
                r.raise_for_status()
                break
            j = r.json()
            pages = int(j.get("totalPages", 1))
            rows += j["Lista statystyk"]
            log.info("GIOŚ %s page %d/%d (%d rows)", ind, page + 1, pages, len(rows))
            page += 1
            time.sleep(31)
        f.write_text(json.dumps({"fetchedAt": now_iso(), "rows": rows}, ensure_ascii=False))


def stations() -> pd.DataFrame:
    d = json.loads((raw_dir("krakow") / "gios_stations.json").read_text())
    st = pd.DataFrame(d["Lista stacji pomiarowych"])
    return pd.DataFrame({"code": st["Kod stacji"], "name": st["Nazwa stacji"],
                         "lat": st["WGS84 φ N"].astype(float), "lon": st["WGS84 λ E"].astype(float)})


def station_means(ind: str, years: int = 3) -> pd.DataFrame:
    f = raw_dir("krakow") / f"gios_stats_{ind.replace(',', '_')}_all.json"
    if not f.exists():
        return pd.DataFrame(columns=["code", "value", "years"])
    df = pd.DataFrame(json.loads(f.read_text())["rows"])
    df = df[df["Kompletność [%]"].fillna(0) >= 75]
    last = df["Rok"].max()
    df = df[df["Rok"] > last - years]
    # prefer daily (24g) gravimetric series, otherwise hourly automatic
    df = df.sort_values("Czas uśredniania").drop_duplicates(["Kod stacji", "Rok"], keep="last")
    g = df.groupby("Kod stacji").agg(value=("Średnia [µg/m3]", "mean"), years=("Rok", lambda s: f"{s.min()}–{s.max()}"))
    return g.reset_index().rename(columns={"Kod stacji": "code"})


def idw(ctx: Ctx, pts_xy: np.ndarray, vals: np.ndarray, power: float = 2.0) -> np.ndarray:
    d = np.hypot(ctx.xy[:, None, 0] - pts_xy[None, :, 0], ctx.xy[:, None, 1] - pts_xy[None, :, 1])
    w = 1.0 / np.maximum(d, 200.0) ** power
    return (w * vals[None, :]).sum(1) / w.sum(1)


def features(ctx: Ctx) -> pd.DataFrame:
    from core.network import to_xy
    out = pd.DataFrame(index=range(len(ctx.grid)))
    st = stations()
    notes = []
    for ind, colname in INDICATORS.items():
        m = station_means(ind).merge(st, on="code")
        m["xy"] = list(to_xy(m, ctx.crs))
        xy = np.vstack(m["xy"].to_numpy()) if len(m) else np.zeros((0, 2))
        # stations within 25 km of the city centre
        c = ctx.xy.mean(0)
        near = np.hypot(*(xy - c).T) < 25_000 if len(xy) else np.zeros(0, bool)
        m, xy = m[near], xy[near]
        if len(m) < 2:
            out[colname] = np.nan
            notes.append(f"{ind}: <2 stations")
            continue
        out[colname] = idw(ctx, xy, m["value"].to_numpy()).round(1)
        notes.append(f"{ind}: {len(m)} stations, annual means {m['years'].iloc[0]}")
        log.info("[krakow] GIOŚ %s stations: %s", ind, dict(zip(m["code"], m["value"].round(1))))
    status = "ok" if out.notna().any().any() else "missing"
    ctx.man.record("gios", rows=int(out.notna().all(axis=1).sum()), status=status,
                   note="IDW (p=2) of GIOŚ station annual means; " + "; ".join(notes))
    return out


if __name__ == "__main__":
    fetch()

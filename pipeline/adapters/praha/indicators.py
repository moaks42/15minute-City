"""Praha indicator adapters: IPR noise, ČHMÚ 1×1 km air grid, Police ČR crime → MČ, MF rent map → k.ú."""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from core.common import log
from core.context import Ctx
from core.noise import noise_db


def noise(ctx: Ctx) -> np.ndarray:
    g = gpd.read_file(ctx.raw_file("ipr_noise_day"), engine="pyogrio", columns=["db_lo", "db_hi"])
    g = g.rename(columns={"db_lo": "lo", "db_hi": "hi"})
    v = noise_db(ctx, [g])
    ctx.ok("ipr_noise_day", int(np.isfinite(v).sum()),
           "IPR Hluková mapa automobilové dopravy – den (LAeq,day, road traffic) 5-dB bands; mean per cell. IPR "
           "publishes no tram/rail layer, so Praha = road only (Kraków = max(road, rail+tram), Lden)")
    return v


def air(ctx: Ctx) -> pd.DataFrame:
    shp = "petileti20-24_CR_rp_-_podle_zakona_201/sit1000_5lprum_20_24_JTSK_rp.shp"
    g = gpd.read_file(f"/vsizip/{ctx.raw_file('chmi_air')}/{shp}", engine="pyogrio",
                      columns=["PM10_rp_5l", "PM25_rp_5l", "NO2_rp_5l"])
    g = g.set_crs(5514, allow_override=True)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(ctx.xy[:, 0], ctx.xy[:, 1]), crs=ctx.crs).to_crs(5514)
    j = gpd.sjoin(pts, g, how="left", predicate="within")
    j = j[~j.index.duplicated()]
    out = pd.DataFrame({"environment.pm10": j["PM10_rp_5l"].to_numpy(float).round(1),
                        "environment.pm25": j["PM25_rp_5l"].to_numpy(float).round(1),
                        "environment.no2": j["NO2_rp_5l"].to_numpy(float).round(1)})
    ctx.ok("chmi_air", int(out.notna().all(axis=1).sum()),
           "ČHMÚ 5-year (2020–2024) annual-mean 1×1 km grid, S-JTSK; value of the grid square containing the centroid")
    return out


def _population_total(ctx: Ctx) -> tuple[int, str]:
    f = ctx.raw_file("csu_population")
    best = (None, None)
    with open(f, encoding="utf-8") as fh:
        r = csv.reader(fh)
        hdr = next(r)
        iu, iy, iv, ip = hdr.index("UZ24596C"), hdr.index("Roky"), hdr.index("Hodnota"), hdr.index("Pohlaví")
        ik = hdr.index("Ukazatel")
        for row in r:
            if len(row) == len(hdr) and row[iu] == "554782" and row[ip] == "Celkem" and row[ik].startswith("Počet obyvatel k 1. 7"):
                if best[1] is None or row[iy] > best[1]:
                    best = (int(float(row[iv])), row[iy])
    return best


def safety(ctx: Ctx) -> np.ndarray:
    types = json.loads(ctx.raw_file("police_cz_types").read_text())["polozky"]
    top = {p["kod"]: (p["kod"] if p["iri_1"] is None else int(p["iri_1"].rsplit("/", 1)[1])) for p in types}
    excluded = {13, 79, 97}  # fires/disasters, traffic accidents, misdemeanours (přestupky)
    frames = []
    months = sorted((ctx.raw / "police_months").glob("*.zip"))
    xmin, ymin, xmax, ymax = ctx.boundary.total_bounds
    for zf in months:
        with zipfile.ZipFile(zf) as z:
            name = next(n for n in z.namelist() if re.fullmatch(r"\d{6}\.csv", n.split("/")[-1]))
            df = pd.read_csv(z.open(name), usecols=["id", "x", "y", "types"])
        df = df[(df.x.between(xmin, xmax)) & (df.y.between(ymin, ymax))]
        df["top"] = df["types"].map(top)
        bad = df.groupby("id")["top"].apply(lambda s: bool(set(s) & excluded))
        df = df.drop_duplicates("id").set_index("id")
        frames.append(df[~bad.reindex(df.index).to_numpy()][["x", "y"]])
    inc = pd.concat(frames)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(inc.x, inc.y), crs=4326)
    j = gpd.sjoin(pts, ctx.districts[["district_id", "geometry"]], predicate="within")
    crimes = j.groupby("district_id").size()
    total, year = _population_total(ctx)
    pop = ctx.grid.groupby("district_id")["population_est"].sum()
    residents = pop / pop.sum() * total
    rate = (crimes.reindex(residents.index).fillna(0) / residents * 1000).round(2)
    log.info("[praha] crimes/1000 (top): %s", rate.sort_values(ascending=False).head(5).to_dict())
    ctx.ok("police_cz", int(len(j)), f"{len(months)} months ({months[0].stem}–{months[-1].stem}), criminal offences only "
           "(excl. přestupky, traffic accidents, fires); anonymised Voronoi points → městská část; residents = ČSÚ "
           f"{year} total split by RÚIAN address share. NON-COMMERCIAL licence")
    ctx.ok("csu_population", 1, f"Praha population {total} (1 July {year})")
    return ctx.grid["district_id"].map(rate).to_numpy(dtype=float)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))


def rent(ctx: Ctx, nb: gpd.GeoDataFrame) -> np.ndarray:
    raw = pd.read_excel(ctx.raw_file("mf_rent"), sheet_name="Cenové mapy nájemného", header=None)
    hdr = raw.iloc[0].tolist()
    data = raw.iloc[1:]
    data = data[data[0] == "Hlavní město Praha"]
    med_cols = [i for i, h in enumerate(hdr) if isinstance(h, str) and h.startswith("Mediánová hodnota")]
    vals = data[med_cols].apply(pd.to_numeric, errors="coerce")
    tab = pd.DataFrame({"code": data[3].astype(str), "name": data[1].astype(str),
                        "rent": vals.median(axis=1).round(0)})
    k = nb.copy()
    k = k.merge(tab[["code", "rent"]], left_on="neighborhood_id", right_on="code", how="left")
    miss = k["rent"].isna()
    if miss.any():  # fall back to normalised names
        byname = tab.assign(n=tab["name"].map(_norm)).set_index("n")["rent"]
        k.loc[miss, "rent"] = k.loc[miss, "neighborhood"].map(_norm).map(byname)
    m = dict(zip(k["neighborhood_id"], k["rent"]))
    out = ctx.grid["neighborhood_id"].map(m).to_numpy(dtype=float)
    ctx.ok("mf_rent", int(k["rent"].notna().sum()),
           f"MF cenová mapa nájemného 2026-08-15: median Kč/m²/month per k.ú. = median over size categories; "
           f"joined on k.ú. code ({int((~miss).sum())}) / name ({int(miss.sum())}); cells take their k.ú. value")
    return out


def features(ctx: Ctx) -> pd.DataFrame:
    out = pd.DataFrame(index=range(len(ctx.grid)))
    out["environment.noise_db"] = noise(ctx)
    a = air(ctx)
    for c in a.columns:
        out[c] = a[c].to_numpy()
    out["safety.crime_per_1000"] = safety(ctx)
    nb = gpd.read_file(ctx.raw_file("ipr_katastralni_uzemi"))
    nb["neighborhood_id"] = nb["KATUZE_KOD"].astype(int).astype(str)
    nb["neighborhood"] = nb["NAZEV_KATASTRU"].fillna(nb["NAZEV"])
    out["price.rent_per_m2"] = rent(ctx, nb)
    return out

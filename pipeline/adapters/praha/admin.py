"""Praha admin units: IPR městské části (57), IPR katastrální území (112), RÚIAN address points."""
from __future__ import annotations

import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from core.context import Ctx


def districts(ctx: Ctx) -> gpd.GeoDataFrame:
    d = gpd.read_file(ctx.raw_file("ipr_mestske_casti")).to_crs(4326)
    d["district_id"] = d["kod_mc"].astype(int).astype(str)
    d["district_name"] = d["nazev_mc"].str.strip()
    d["district_short_name"] = d["nazev_1"].str.strip()
    d = d.sort_values("district_name")
    ctx.ok("ipr_mestske_casti", len(d), "57 městských částí (IPR Praha), union = city boundary")
    return d[["district_id", "district_name", "district_short_name", "geometry"]]


def neighborhoods(ctx: Ctx) -> gpd.GeoDataFrame:
    k = gpd.read_file(ctx.raw_file("ipr_katastralni_uzemi")).to_crs(4326)
    k["neighborhood_id"] = k["KATUZE_KOD"].astype(int).astype(str)
    k["neighborhood"] = k["NAZEV_KATASTRU"].fillna(k["NAZEV"]).str.strip()
    ctx.ok("ipr_katastralni_uzemi", len(k), "112 katastrálních území; also the MF rent-map unit")
    return k[["neighborhood_id", "neighborhood", "geometry"]]


def ruian(ctx: Ctx) -> pd.DataFrame:
    with zipfile.ZipFile(ctx.raw_file("ruian")) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            df = pd.read_csv(f, sep=";", encoding="cp1250", dtype=str)
    # RÚIAN CSV stores positive Y/X; EPSG:5514 expects x = −Y, y = −X
    df["x"] = -pd.to_numeric(df["Souřadnice Y"], errors="coerce")
    df["y"] = -pd.to_numeric(df["Souřadnice X"], errors="coerce")
    return df.dropna(subset=["x", "y"])


def addresses(ctx: Ctx) -> gpd.GeoDataFrame:
    df = ruian(ctx)
    from core.geocode import fold
    street = df["Název ulice"].fillna("")
    cp = df["Číslo domovní"].fillna("")
    co = df["Číslo orientační"].fillna("") + df["Znak čísla orientačního"].fillna("")
    num = np.where(co != "", cp + "/" + co, np.where(df["Typ SO"].eq("č.ev."), "ev. " + cp, cp))
    base = np.where(street != "", street, df["Název části obce"].fillna(""))
    df["street"] = street
    df["label"] = pd.Series(base, index=df.index) + " " + pd.Series(num, index=df.index)
    # search key also accepts "Street co" and "Street cp" (people use the orientation number)
    df["search"] = [f"{fold(l)} {fold(b)} {c}".strip() for l, b, c in zip(df["label"], base, co)]
    g = gpd.GeoDataFrame(df[["Kód ADM", "Název MOMC", "Název části obce", "Název ulice", "Číslo domovní",
                             "Číslo orientační", "street", "label", "search"]],
                         geometry=gpd.points_from_xy(df["x"], df["y"]), crs=5514).to_crs(4326)
    # validate the sign flip against a known address: Hradčany, Hrad I. nádvoří 1 ≈ 50.0905 N, 14.4005 E
    p = g[(g["Název ulice"] == "Hrad I. nádvoří") & (g["Číslo domovní"] == "1")].geometry
    if len(p):
        assert abs(p.iloc[0].y - 50.090) < 0.01 and abs(p.iloc[0].x - 14.400) < 0.01, p.iloc[0]
    ctx.ok("ruian", len(g), "RÚIAN address points (obec 554782), S-JTSK sign flip x=−Y, y=−X validated "
           "against Pražský hrad; cp1250 ';' CSV")
    return g

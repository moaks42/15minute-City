"""Praha registers → POIs: MŠMT school register (geocoded by RÚIAN code), NRPZS health, Golemio playgrounds."""
from __future__ import annotations

import json
import re
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd

from core.common import log
from core.context import Ctx

from .admin import ruian

MSMT = {"A00": "kindergarten", "B00": "primary_school", "C00": "secondary_school"}
HOSP = {"Fakultní nemocnice", "Nemocnice", "Specializovaná nemocnice"}


def msmt_schools(ctx: Ctx) -> pd.DataFrame:
    d = json.loads(ctx.raw_file("msmt_schools").read_text())
    rows = []
    for e in d["list"]:
        for s in e["skolyAZarizeni"]:
            cat = MSMT.get(s["druh"])
            if not cat:
                continue
            for m in s.get("mistaVyuky") or [{"adresa": e.get("adresa")}]:
                a = m.get("adresa") or {}
                rows.append({"category": cat, "name": e.get("zkracenyNazev") or e.get("uplnyNazev"),
                             "adm": str(a.get("kodRUIAN") or ""), "izo": s.get("izo"), "redizo": e.get("redIzo")})
    df = pd.DataFrame(rows)
    r = ruian(ctx)
    pts = gpd.GeoSeries(gpd.points_from_xy(r["x"], r["y"]), crs=5514).to_crs(4326)
    lut = pd.DataFrame({"adm": r["Kód ADM"].astype(str), "lat": pts.y, "lon": pts.x}).drop_duplicates("adm")
    df = df.merge(lut, on="adm", how="left")
    miss = int(df["lat"].isna().sum())
    df = df.dropna(subset=["lat"]).drop_duplicates(["category", "izo", "lat", "lon"])
    log.info("[praha] MŠMT schools: %s (unmatched RÚIAN codes: %d)", df["category"].value_counts().to_dict(), miss)
    ctx.ok("msmt_schools", len(df), f"RSSZ Hl. m. Praha (LKOD JSON-LD); místa výuky geocoded by RÚIAN code "
           f"(unmatched {miss}); A00→kindergarten, B00→primary, C00→secondary")
    return pd.DataFrame({"category": df["category"], "name": df["name"], "lat": df["lat"], "lon": df["lon"],
                         "source": "msmt_schools", "extra_json": [json.dumps({"izo": i, "redizo": z}) for i, z in
                                                          zip(df["izo"], df["redizo"])]})


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))


def mpsv_nurseries(ctx: Ctx) -> pd.DataFrame:
    """MPSV register of dětské skupiny (children's groups, the Czech nursery form), active, in Praha."""
    f = ctx.raw_file("mpsv_detske_skupiny")
    df = pd.read_csv(f, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    df = df[df["kraj_ds"].str.contains("Praha") & df["stav_opravneni_ds"].eq("Aktivní")]
    r = ruian(ctx)
    pts = gpd.GeoSeries(gpd.points_from_xy(r["x"], r["y"]), crs=5514).to_crs(4326)
    r = r.assign(lat=pts.y.to_numpy(), lon=pts.x.to_numpy(), st=r["Název ulice"].fillna("").map(_n),
                 part=r["Název části obce"].fillna("").map(_n))
    by_cp = r.drop_duplicates(["st", "Číslo domovní"]).set_index(["st", "Číslo domovní"])[["lat", "lon"]]
    by_co = r[r["Číslo orientační"].notna()].drop_duplicates(["st", "Číslo orientační"]).set_index(
        ["st", "Číslo orientační"])[["lat", "lon"]]
    by_part = r.drop_duplicates(["part", "Číslo domovní"]).set_index(["part", "Číslo domovní"])[["lat", "lon"]]
    rows, miss = [], 0
    for _, x in df.iterrows():
        addr = x["misto_poskytovani_ds"].split(",")[0].strip()
        m = re.match(r"^(.*?)\s+(\d+)(?:/(\d+)\w*)?$", addr)
        hit = None
        if m:
            st, cp, co = _n(m.group(1)), m.group(2), m.group(3)
            for idx, key in ((by_cp, (st, cp)), (by_co, (st, co or cp)), (by_part, (st, cp))):
                if key in idx.index:
                    hit = idx.loc[key]
                    break
        if hit is None:
            miss += 1
            continue
        rows.append({"category": "nursery", "name": x["nazev_ds"], "lat": float(hit["lat"]), "lon": float(hit["lon"]),
                     "source": "mpsv_detske_skupiny",
                     "extra_json": json.dumps({"kod": x["kod_detske_skupiny"], "kapacita": x["kapacita_ds"]},
                                              ensure_ascii=False)})
    out = pd.DataFrame(rows)
    ctx.ok("mpsv_detske_skupiny", len(out), f"active dětské skupiny in Praha: {len(df)}; geocoded via RÚIAN street + "
           f"house number {len(out)}, unmatched {miss}; added to POI category nursery (with OSM jesle)")
    return out


def nrpzs(ctx: Ctx) -> pd.DataFrame:
    n = pd.read_csv(ctx.raw_file("nrpzs"), dtype=str)
    n = n[n["ZZ_kraj_kod"] == "CZ010"].copy()
    ll = n["ZZ_GPS"].fillna("").str.extract(r"POINT\(\s*([\d.]+)\s+([\d.]+)\s*\)").astype(float)
    n["lat"], n["lon"] = ll[0], ll[1]  # NRPZS writes POINT(lat lon)
    n = n.dropna(subset=["lat"])
    druh = n["ZZ_druh_nazev"].fillna("")
    obor = n["ZZ_obor_pece"].fillna("").str.lower()
    forma = n["ZZ_forma_pece"].fillna("").str.lower()
    hosp = druh.isin(HOSP)
    rules = {
        "gp_clinic": druh.str.contains("všeob. prakt. lékaře") | obor.str.contains("všeobecné praktické lékařství"),
        "paediatrician": druh.str.contains("pro děti a dorost") | obor.str.contains("praktické lékařství pro děti a dorost")
        | (obor.str.contains("dětské lékařství") & ~hosp),
        "gynaecology": druh.str.contains("gynekologa") | (obor.str.contains("gynekologie a porodnictví") & forma.str.contains("ambulantní")),
        "maternity_ward": hosp & obor.str.contains("gynekologie a porodnictví|neonatologie") & forma.str.contains("lůžková"),
        "hospital_er": hosp & druh.isin({"Fakultní nemocnice", "Nemocnice"}) & obor.str.contains("urgentní medicína|anesteziologie"),
        "hospital": hosp,
        "dentist": druh.str.contains("stomatologa") | obor.str.contains("zubní lékařství"),
        "pharmacy": druh.eq("Lékárna"),
    }
    out = []
    for cat, m in rules.items():
        s = n[m.to_numpy()].drop_duplicates(["ZZ_nazev", "lat", "lon"])
        out.append(pd.DataFrame({"category": cat, "name": s["ZZ_nazev"], "lat": s["lat"], "lon": s["lon"],
                                 "source": "nrpzs",
                                 "extra_json": [json.dumps({"druh": a, "obor": b[:200]}, ensure_ascii=False)
                                                for a, b in zip(s["ZZ_druh_nazev"].fillna(""), s["ZZ_obor_pece"].fillna(""))]}))
    df = pd.concat(out, ignore_index=True)
    log.info("[praha] NRPZS: %s", df["category"].value_counts().to_dict())
    ctx.ok("nrpzs", len(df), "kraj CZ010; GP, paediatrics, gynaecology, maternity (inpatient G&P/neonatology "
           "at hospitals), ER (acute hospitals), dentists, pharmacies derived from druh/obor/forma péče")
    return df


def golemio(ctx: Ctx) -> pd.DataFrame:
    out = []
    for key, cat in (("golemio_playgrounds", "playground"), ("golemio_gardens", "park"), ("golemio_libraries", "library")):
        f = ctx.raw_file(key)
        if not f.exists():
            ctx.missing(key, "not fetched (Golemio key?)")
            continue
        g = gpd.read_file(f)
        g = g[g.geometry.notna()]
        p = g.geometry.representative_point()
        out.append(pd.DataFrame({"category": cat, "name": g.get("name", pd.Series("", index=g.index)).fillna(""),
                                 "lat": p.y, "lon": p.x, "source": key, "extra_json": "{}"}))
        ctx.ok(key, len(g), f"added to POI category '{cat}'")
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def extra_pois(ctx: Ctx) -> pd.DataFrame:
    df = pd.concat([msmt_schools(ctx), nrpzs(ctx), golemio(ctx), mpsv_nurseries(ctx)], ignore_index=True)
    df.attrs["replace"] = ["kindergarten", "primary_school", "secondary_school", "gp_clinic", "paediatrician",
                           "gynaecology", "maternity_ward", "hospital_er", "dentist", "pharmacy"]
    return df


def parks(ctx: Ctx) -> gpd.GeoDataFrame:
    f = ctx.raw_file("ipr_parks")
    if not f.exists():
        return gpd.GeoDataFrame(geometry=[], crs=4326)
    g = gpd.read_file(f)
    g = g[g.geometry.notna() & g.geom_type.isin(["Polygon", "MultiPolygon"])]
    ctx.ok("ipr_parks", len(g), "IPR 'Parky (ÚAP)' polygons added to the park ≥ 2 ha layer")
    return g[["geometry"]]

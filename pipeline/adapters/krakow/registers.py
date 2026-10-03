"""Kraków registers → POIs: MEN SIO schools (geocoded via EMUiA), NFZ wards/clinics, ZTP bike racks."""
from __future__ import annotations

import json
import re
import time
import unicodedata

import geopandas as gpd
import pandas as pd
import requests

from core.common import USER_AGENT, log, now_iso
from core.context import Ctx

KINDER = {"Przedszkole", "Punkt przedszkolny", "Zespół wychowania przedszkolnego"}
PRIMARY = {"Szkoła podstawowa"}
SECONDARY = {"Liceum ogólnokształcące", "Technikum", "Branżowa szkoła I stopnia"}
PREFIX = re.compile(r"^(ul|al|aleja|aleje|os|osiedle|pl|plac|rondo|bulwar|skwer|marsz|gen|ks|św|prof|dr|im)\.?\s+")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for _ in range(3):
        s = PREFIX.sub("", s)
    return s


def norm_no(s: str) -> str:
    return re.sub(r"\s+", "", str(s).lower()).split("/")[0]


class Geocoder:
    """Exact (street, number) → EMUiA point; fallbacks: surname-only street key, then street centroid."""

    def __init__(self, addr: gpd.GeoDataFrame):
        a = addr.copy()
        a["k"] = a["nazwa_ulicy"].fillna("").map(norm)
        a["k2"] = a["k"].str.split().str[-1].fillna("")
        a["n"] = a["numer_adresowy"].fillna("").map(norm_no)
        a["lon"], a["lat"] = a.geometry.x, a.geometry.y
        self.full = a.drop_duplicates(["k", "n"]).set_index(["k", "n"])[["lat", "lon"]]
        self.last = a.drop_duplicates(["k2", "n"]).set_index(["k2", "n"])[["lat", "lon"]]
        self.street = a.groupby("k")[["lat", "lon"]].median()

    def __call__(self, street: str, number: str):
        k, n = norm(street), norm_no(number)
        for idx, key in ((self.full, (k, n)), (self.last, (k.split()[-1] if k else "", n))):
            if key in idx.index:
                r = idx.loc[key]
                return float(r["lat"]), float(r["lon"]), "exact"
        if k in self.street.index:
            r = self.street.loc[k]
            return float(r["lat"]), float(r["lon"]), "street"
        return None, None, "none"


def men_schools(ctx: Ctx, geo: Geocoder) -> pd.DataFrame:
    df = pd.read_excel(ctx.raw_file("men_schools"), dtype=str)
    k = df[df["idTerytPowiat"] == "1261"]
    cat = pd.Series(None, index=k.index, dtype=object)
    youth = k["Kategoria uczniów"].ne("Dorośli")
    cat[k["Typ podmiotu"].isin(KINDER)] = "kindergarten"
    cat[k["Typ podmiotu"].isin(PRIMARY) & youth] = "primary_school"
    cat[k["Typ podmiotu"].isin(SECONDARY) & k["Kategoria uczniów"].eq("Dzieci lub młodzież")] = "secondary_school"
    k = k.assign(category=cat).dropna(subset=["category"])
    res = [geo(s, n) for s, n in zip(k["Ulica"].fillna(""), k["Numer domu"].fillna(""))]
    k = k.assign(lat=[r[0] for r in res], lon=[r[1] for r in res], how=[r[2] for r in res])
    stats = k["how"].value_counts().to_dict()
    log.info("[krakow] MEN schools geocoding: %s", stats)
    k = k.dropna(subset=["lat"])
    out = pd.DataFrame({"category": k["category"], "name": k["Nazwa placówki"].str.title(), "lat": k["lat"],
                        "lon": k["lon"], "source": "men_schools",
                        "extra_json": [json.dumps({"rspo": r, "public": p, "geocode": h}, ensure_ascii=False)
                                       for r, p, h in zip(k["RSPO"], k["Publiczność"], k["how"])]})
    ctx.ok("men_schools", len(out), f"SIO 30.09.2025, powiat 1261; geocoded via EMUiA {stats}")
    return out


def nfz(ctx: Ctx, geo: Geocoder) -> pd.DataFrame:
    """NFZ 'Informator o terminach leczenia' providers in Kraków for selected benefits (has lat/lon)."""
    wanted = {"ODDZIAŁ POŁOŻNICZO-GINEKOLOGICZNY": "maternity_ward",
              "PORADNIA POŁOŻNICZO-GINEKOLOGICZNA": "gynaecology"}
    cache = ctx.raw / "nfz_queues_krakow.json"
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        data, ses = {}, requests.Session()
        ses.headers["User-Agent"] = USER_AGENT
        for b in wanted:
            rows, page = [], 1
            while True:
                r = ses.get("https://api.nfz.gov.pl/app-itl-api/queues", timeout=60, params={
                    "case": 1, "province": "06", "locality": "KRAKÓW", "benefit": b, "format": "json",
                    "limit": 25, "page": page, "api-version": "1.3"})
                r.raise_for_status()
                j = r.json()
                rows += [x["attributes"] for x in j.get("data", [])]
                if not j.get("links", {}).get("next"):
                    break
                page += 1
                time.sleep(0.3)
            data[b] = rows
        cache.write_text(json.dumps(data, ensure_ascii=False))
    out = []
    for b, rows in data.items():
        for a in rows:
            lat, lon = a.get("latitude"), a.get("longitude")
            how = "nfz"
            if not lat:
                m = re.match(r"^(?:UL\.\s*|OS\.\s*|AL\.\s*)?(.*?)\s+(\d+\w*)", a.get("address", ""))
                lat, lon, how = geo(m.group(1), m.group(2)) if m else (None, None, "none")
            if lat:
                out.append({"category": wanted[b], "name": a.get("provider", "").title(), "lat": float(lat),
                            "lon": float(lon), "source": "nfz",
                            "extra_json": json.dumps({"benefit": b, "address": a.get("address"), "geocode": how},
                                                     ensure_ascii=False)})
    out = pd.DataFrame(out).drop_duplicates(["category", "lat", "lon"])
    ctx.man.record("nfz", url="https://api.nfz.gov.pl/app-itl-api/queues", fetchedAt=now_iso(), licence="NFZ open API",
                   rows=len(out), status="ok",
                   note="providers of ODDZIAŁ POŁOŻNICZO-GINEKOLOGICZNY (maternity) / PORADNIA POŁOŻNICZO-GINEKOLOGICZNA (gynaecology) in Kraków")
    return out


def ztp_racks(ctx: Ctx) -> pd.DataFrame:
    g = gpd.read_file(ctx.raw_file("ztp_hub_bike_racks"))
    g = g[g.geometry.notna()]
    p = g.geometry.representative_point()
    ctx.ok("ztp_hub_bike_racks", len(g), "ZTP bike racks (stojaki) added to POI category bike_rack")
    return pd.DataFrame({"category": "bike_rack", "name": "", "lat": p.y, "lon": p.x, "source": "ztp_hub_bike_racks",
                         "extra_json": "{}"})


def nurseries(ctx: Ctx) -> pd.DataFrame:
    """UM Kraków layer 'Żłobki i kluby dziecięce' (municipal + non-municipal), last edited 2023-07."""
    out = []
    for key, public in (("krk_zlobki_samorzadowe", True), ("krk_zlobki_niesamorzadowe", False)):
        f = ctx.raw_file(key)
        if not f.exists():
            ctx.missing(key, "not fetched")
            continue
        g = gpd.read_file(f)
        g = g[g.geometry.notna()]
        out.append(pd.DataFrame({"category": "nursery", "name": g.get("Miejsce_pr", pd.Series("", index=g.index)).fillna("").str.strip(),
                                 "lat": g.geometry.y, "lon": g.geometry.x, "source": key,
                                 "extra_json": json.dumps({"public": public})}))
        ctx.ok(key, len(g), f"żłobki i kluby dziecięce ({'samorządowe' if public else 'niesamorządowe'}), layer edited 2023-07; "
               "added to POI category nursery together with OSM")
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def extra_pois(ctx: Ctx) -> pd.DataFrame:
    geo = Geocoder(ctx.addresses)
    parts = [men_schools(ctx, geo), nfz(ctx, geo), ztp_racks(ctx), nurseries(ctx)]
    df = pd.concat(parts, ignore_index=True)
    # MEN register is authoritative for schools; OSM kept for nursery (żłobki are not in SIO)
    df.attrs["replace"] = ["kindergarten", "primary_school", "secondary_school"]
    return df

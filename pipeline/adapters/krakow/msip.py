"""MSIP (UM Kraków): 18 dzielnice and EMUiA address points. Source CRS is EPSG:2178 (PL-2000 zone 7)."""
from __future__ import annotations

import geopandas as gpd

from core.context import Ctx


def districts(ctx: Ctx) -> gpd.GeoDataFrame:
    d = gpd.read_file(f"zip://{ctx.raw_file('msip_districts')}!Dzielnice.geojson")
    if d.crs is None:
        d = d.set_crs(2178)
    d["district_id"] = d["id_dzielni"].astype(int).astype(str)  # contract: "1"…"18"
    d["district_name"] = d["nazwa"].str.strip()
    d["district_full_name"] = d["nazwa_peln"].str.strip()
    d["district_no"] = d["nr_dzielni"]
    d = d.sort_values("id_dzielni").to_crs(4326)
    ctx.ok("msip_districts", len(d), "18 dzielnic, union = city boundary")
    return d[["district_id", "district_name", "district_full_name", "district_no", "geometry"]]


def addresses(ctx: Ctx) -> gpd.GeoDataFrame:
    a = gpd.read_file(f"zip://{ctx.raw_file('msip_addresses')}!Adresy.geojson", engine="pyogrio",
                      columns=["nazwa_ulicy", "numer_adresowy", "kod_pocztowy", "numer_dzielnicy"])
    if a.crs is None:
        a = a.set_crs(2178)
    a = a[a.geometry.notna()].to_crs(4326)
    from core.geocode import fold
    a["street"] = a["nazwa_ulicy"].fillna("").str.strip()
    a["label"] = (a["street"] + " " + a["numer_adresowy"].fillna("").str.strip()).str.strip()
    a["search"] = a["label"].map(fold)
    ctx.ok("msip_addresses", len(a), "EMUiA address points → habitable mask + population proxy")
    return a

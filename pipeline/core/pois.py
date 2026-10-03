"""Shared POI category vocabulary (identical in both cities) and OSM → pois extraction.

pois.parquet columns: category, name, lat, lon, h3_9, source, extra_json
City adapters append rows with the same categories (e.g. MEN/MŠMT schools, NRPZS health, Golemio playgrounds).
"""
from __future__ import annotations

import json
import re

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

from . import osm
from .osm import col

# category -> human description (documentation + validate.py)
CATEGORIES = {
    "supermarket": "shop=supermarket",
    "discount_grocery": "supermarket of a discount brand (Lidl, Biedronka, Aldi, Penny, Netto, Kaufland)",
    "convenience": "shop=convenience",
    "pharmacy": "amenity=pharmacy",
    "post_office": "amenity=post_office",
    "parcel_locker": "amenity=parcel_locker / vending=parcel_pickup",
    "bakery": "shop=bakery",
    "marketplace": "amenity=marketplace",
    "atm": "amenity=atm or bank with atm=yes",
    "shop": "any shop=*",
    "gp_clinic": "amenity=doctors|clinic / healthcare=doctor|clinic (not dentist); PL: POZ; CZ: NRPZS praktický lékař",
    "paediatrician": "paediatrics speciality (OSM tag/name; CZ: NRPZS)",
    "gynaecology": "gynaecology speciality (OSM tag/name; CZ: NRPZS; PL: NFZ)",
    "hospital": "amenity=hospital",
    "hospital_er": "hospital with emergency=yes (CZ: NRPZS urgentní příjem)",
    "maternity_ward": "inpatient obstetrics (CZ: NRPZS; PL: NFZ oddział położniczy)",
    "dentist": "amenity=dentist / healthcare=dentist",
    "nursery": "żłobek / jesle / dětská skupina (amenity=childcare + name)",
    "kindergarten": "amenity=kindergarten; PL: MEN przedszkole; CZ: MŠMT mateřská škola",
    "primary_school": "PL: MEN szkoła podstawowa; CZ: MŠMT základní škola; OSM amenity=school fallback",
    "secondary_school": "PL: MEN liceum/technikum/branżowa; CZ: MŠMT střední škola/gymnázium",
    "university": "amenity=university",
    "library": "amenity=library",
    "playground": "leisure=playground",
    "park": "leisure=park",
    "sports": "leisure=sports_centre|fitness_centre|sports_hall|ice_rink|swimming_pool(public)",
    "kids_sports": "public swimming pool / water park / sports centre or hall",
    "restaurant": "amenity=restaurant|fast_food|food_court",
    "cafe": "amenity=cafe|ice_cream",
    "bar": "amenity=bar|pub|biergarten",
    "nightclub": "amenity=nightclub",
    "culture": "amenity=theatre|cinema|arts_centre|community_centre; tourism=museum|gallery",
    "bench": "amenity=bench",
    "bike_rack": "amenity=bicycle_parking (PL: + ZTP stojaki)",
    "bikeshare_station": "amenity=bicycle_rental",
    "tram_stop": "GTFS route_type 0 stop / railway=tram_stop",
    "bus_stop": "GTFS route_type 3 stop",
    "metro_station": "GTFS route_type 1 stop / station=subway",
    "rail_station": "railway=station|halt (train) / GTFS route_type 2",
    "transit_stop": "any GTFS stop with weekday service",
}
# categories written to pois.parquet (contracts/DATA_CONTRACT.md §3); the rest are internal helpers
VOCAB = ["supermarket", "discount_grocery", "pharmacy", "post_office", "parcel_locker", "bakery", "marketplace", "atm",
         "playground", "park", "nursery", "kindergarten", "primary_school", "secondary_school", "university", "library",
         "gp_clinic", "paediatrician", "gynaecology", "dentist", "hospital_er", "maternity_ward", "bus_stop", "tram_stop",
         "metro_station", "rail_station", "bike_rack", "bikeshare_station", "culture", "sports", "kids_sports",
         "restaurant", "cafe", "bar", "nightclub", "bench"]

DISCOUNT = re.compile(r"lidl|biedronka|aldi|penny|netto|kaufland|dino", re.I)
NURSERY = re.compile(r"żłob|zlob|jesl|dětsk[áa] skupin|detska skupin|nursery|kids club", re.I)
PAED = re.compile(r"pediatr|paediatr|dětsk[ýy] lékař|detsky lekar", re.I)
GYN = re.compile(r"gyn|położn|polozn|porod", re.I)

OSM_FILTERS = ["nwr/amenity", "nwr/shop", "nwr/leisure", "nwr/tourism=museum,gallery", "nwr/healthcare",
               "nwr/railway=station,halt,tram_stop", "nwr/station=subway", "nwr/vending=parcel_pickup"]


def _pt(gdf: gpd.GeoDataFrame) -> gpd.GeoSeries:
    g = gdf.geometry
    return g.where(g.geom_type == "Point", g.representative_point())


def from_osm(city: str) -> pd.DataFrame:
    g = osm.export(city, "pois", OSM_FILTERS)
    g = g[g.geometry.notna()].copy()
    pts = _pt(g)
    g["lon"], g["lat"] = pts.x, pts.y
    amen, shop, leis, tour, hc = (col(g, k).fillna("") for k in ("amenity", "shop", "leisure", "tourism", "healthcare"))
    name = col(g, "name").fillna("")
    brand = col(g, "brand").fillna("") + " " + name
    spec = col(g, "healthcare:speciality").fillna("")
    emerg = col(g, "emergency").fillna("")
    access = col(g, "access").fillna("")
    rail, station = col(g, "railway").fillna(""), col(g, "station").fillna("")
    subway = col(g, "subway").fillna("")
    vending, atm = col(g, "vending").fillna(""), col(g, "atm").fillna("")

    rules: dict[str, pd.Series] = {
        "supermarket": shop.eq("supermarket"),
        "discount_grocery": shop.isin(["supermarket", "convenience"]) & brand.str.contains(DISCOUNT),
        "convenience": shop.eq("convenience"),
        "pharmacy": amen.eq("pharmacy") | hc.eq("pharmacy"),
        "post_office": amen.eq("post_office"),
        "parcel_locker": amen.eq("parcel_locker") | vending.eq("parcel_pickup"),
        "bakery": shop.eq("bakery"),
        "marketplace": amen.eq("marketplace"),
        "atm": amen.eq("atm") | (amen.eq("bank") & atm.eq("yes")),
        "shop": shop.ne(""),
        "gp_clinic": (amen.isin(["doctors", "clinic"]) | hc.isin(["doctor", "clinic", "centre"]))
        & ~amen.eq("dentist") & ~hc.eq("dentist"),
        "paediatrician": spec.str.contains("paediatrics") | name.str.contains(PAED),
        "gynaecology": spec.str.contains("gynaecology|obstetrics") | (amen.isin(["doctors", "clinic"]) & name.str.contains(GYN)),
        "hospital": amen.eq("hospital") | hc.eq("hospital"),
        "hospital_er": (amen.eq("hospital") | hc.eq("hospital")) & emerg.eq("yes"),
        "maternity_ward": (amen.eq("hospital") | hc.eq("hospital")) & spec.str.contains("obstetrics|maternity"),
        "dentist": amen.eq("dentist") | hc.eq("dentist"),
        "nursery": (amen.isin(["childcare", "kindergarten"]) & name.str.contains(NURSERY)),
        "kindergarten": amen.eq("kindergarten") & ~name.str.contains(NURSERY),
        "primary_school": amen.eq("school"),  # refined/replaced by MEN / MŠMT adapters
        "university": amen.eq("university"),
        "library": amen.eq("library"),
        "playground": leis.eq("playground"),
        "park": leis.eq("park"),
        "sports": leis.isin(["sports_centre", "fitness_centre", "sports_hall", "ice_rink"])
        | (leis.eq("swimming_pool") & ~access.isin(["private", "customers", "no"])),
        "kids_sports": leis.eq("water_park") | (leis.isin(["swimming_pool", "sports_centre", "sports_hall"])
                                                & ~access.isin(["private", "customers", "no"])),
        "restaurant": amen.isin(["restaurant", "fast_food", "food_court"]),
        "cafe": amen.isin(["cafe", "ice_cream"]),
        "bar": amen.isin(["bar", "pub", "biergarten"]),
        "nightclub": amen.eq("nightclub"),
        "culture": amen.isin(["theatre", "cinema", "arts_centre", "community_centre", "concert_hall"])
        | tour.isin(["museum", "gallery"]),
        "bench": amen.eq("bench"),
        "bike_rack": amen.eq("bicycle_parking"),
        "bikeshare_station": amen.eq("bicycle_rental"),
        "tram_stop": rail.eq("tram_stop"),
        "metro_station": station.eq("subway") | (rail.eq("station") & subway.eq("yes")),
        "rail_station": rail.isin(["station", "halt"]) & ~station.isin(["subway", "light_rail", "monorail"])
        & ~subway.eq("yes") & ~col(g, "tram").fillna("").eq("yes"),
    }
    rows = []
    for cat, mask in rules.items():
        sub = g[mask.fillna(False).to_numpy()]
        if sub.empty:
            continue
        extra = sub[["osm_type", "osm_id"]].astype(str).apply(lambda r: json.dumps({"osm": f"{r.iloc[0]}/{r.iloc[1]}"}), axis=1)
        rows.append(pd.DataFrame({"category": cat, "name": col(sub, "name").fillna("").to_numpy(),
                                  "lat": sub["lat"].to_numpy(), "lon": sub["lon"].to_numpy(),
                                  "source": f"osm_{city}", "extra_json": extra.to_numpy()}))
    df = pd.concat(rows, ignore_index=True)
    return df


def finalize(df: pd.DataFrame, res: int = 9) -> pd.DataFrame:
    df = df.dropna(subset=["lat", "lon"]).copy()
    df["h3_9"] = [h3.latlng_to_cell(a, b, res) for a, b in zip(df["lat"].to_numpy(), df["lon"].to_numpy())]
    df["name"] = df["name"].fillna("").astype(str)
    df["extra_json"] = df["extra_json"].fillna("{}").astype(str)
    df["lat"] = df["lat"].astype(np.float64).round(6)
    df["lon"] = df["lon"].astype(np.float64).round(6)
    return df[["category", "name", "lat", "lon", "h3_9", "source", "extra_json"]].reset_index(drop=True)

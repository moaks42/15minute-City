"""addresses.parquet for the engine's local geocoder (contracts-v2, DATA_CONTRACT §3b)."""
from __future__ import annotations

import re
import unicodedata

import geopandas as gpd
import h3
import pandas as pd


def fold(s: str) -> str:
    """lower-case, diacritics-free (ł→l) form used for accent-insensitive matching."""
    s = unicodedata.normalize("NFKD", str(s).lower().replace("ł", "l"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s/.-]", " ", s)).strip()


def addresses(addr: gpd.GeoDataFrame) -> pd.DataFrame:
    a = addr.to_crs(4326)
    lat, lon = a.geometry.y.round(6).to_numpy(), a.geometry.x.round(6).to_numpy()
    out = pd.DataFrame({
        "street": a["street"].astype("string"),
        "housenumber": a["housenumber"].astype("string"),
        "postcode": a["postcode"].astype("string"),
        "lat": lat.astype("float64"), "lon": lon.astype("float64"),
        "h3_9": pd.array([h3.latlng_to_cell(y, x, 9) for y, x in zip(lat, lon)], dtype="string"),
        "source": a["source"].astype("string"),
    })
    out = out[(out["street"].fillna("") != "") & (out["housenumber"].fillna("") != "")]
    return out.drop_duplicates(["street", "housenumber", "lat", "lon"]).reset_index(drop=True)
